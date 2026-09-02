"""Small DB-API compatibility layer for SQLite and managed Postgres."""
import sqlite3
from contextlib import contextmanager

_MIGRATION_LOCK_KEY = 4_242_424_242


def resolve_dialect(settings) -> str:
    return "postgres" if (getattr(settings, "database_url", "") or "").strip() else "sqlite"


def connect_sqlite(path: str):
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=30000")
    return db


class _PostgresCursor:
    """Expose the tiny sqlite cursor surface used by Store."""
    def __init__(self, cursor, lastrowid=None):
        self._cursor = cursor
        self.lastrowid = lastrowid

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __iter__(self):
        return iter(self._cursor)


class _PostgresConnection:
    """Translate the application's portable qmark SQL to psycopg's style."""
    def __init__(self, connection):
        self._connection = connection

    def execute(self, sql, parameters=()):
        statement = sql.replace("?", "%s")
        wants_id = statement.lstrip().upper().startswith("INSERT INTO ATTEMPTS(")
        if wants_id and " RETURNING " not in statement.upper():
            statement += " RETURNING id"
        cursor = self._connection.execute(statement, parameters)
        lastrowid = cursor.fetchone()["id"] if wants_id else None
        return _PostgresCursor(cursor, lastrowid)

    def commit(self):
        return self._connection.commit()

    def rollback(self):
        return self._connection.rollback()

    def close(self):
        return self._connection.close()

    def __enter__(self):
        self._connection.__enter__()
        return self

    def __exit__(self, *args):
        return self._connection.__exit__(*args)


def connect_postgres(dsn: str):
    # Lazy import keeps the complete offline SQLite test path independent of
    # psycopg and avoids importing a production driver during module loading.
    import psycopg
    from psycopg.rows import dict_row
    return _PostgresConnection(psycopg.connect(dsn, row_factory=dict_row))


def connect(settings):
    return connect_postgres(settings.database_url) if resolve_dialect(settings) == "postgres" else connect_sqlite(settings.database)


def is_integrity_error(exc: BaseException) -> bool:
    if isinstance(exc, sqlite3.IntegrityError):
        return True
    try:
        import psycopg
        return isinstance(exc, psycopg.errors.IntegrityError)
    except ImportError:
        return False


def integrity_errors() -> tuple:
    """Backward-compatible helper; prefer :func:`is_integrity_error`."""
    errors = [sqlite3.IntegrityError]
    try:
        import psycopg
        errors.append(psycopg.errors.IntegrityError)
    except ImportError:
        pass
    return tuple(errors)


@contextmanager
def advisory_migration_lock(conn, dialect: str):
    """Serialize automatic migrations across concurrent cold starts."""
    if dialect == "postgres":
        conn.execute("SELECT pg_advisory_xact_lock(?)", (_MIGRATION_LOCK_KEY,))
        try:
            yield
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
