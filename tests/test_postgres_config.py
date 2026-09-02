"""C8: dialect selection and idempotent, import-free migrations."""
from src.db import connect_sqlite, resolve_dialect
from src.migrations import BASE, MIGRATIONS, migrate
from tests.test_review_ui import oauth_settings


def test_dialect_is_postgres_only_when_a_database_url_is_configured(tmp_path):
    assert resolve_dialect(oauth_settings(tmp_path)) == "sqlite"
    assert resolve_dialect(oauth_settings(tmp_path, database_url="postgres://h/db")) == "postgres"
    assert resolve_dialect(oauth_settings(tmp_path, database_url="   ")) == "sqlite"


def test_settings_from_env_reads_either_url_without_logging_it(monkeypatch, tmp_path):
    for name in ("GITHUB_OAUTH_CLIENT_ID", "GITHUB_OAUTH_CLIENT_SECRET",
                 "GITHUB_OAUTH_CALLBACK_URL", "SESSION_SECRET", "RELEASE_MANAGER_WEB_URL"):
        monkeypatch.setenv(name, "x/auth/github/callback" if "CALLBACK" in name else "x")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_URL", "postgres://user:secretpw@db/rm")
    from src.config import Settings

    cfg = Settings.from_env()
    assert cfg.database_url == "postgres://user:secretpw@db/rm"
    assert "secretpw" not in repr(cfg)


def test_running_migrations_twice_is_a_no_op(tmp_path):
    path = str(tmp_path / "state.db")
    db = connect_sqlite(path)
    for statement in BASE["sqlite"]:
        db.execute(statement)
    first = migrate(db, "sqlite")
    db.commit()
    rows_after_first = db.execute("SELECT version FROM schema_versions ORDER BY version").fetchall()

    second = migrate(db, "sqlite")  # must not raise and must add nothing
    db.commit()
    rows_after_second = db.execute("SELECT version FROM schema_versions ORDER BY version").fetchall()

    assert first == second == [v for v, _ in MIGRATIONS["sqlite"]]
    assert [r[0] for r in rows_after_first] == [r[0] for r in rows_after_second]
    db.close()


def test_migrations_are_well_formed_for_both_dialects():
    assert [v for v, _ in MIGRATIONS["sqlite"]] == [v for v, _ in MIGRATIONS["postgres"]]
    for statements in dict(MIGRATIONS["postgres"]).values():
        assert statements and all(isinstance(s, str) for s in statements)
    # The json_extract legacy backfill is SQLite-only; no data import for Postgres.
    from src import migrations as m

    assert "json_extract" in m._LEGACY_BACKFILL
