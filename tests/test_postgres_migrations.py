"""Execute the Postgres cold-start migration path against a strict DB-API double.

This is intentionally more than SQL string inspection: concurrent ``Store``
initialization runs the real advisory-lock and migration control flow, and the
double rejects SQLite-only syntax while modelling the shared version table.
"""
from contextlib import nullcontext
from threading import Lock
import concurrent.futures
import re

from src.migrations import MIGRATIONS
from src.store import Store


class Cursor:
    def __init__(self, rows=(), rowcount=0):
        self.rows, self.rowcount = list(rows), rowcount
        self.lastrowid = None

    def fetchall(self): return self.rows
    def fetchone(self): return self.rows[0] if self.rows else None
    def __iter__(self): return iter(self.rows)


class PostgresServer:
    def __init__(self):
        self.lock = Lock()
        self.versions = set()
        self.executed = []

    def connect(self): return PostgresConnection(self)


class PostgresConnection:
    def __init__(self, server):
        self.server, self.held, self.pending = server, False, set()

    def execute(self, sql, parameters=()):
        normalized = " ".join(sql.split())
        # Fail if migration selection accidentally emits SQLite SQL.
        assert "INSERT OR IGNORE" not in normalized
        assert "json_extract" not in normalized
        assert not (" ADD COLUMN " in normalized and
                    " ADD COLUMN IF NOT EXISTS " not in normalized)
        self.server.executed.append((normalized, tuple(parameters)))
        if normalized.startswith("SELECT pg_advisory_xact_lock"):
            self.server.lock.acquire(); self.held = True
            return Cursor([{"pg_advisory_xact_lock": None}])
        if normalized == "SELECT version FROM schema_versions":
            return Cursor([{"version": value} for value in sorted(self.server.versions)])
        if normalized.startswith("INSERT INTO schema_versions"):
            match = re.search(r"VALUES\((?:%s|\?)\)", normalized)
            assert match and len(parameters) == 1
            self.pending.add(parameters[0])
            return Cursor(rowcount=1)
        # The strict syntax checks above are the relevant execution semantics;
        # all CREATE/ALTER/seed statements are accepted like PostgreSQL DDL.
        assert normalized.startswith(("CREATE ", "ALTER ", "DROP ", "INSERT INTO "))
        return Cursor(rowcount=1)

    def commit(self):
        self.server.versions.update(self.pending); self.pending.clear()
        if self.held: self.held = False; self.server.lock.release()

    def rollback(self):
        self.pending.clear()
        if self.held: self.held = False; self.server.lock.release()

    def close(self):
        if self.held: self.rollback()

    def __enter__(self): return self
    def __exit__(self, exc_type, *_):
        self.rollback() if exc_type else self.commit()


def test_concurrent_postgres_cold_starts_are_locked_and_idempotent(monkeypatch):
    server = PostgresServer()
    monkeypatch.setattr("src.store.connect_postgres", lambda _dsn: server.connect())

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        stores = list(pool.map(
            lambda _: Store("unused", dialect="postgres", database_url="postgres://redacted"),
            range(4),
        ))

    assert len(stores) == 4
    expected = {version for version, _ in MIGRATIONS["postgres"]}
    assert server.versions == expected
    lock_calls = [sql for sql, _ in server.executed if sql.startswith("SELECT pg_advisory_xact_lock")]
    assert len(lock_calls) == 4
    # Serialization means each version is inserted exactly once despite races.
    inserts = [params[0] for sql, params in server.executed
               if sql.startswith("INSERT INTO schema_versions")]
    assert inserts == sorted(expected)
