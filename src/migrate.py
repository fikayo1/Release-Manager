"""Operator command: apply schema migrations once, explicitly.

    python -m src.migrate

Reads configuration from the environment (:class:`src.config.Settings`), opens a
connection for the selected dialect, takes the advisory migration lock, applies
every unapplied version, and prints the applied set. Safe to run repeatedly and
safe to run concurrently with a cold start (both hold the same lock).
"""
import sys

from .config import Settings
from .db import advisory_migration_lock, connect, resolve_dialect
from .migrations import BASE, migrate


def main() -> int:
    settings = Settings.from_env()
    dialect = resolve_dialect(settings)
    conn = connect(settings)
    try:
        with advisory_migration_lock(conn, dialect):
            for statement in BASE[dialect]:
                conn.execute(statement)
            applied = migrate(conn, dialect)
        if dialect == "sqlite":
            conn.commit()
    finally:
        conn.close()
    print(f"dialect={dialect} applied_versions={applied}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
