"""Additive, transactional, dialect-aware schema migrations.

Each version is a list of individual statements (not one ``executescript``
blob) so it runs unchanged on SQLite and Postgres. ``migrate`` is idempotent:
already-applied versions are skipped, so running it twice in a row is a no-op.
Callers that may race (serverless cold starts) hold
:func:`src.db.advisory_migration_lock` around the call.
"""

# Base tables created before the versioned migrations. Kept here so both the
# standalone ``Store`` and the migration CLI create an identical schema.
BASE = {
    "sqlite": [
        "CREATE TABLE IF NOT EXISTS scans(id TEXT PRIMARY KEY, data TEXT NOT NULL, created_at TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS verdicts(scan_id TEXT PRIMARY KEY REFERENCES scans(id), data TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS packs(id TEXT PRIMARY KEY,scan_id TEXT UNIQUE REFERENCES scans(id),status TEXT NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS decisions(id INTEGER PRIMARY KEY,pack_id TEXT UNIQUE REFERENCES packs(id),decision TEXT NOT NULL,actor TEXT NOT NULL,reason TEXT,created_at TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY,pack_id TEXT REFERENCES packs(id),result TEXT NOT NULL,error TEXT,url TEXT,created_at TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS reconciliations(id INTEGER PRIMARY KEY,pack_id TEXT REFERENCES packs(id),result TEXT NOT NULL,detail TEXT,created_at TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,kind TEXT NOT NULL,subject_id TEXT NOT NULL,actor TEXT,detail TEXT NOT NULL,created_at TEXT NOT NULL)",
    ],
    "postgres": [
        "CREATE TABLE IF NOT EXISTS scans(id TEXT PRIMARY KEY, data TEXT NOT NULL, created_at TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS verdicts(scan_id TEXT PRIMARY KEY REFERENCES scans(id), data TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS packs(id TEXT PRIMARY KEY,scan_id TEXT UNIQUE REFERENCES scans(id),status TEXT NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS decisions(id BIGSERIAL PRIMARY KEY,pack_id TEXT UNIQUE REFERENCES packs(id),decision TEXT NOT NULL,actor TEXT NOT NULL,reason TEXT,created_at TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS attempts(id BIGSERIAL PRIMARY KEY,pack_id TEXT REFERENCES packs(id),result TEXT NOT NULL,error TEXT,url TEXT,created_at TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS reconciliations(id BIGSERIAL PRIMARY KEY,pack_id TEXT REFERENCES packs(id),result TEXT NOT NULL,detail TEXT,created_at TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS audit(id BIGSERIAL PRIMARY KEY,kind TEXT NOT NULL,subject_id TEXT NOT NULL,actor TEXT,detail TEXT NOT NULL,created_at TEXT NOT NULL)",
    ],
}

MIGRATIONS = {
    "sqlite": (
        (1, [
            "CREATE TABLE IF NOT EXISTS schedules(id INTEGER PRIMARY KEY CHECK(id=1), expression TEXT NOT NULL, enabled INTEGER NOT NULL, updated_at TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS operations(id TEXT PRIMARY KEY, source TEXT NOT NULL, repository TEXT NOT NULL, status TEXT NOT NULL, result TEXT, scan_id TEXT REFERENCES scans(id), pack_id TEXT REFERENCES packs(id), error TEXT, started_at TEXT NOT NULL, finished_at TEXT, scheduled_for TEXT)",
            "CREATE TABLE IF NOT EXISTS scan_lease(id INTEGER PRIMARY KEY CHECK(id=1), owner TEXT NOT NULL, operation_id TEXT NOT NULL, expires_at TEXT NOT NULL, heartbeat_at TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS scheduler_state(id INTEGER PRIMARY KEY CHECK(id=1), heartbeat_at TEXT, last_slot TEXT, last_operation_id TEXT, last_result TEXT, last_error TEXT)",
            "INSERT OR IGNORE INTO schedules(id,expression,enabled,updated_at) VALUES(1,'0 * * * *',0,'1970-01-01T00:00:00+00:00')",
            "INSERT OR IGNORE INTO scheduler_state(id) VALUES(1)",
        ]),
        (2, [
            "ALTER TABLE scheduler_state ADD COLUMN last_run_at TEXT",
            "CREATE UNIQUE INDEX IF NOT EXISTS scheduled_operation_slot ON operations(scheduled_for) WHERE source='scheduled' AND scheduled_for IS NOT NULL",
        ]),
        (3, [
            "CREATE TABLE IF NOT EXISTS github_connection(id INTEGER PRIMARY KEY CHECK(id=1), login TEXT NOT NULL, account_id TEXT, access_token TEXT NOT NULL, refresh_token TEXT, expires_at TEXT, selected_repository TEXT, status TEXT NOT NULL DEFAULT 'connected', updated_at TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS oauth_states(state_digest TEXT PRIMARY KEY, session_id TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, consumed_at TEXT)",
            "CREATE INDEX IF NOT EXISTS oauth_states_expiry ON oauth_states(expires_at)",
        ]),
        (4, [
            "CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, login TEXT NOT NULL, account_id TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS user_sessions(session_id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS user_github_connections(user_id TEXT PRIMARY KEY REFERENCES users(id), login TEXT NOT NULL, account_id TEXT, access_token TEXT NOT NULL, refresh_token TEXT, expires_at TEXT, selected_repository TEXT, status TEXT NOT NULL DEFAULT 'connected', updated_at TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS resource_owners(kind TEXT NOT NULL, resource_id TEXT NOT NULL, user_id TEXT NOT NULL REFERENCES users(id), PRIMARY KEY(kind,resource_id))",
            "CREATE INDEX IF NOT EXISTS resource_owners_user ON resource_owners(user_id,kind)",
            "CREATE TABLE IF NOT EXISTS user_schedules(user_id TEXT PRIMARY KEY REFERENCES users(id), expression TEXT NOT NULL, enabled INTEGER NOT NULL, updated_at TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS user_scan_leases(user_id TEXT NOT NULL REFERENCES users(id), operation_id TEXT PRIMARY KEY, expires_at TEXT NOT NULL, heartbeat_at TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS pack_keys(user_id TEXT NOT NULL, repository TEXT NOT NULL, version TEXT NOT NULL, pack_id TEXT NOT NULL UNIQUE REFERENCES packs(id), PRIMARY KEY(user_id,repository,version))",
        ]),
        (5, [
            "ALTER TABLE operations ADD COLUMN user_id TEXT REFERENCES users(id)",
            "DROP INDEX IF EXISTS scheduled_operation_slot",
            "CREATE UNIQUE INDEX IF NOT EXISTS scheduled_operation_user_slot ON operations(user_id,scheduled_for) WHERE source='scheduled' AND scheduled_for IS NOT NULL AND user_id IS NOT NULL",
            "CREATE UNIQUE INDEX IF NOT EXISTS scheduled_operation_legacy_slot ON operations(scheduled_for) WHERE source='scheduled' AND scheduled_for IS NOT NULL AND user_id IS NULL",
        ]),
    ),
    "postgres": (
        (1, [
            "CREATE TABLE IF NOT EXISTS schedules(id INTEGER PRIMARY KEY CHECK(id=1), expression TEXT NOT NULL, enabled INTEGER NOT NULL, updated_at TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS operations(id TEXT PRIMARY KEY, source TEXT NOT NULL, repository TEXT NOT NULL, status TEXT NOT NULL, result TEXT, scan_id TEXT REFERENCES scans(id), pack_id TEXT REFERENCES packs(id), error TEXT, started_at TEXT NOT NULL, finished_at TEXT, scheduled_for TEXT)",
            "CREATE TABLE IF NOT EXISTS scan_lease(id INTEGER PRIMARY KEY CHECK(id=1), owner TEXT NOT NULL, operation_id TEXT NOT NULL, expires_at TEXT NOT NULL, heartbeat_at TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS scheduler_state(id INTEGER PRIMARY KEY CHECK(id=1), heartbeat_at TEXT, last_slot TEXT, last_operation_id TEXT, last_result TEXT, last_error TEXT)",
            "INSERT INTO schedules(id,expression,enabled,updated_at) VALUES(1,'0 * * * *',0,'1970-01-01T00:00:00+00:00') ON CONFLICT (id) DO NOTHING",
            "INSERT INTO scheduler_state(id) VALUES(1) ON CONFLICT (id) DO NOTHING",
        ]),
        (2, [
            "ALTER TABLE scheduler_state ADD COLUMN IF NOT EXISTS last_run_at TEXT",
            "CREATE UNIQUE INDEX IF NOT EXISTS scheduled_operation_slot ON operations(scheduled_for) WHERE source='scheduled' AND scheduled_for IS NOT NULL",
        ]),
        (3, [
            "CREATE TABLE IF NOT EXISTS github_connection(id INTEGER PRIMARY KEY CHECK(id=1), login TEXT NOT NULL, account_id TEXT, access_token TEXT NOT NULL, refresh_token TEXT, expires_at TEXT, selected_repository TEXT, status TEXT NOT NULL DEFAULT 'connected', updated_at TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS oauth_states(state_digest TEXT PRIMARY KEY, session_id TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, consumed_at TEXT)",
            "CREATE INDEX IF NOT EXISTS oauth_states_expiry ON oauth_states(expires_at)",
        ]),
        (4, [
            "CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, login TEXT NOT NULL, account_id TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS user_sessions(session_id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS user_github_connections(user_id TEXT PRIMARY KEY REFERENCES users(id), login TEXT NOT NULL, account_id TEXT, access_token TEXT NOT NULL, refresh_token TEXT, expires_at TEXT, selected_repository TEXT, status TEXT NOT NULL DEFAULT 'connected', updated_at TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS resource_owners(kind TEXT NOT NULL, resource_id TEXT NOT NULL, user_id TEXT NOT NULL REFERENCES users(id), PRIMARY KEY(kind,resource_id))",
            "CREATE INDEX IF NOT EXISTS resource_owners_user ON resource_owners(user_id,kind)",
            "CREATE TABLE IF NOT EXISTS user_schedules(user_id TEXT PRIMARY KEY REFERENCES users(id), expression TEXT NOT NULL, enabled INTEGER NOT NULL, updated_at TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS user_scan_leases(user_id TEXT NOT NULL REFERENCES users(id), operation_id TEXT PRIMARY KEY, expires_at TEXT NOT NULL, heartbeat_at TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS pack_keys(user_id TEXT NOT NULL, repository TEXT NOT NULL, version TEXT NOT NULL, pack_id TEXT NOT NULL UNIQUE REFERENCES packs(id), PRIMARY KEY(user_id,repository,version))",
        ]),
        (5, [
            "ALTER TABLE operations ADD COLUMN IF NOT EXISTS user_id TEXT REFERENCES users(id)",
            "DROP INDEX IF EXISTS scheduled_operation_slot",
            "CREATE UNIQUE INDEX IF NOT EXISTS scheduled_operation_user_slot ON operations(user_id,scheduled_for) WHERE source='scheduled' AND scheduled_for IS NOT NULL AND user_id IS NOT NULL",
            "CREATE UNIQUE INDEX IF NOT EXISTS scheduled_operation_legacy_slot ON operations(scheduled_for) WHERE source='scheduled' AND scheduled_for IS NOT NULL AND user_id IS NULL",
        ]),
    ),
}

# Existing SQLite scans are retained and represented as legacy operations. A
# fresh Postgres target starts empty, so this backfill is SQLite-only.
_LEGACY_BACKFILL = """INSERT OR IGNORE INTO operations(id,source,repository,status,result,scan_id,pack_id,started_at,finished_at)
  SELECT 'legacy-'||s.id,'legacy',COALESCE(json_extract(s.data,'$.repository'),'unknown'),'completed',
  CASE WHEN p.id IS NULL THEN 'non_release' ELSE 'draft_created' END,s.id,p.id,s.created_at,s.created_at
  FROM scans s LEFT JOIN packs p ON p.scan_id=s.id"""


def migrate(db, dialect: str = "sqlite"):
    """Apply every unapplied migration version for ``dialect``. Idempotent."""
    db.execute(
        "CREATE TABLE IF NOT EXISTS schema_versions(version INTEGER PRIMARY KEY, "
        "applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    applied = {
        row["version"] if isinstance(row, dict) else row[0]
        for row in db.execute("SELECT version FROM schema_versions").fetchall()
    }
    placeholder = "?" if dialect == "sqlite" else "%s"
    for version, statements in MIGRATIONS[dialect]:
        if version in applied:
            continue
        for statement in statements:
            db.execute(statement)
        if dialect == "sqlite":
            db.execute(_LEGACY_BACKFILL)
        db.execute(f"INSERT INTO schema_versions(version) VALUES({placeholder})", (version,))
    return sorted(applied | {v for v, _ in MIGRATIONS[dialect]})
