"""Additive, transactional SQLite schema migrations."""

MIGRATIONS = ((1, """
CREATE TABLE IF NOT EXISTS schedules(
 id INTEGER PRIMARY KEY CHECK(id=1), expression TEXT NOT NULL, enabled INTEGER NOT NULL,
 updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS operations(
 id TEXT PRIMARY KEY, source TEXT NOT NULL, repository TEXT NOT NULL,
 status TEXT NOT NULL, result TEXT, scan_id TEXT REFERENCES scans(id), pack_id TEXT REFERENCES packs(id),
 error TEXT, started_at TEXT NOT NULL, finished_at TEXT, scheduled_for TEXT);
CREATE TABLE IF NOT EXISTS scan_lease(
 id INTEGER PRIMARY KEY CHECK(id=1), owner TEXT NOT NULL, operation_id TEXT NOT NULL,
 expires_at TEXT NOT NULL, heartbeat_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS scheduler_state(
 id INTEGER PRIMARY KEY CHECK(id=1), heartbeat_at TEXT, last_slot TEXT, last_operation_id TEXT,
 last_result TEXT, last_error TEXT);
INSERT OR IGNORE INTO schedules(id,expression,enabled,updated_at) VALUES(1,'0 * * * *',0,'1970-01-01T00:00:00+00:00');
INSERT OR IGNORE INTO scheduler_state(id) VALUES(1);
"""), (2, """
ALTER TABLE scheduler_state ADD COLUMN last_run_at TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS scheduled_operation_slot
  ON operations(scheduled_for) WHERE source='scheduled' AND scheduled_for IS NOT NULL;
"""))


def migrate(db):
    db.execute("CREATE TABLE IF NOT EXISTS schema_versions(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    applied = {r[0] for r in db.execute("SELECT version FROM schema_versions")}
    for version, sql in MIGRATIONS:
        if version not in applied:
            db.executescript(sql)
            # Existing scans are retained and represented as legacy operations.
            db.execute("""INSERT OR IGNORE INTO operations(id,source,repository,status,result,scan_id,pack_id,started_at,finished_at)
              SELECT 'legacy-'||s.id,'legacy',COALESCE(json_extract(s.data,'$.repository'),'unknown'),'completed',
              CASE WHEN p.id IS NULL THEN 'non_release' ELSE 'draft_created' END,s.id,p.id,s.created_at,s.created_at
              FROM scans s LEFT JOIN packs p ON p.scan_id=s.id""")
            db.execute("INSERT INTO schema_versions(version) VALUES(?)", (version,))
