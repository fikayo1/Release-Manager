"""Dialect-aware persistence and compare-and-set governance transitions.

The SQL below is written for SQLite, which remains the default and the only
store the test and Playwright suites exercise. Postgres is selected by passing
``dialect="postgres"`` (wired from ``DATABASE_URL`` / ``POSTGRES_URL`` in
:mod:`src.config` / :mod:`src.app`); connection handling and the migration
runner are dialect-aware via :mod:`src.db` and :mod:`src.migrations`.
"""
import json

from .models import primitive
from .crypto import decrypt_token, encrypt_token
from .db import advisory_migration_lock, connect_postgres, connect_sqlite, is_integrity_error
from .migrations import BASE, migrate


class StateError(RuntimeError):
    pass


class Store:
    def __init__(self, path: str, *, dialect: str = "sqlite", database_url: str = "",
                 token_key: bytes = b""):
        self.path = path
        self.dialect = dialect
        self.database_url = database_url
        # 32-byte key used to encrypt OAuth tokens at rest. Empty -> tokens are
        # stored as-is (bare unit tests that never build Settings).
        self.token_key = token_key or b""
        self.init()

    def connect(self):
        if self.dialect == "postgres":
            return connect_postgres(self.database_url)
        return connect_sqlite(self.path)

    def init(self):
        db = self.connect()
        try:
            with advisory_migration_lock(db, self.dialect):
                for statement in BASE[self.dialect]:
                    db.execute(statement)
                migrate(db, self.dialect)
        finally:
            db.close()

    # Multi-user identity is kept in additive tables so existing installations
    # migrate without rewriting immutable release evidence.
    def bind_session(self, session_id, login, account_id, now):
        user_id = "github:" + str(account_id)
        with self.connect() as db:
            db.execute("INSERT INTO users(id,login,account_id,created_at) VALUES(?,?,?,?) ON CONFLICT(account_id) DO UPDATE SET login=excluded.login",
                       (user_id, login, str(account_id), now))
            db.execute("INSERT INTO user_sessions(session_id,user_id,created_at) VALUES(?,?,?) ON CONFLICT(session_id) DO UPDATE SET user_id=excluded.user_id",
                       (session_id, user_id, now))
        return user_id

    def session_user(self, session_id):
        if not session_id:
            return None
        with self.connect() as db:
            row = db.execute("SELECT user_id FROM user_sessions WHERE session_id=?", (session_id,)).fetchone()
            return row["user_id"] if row else None

    def singleton_user(self):
        """Return an identity only when the database contains exactly one user."""
        with self.connect() as db:
            rows = db.execute("SELECT id FROM users LIMIT 2").fetchall()
        return rows[0]["id"] if len(rows) == 1 else None

    def save_user_github_connection(self, user_id, login, account_id, access_token, refresh_token, expires_at, now):
        with self.connect() as db:
            previous = db.execute("SELECT selected_repository FROM user_github_connections WHERE user_id=?", (user_id,)).fetchone()
            selected = previous["selected_repository"] if previous else None
            db.execute("""INSERT INTO user_github_connections VALUES(?,?,?,?,?,?,?,'connected',?)
                ON CONFLICT(user_id) DO UPDATE SET login=excluded.login,account_id=excluded.account_id,
                access_token=excluded.access_token,refresh_token=excluded.refresh_token,
                expires_at=excluded.expires_at,status='connected',updated_at=excluded.updated_at""",
                (user_id, login, str(account_id), encrypt_token(access_token, key=self.token_key),
                 encrypt_token(refresh_token, key=self.token_key), expires_at, selected, now))

    def user_github_credentials(self, user_id):
        with self.connect() as db:
            row = db.execute("SELECT access_token,refresh_token,expires_at,status FROM user_github_connections WHERE user_id=?", (user_id,)).fetchone()
            if not row: return None
            data = dict(row)
            data["access_token"] = decrypt_token(data.get("access_token"), key=self.token_key)
            data["refresh_token"] = decrypt_token(data.get("refresh_token"), key=self.token_key)
            return data

    def user_github_connection(self, user_id):
        with self.connect() as db:
            row = db.execute("SELECT login,account_id,selected_repository,status,updated_at FROM user_github_connections WHERE user_id=?", (user_id,)).fetchone()
            return dict(row) if row else None

    def select_user_repository(self, user_id, full_name, now):
        with self.connect() as db:
            if db.execute("UPDATE user_github_connections SET selected_repository=?,updated_at=? WHERE user_id=? AND status='connected'", (full_name, now, user_id)).rowcount != 1:
                raise StateError("GitHub connection requires reconnect")

    def own(self, kind, resource_id, user_id):
        with self.connect() as db:
            db.execute("INSERT INTO resource_owners(kind,resource_id,user_id) VALUES(?,?,?) ON CONFLICT(kind,resource_id) DO NOTHING", (kind, resource_id, user_id))

    def resource_owner(self, kind, resource_id):
        with self.connect() as db:
            row = db.execute("SELECT user_id FROM resource_owners WHERE kind=? AND resource_id=?", (kind, resource_id)).fetchone()
            return row["user_id"] if row else None

    def owns(self, kind, resource_id, user_id):
        return self.resource_owner(kind, resource_id) == user_id

    def scoped_operations(self, user_id):
        owned = {r["resource_id"] for r in self._owned_rows("operation", user_id)}
        return [item for item in self.operations() if item["id"] in owned]

    def scoped_scans(self, user_id):
        with self.connect() as db:
            rows = db.execute("""SELECT s.data,s.created_at FROM scans s JOIN resource_owners o
                ON o.kind='scan' AND o.resource_id=s.id WHERE o.user_id=? ORDER BY s.created_at DESC,s.id DESC""", (user_id,)).fetchall()
            return [{**json.loads(r["data"]), "created_at": r["created_at"]} for r in rows]

    def scoped_packs(self, user_id):
        owned = {r["resource_id"] for r in self._owned_rows("pack", user_id)}
        return [item for item in self.packs() if item["id"] in owned]

    def _owned_rows(self, kind, user_id):
        with self.connect() as db:
            return db.execute("SELECT resource_id FROM resource_owners WHERE kind=? AND user_id=?", (kind,user_id)).fetchall()

    def running_count(self, user_id, now):
        with self.connect() as db:
            db.execute("DELETE FROM user_scan_leases WHERE expires_at<=?", (now,))
            return db.execute("SELECT COUNT(*) AS n FROM user_scan_leases WHERE user_id=?", (user_id,)).fetchone()["n"]

    def acquire_user_lease(self, user_id, operation_id, now, expires, limit):
        """Atomically admit a lease under the per-user concurrency limit."""
        db = self.connect()
        try:
            if self.dialect == "sqlite":
                db.execute("BEGIN IMMEDIATE")
            else:
                # Serialize admission for this user without blocking other users.
                db.execute("SELECT pg_advisory_xact_lock(hashtext(?))", ("scan:" + user_id,))
            db.execute("DELETE FROM user_scan_leases WHERE expires_at<=?", (now,))
            count = db.execute("SELECT COUNT(*) AS n FROM user_scan_leases WHERE user_id=?", (user_id,)).fetchone()["n"]
            if count >= limit:
                db.rollback()
                return False
            db.execute("INSERT INTO user_scan_leases VALUES(?,?,?,?)", (user_id,operation_id,expires,now))
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def release_user_lease(self, operation_id):
        with self.connect() as db: db.execute("DELETE FROM user_scan_leases WHERE operation_id=?", (operation_id,))

    def create_oauth_state(self, digest, session_id, created_at, expires_at):
        with self.connect() as db:
            db.execute("DELETE FROM oauth_states WHERE expires_at<?", (created_at,))
            db.execute("INSERT INTO oauth_states VALUES(?,?,?,?,NULL)",
                       (digest, session_id, created_at, expires_at))

    def consume_oauth_state(self, digest, session_id, consumed_at):
        with self.connect() as db:
            return db.execute(
                "UPDATE oauth_states SET consumed_at=? WHERE state_digest=? AND session_id=? AND consumed_at IS NULL AND expires_at>=?",
                (consumed_at, digest, session_id, consumed_at),
            ).rowcount == 1

    def save_github_connection(self, login, account_id, access_token, refresh_token, expires_at, now):
        with self.connect() as db:
            previous = db.execute("SELECT selected_repository FROM github_connection WHERE id=1").fetchone()
            selected = previous["selected_repository"] if previous else None
            db.execute("""INSERT INTO github_connection VALUES(1,?,?,?,?,?,?,'connected',?)
                ON CONFLICT(id) DO UPDATE SET login=excluded.login,account_id=excluded.account_id,
                access_token=excluded.access_token,refresh_token=excluded.refresh_token,
                expires_at=excluded.expires_at,status='connected',updated_at=excluded.updated_at""",
                (login, str(account_id) if account_id is not None else None,
                 encrypt_token(access_token, key=self.token_key),
                 encrypt_token(refresh_token, key=self.token_key), expires_at, selected, now))

    def github_credentials(self):
        with self.connect() as db:
            row = db.execute("SELECT access_token,refresh_token,expires_at,status FROM github_connection WHERE id=1").fetchone()
            if not row:
                return None
            data = dict(row)
            data["access_token"] = decrypt_token(data.get("access_token"), key=self.token_key)
            data["refresh_token"] = decrypt_token(data.get("refresh_token"), key=self.token_key)
            return data

    def github_connection(self):
        """Safe browser-facing connection data (credential columns excluded)."""
        with self.connect() as db:
            row = db.execute("SELECT login,account_id,selected_repository,status,updated_at FROM github_connection WHERE id=1").fetchone()
            return dict(row) if row else None

    def mark_github_revoked(self, now):
        with self.connect() as db:
            db.execute("UPDATE github_connection SET status='revoked',updated_at=? WHERE id=1", (now,))

    def mark_user_github_revoked(self, user_id, now):
        with self.connect() as db:
            db.execute("UPDATE user_github_connections SET status='revoked',updated_at=? WHERE user_id=?", (now, user_id))

    def select_repository(self, full_name, now):
        with self.connect() as db:
            if db.execute("UPDATE github_connection SET selected_repository=?,updated_at=? WHERE id=1 AND status='connected'", (full_name, now)).rowcount != 1:
                raise StateError("GitHub connection requires reconnect")

    def event(self, db, kind, subject, now, detail=None, actor=None):
        db.execute(
            "INSERT INTO audit(kind,subject_id,actor,detail,created_at) VALUES(?,?,?,?,?)",
            (kind, subject, actor, json.dumps(detail or {}), now),
        )

    def save_scan(self, scan, verdict, now):
        valid = {x.id for x in (*scan.commits, *scan.pulls)}
        if not set(verdict.evidence_ids) <= valid:
            raise StateError("verdict cites evidence outside scan")
        with self.connect() as db:
            db.execute("INSERT INTO scans VALUES(?,?,?)", (scan.id, json.dumps(primitive(scan)), now))
            db.execute("INSERT INTO verdicts VALUES(?,?)", (scan.id, json.dumps(primitive(verdict))))
            self.event(db, "scan", scan.id, now, {"worthy": verdict.worthy})

    def save_pack(self, pack, now):
        with self.connect() as db:
            db.execute(
                "INSERT INTO packs VALUES(?,?,?,?,?)",
                (pack.id, pack.scan_id, pack.status.value, json.dumps(primitive(pack)), now),
            )
            self.event(db, "pack", pack.id, now, {"version": pack.version})

    def save_current_pack(self, pack, now, user_id, repository):
        """Create or refresh the user's canonical repository/version pack."""
        from dataclasses import replace
        with self.connect() as db:
            row = db.execute("SELECT pack_id FROM pack_keys WHERE user_id=? AND repository=? AND version=?",
                             (user_id, repository, pack.version)).fetchone()
            if row:
                canonical = replace(pack, id=row["pack_id"])
                db.execute("UPDATE packs SET scan_id=?,data=?,created_at=? WHERE id=?",
                           (pack.scan_id, json.dumps(primitive(canonical)), now, canonical.id))
                self.event(db, "pack_reused", canonical.id, now,
                           {"version": canonical.version, "scan_id": pack.scan_id})
                return canonical
            db.execute("INSERT INTO packs VALUES(?,?,?,?,?)",
                       (pack.id, pack.scan_id, pack.status.value, json.dumps(primitive(pack)), now))
            db.execute("INSERT INTO pack_keys(user_id,repository,version,pack_id) VALUES(?,?,?,?)",
                       (user_id, repository, pack.version, pack.id))
            db.execute("INSERT INTO resource_owners(kind,resource_id,user_id) VALUES('pack',?,?)",
                       (pack.id, user_id))
            self.event(db, "pack", pack.id, now, {"version": pack.version})
            return pack

    def pack(self, pid):
        with self.connect() as db:
            row = db.execute("SELECT * FROM packs WHERE id=?", (pid,)).fetchone()
            if not row:
                raise KeyError(pid)
            return {**json.loads(row["data"]), "status": row["status"]}

    def packs(self):
        """Return every pack newest first, with a stable id tie-break."""
        with self.connect() as db:
            rows = db.execute("SELECT * FROM packs ORDER BY created_at DESC, id DESC").fetchall()
            return [
                {**json.loads(row["data"]), "status": row["status"], "created_at": row["created_at"]}
                for row in rows
            ]

    def scan(self, scan_id):
        with self.connect() as db:
            row = db.execute("SELECT data,created_at FROM scans WHERE id=?", (scan_id,)).fetchone()
            if not row:
                raise KeyError(scan_id)
            return {**json.loads(row["data"]), "created_at": row["created_at"]}

    def pack_audit(self, pid):
        """Return chronological activity directly concerning a pack."""
        return [record for record in self.audit() if record["subject_id"] == pid]

    def decide(self, pid, decision, actor, reason, now):
        actor = (actor or "").strip()
        reason = (reason or "").strip()
        if decision not in {"approved", "rejected"}:
            raise StateError("decision must be approved or rejected")
        if not actor or not reason:
            raise StateError("actor and reason are required")
        target = decision
        with self.connect() as db:
            # An ``approved`` row without a decision is an in-progress pack
            # (for example, one imported from an older canonical snapshot),
            # not a completed human decision. Permit it to enter governance,
            # while the NOT EXISTS guard keeps recorded decisions terminal.
            if db.execute(
                """UPDATE packs SET status=?
                   WHERE id=? AND status IN ('pending','approved')
                     AND NOT EXISTS (
                       SELECT 1 FROM decisions WHERE pack_id=packs.id
                     )""",
                (target, pid),
            ).rowcount != 1:
                raise StateError("pack is not awaiting a decision")
            db.execute(
                "INSERT INTO decisions(pack_id,decision,actor,reason,created_at) VALUES(?,?,?,?,?)",
                (pid, decision, actor, reason, now),
            )
            pack = self._pack_data(db, pid)
            self.event(
                db,
                "decision",
                pid,
                now,
                {"decision": decision, "reason": reason, "version": pack["version"]},
                actor,
            )

    @staticmethod
    def _pack_data(db, pid):
        row = db.execute("SELECT data FROM packs WHERE id=?", (pid,)).fetchone()
        if not row:
            raise KeyError(pid)
        return json.loads(row["data"])

    @staticmethod
    def _approver(db, pid):
        row = db.execute(
            "SELECT actor FROM decisions WHERE pack_id=? AND decision='approved'", (pid,)
        ).fetchone()
        return row["actor"] if row else None

    def _publication_detail(self, db, pid, result, url=None, error=None):
        pack = self._pack_data(db, pid)
        return {
            "approver": self._approver(db, pid),
            "version": pack["version"],
            "tag": pack["tag"],
            "title": pack["title"],
            "body": pack["body"],
            "publication_result": result,
            "url": url,
            "error": error,
        }

    def claim_publish(self, pid, now):
        """Durably reserve one publish attempt.

        A process may die after this transaction.  The deliberately durable
        ``publishing`` state is therefore also accepted by reconciliation.
        """
        with self.connect() as db:
            if db.execute(
                "UPDATE packs SET status='publishing' WHERE id=? AND status IN ('approved','retry_safe')",
                (pid,),
            ).rowcount != 1:
                raise StateError("human approval or retry-safe reconciliation required")
            cur = db.execute(
                "INSERT INTO attempts(pack_id,result,created_at) VALUES(?,'started',?)", (pid, now)
            )
            detail = self._publication_detail(db, pid, "started")
            detail["attempt"] = cur.lastrowid
            self.event(db, "publish_started", pid, now, detail, detail["approver"])
            return cur.lastrowid

    def finish(self, pid, attempt, result, now, url=None, error=None, status=None):
        """Atomically finalize an attempt, pack state, and complete receipt."""
        with self.connect() as db:
            if db.execute(
                "UPDATE attempts SET result=?,url=?,error=? WHERE id=? AND pack_id=? AND result='started'",
                (result, url, error, attempt, pid),
            ).rowcount != 1:
                raise StateError("publish attempt is not active")
            db.execute(
                "UPDATE packs SET status=? WHERE id=?",
                (status or ("published" if result == "success" else "uncertain"), pid),
            )
            detail = self._publication_detail(db, pid, result, url, error)
            detail["attempt"] = attempt
            self.event(db, "publish_" + result, pid, now, detail, detail["approver"])

    def reconcile(self, pid, result, now, detail="", url=None):
        """Resolve an interrupted/uncertain publish and close its open attempt.

        Reconciliation and attempt finalization share a transaction, so a
        matching GitHub release cannot leave the original attempt dangling.
        """
        status = {"matching": "published", "absent": "retry_safe", "conflict": "conflict"}[result]
        attempt_result = {"matching": "success", "absent": "absent", "conflict": "conflict"}[result]
        with self.connect() as db:
            if db.execute(
                "UPDATE packs SET status=? WHERE id=? AND status IN ('publishing','uncertain')",
                (status, pid),
            ).rowcount != 1:
                raise StateError("only interrupted or uncertain publications can be reconciled")
            attempt = db.execute(
                "SELECT id FROM attempts WHERE pack_id=? AND result='started' ORDER BY id DESC LIMIT 1",
                (pid,),
            ).fetchone()
            if attempt:
                db.execute(
                    "UPDATE attempts SET result=?,url=?,error=? WHERE id=?",
                    (attempt_result, url, detail or None, attempt["id"]),
                )
            db.execute(
                "INSERT INTO reconciliations(pack_id,result,detail,created_at) VALUES(?,?,?,?)",
                (pid, result, detail, now),
            )
            publication = self._publication_detail(db, pid, attempt_result, url, detail or None)
            publication["reconciled"] = True
            publication["attempt"] = attempt["id"] if attempt else None
            # A recovered success is the final publication receipt, not merely
            # a state adjustment hidden in a reconciliation event.
            if result == "matching":
                self.event(db, "publish_success", pid, now, publication, publication["approver"])
            self.event(
                db,
                "reconcile",
                pid,
                now,
                {**publication, "reconciliation_result": result},
                publication["approver"],
            )

    def create_operation(self, oid, source, repository, now, scheduled_for=None, user_id=None):
        with self.connect() as db:
            db.execute("INSERT INTO operations(id,source,repository,status,started_at,scheduled_for,user_id) VALUES(?,?,?,'running',?,?,?)", (oid,source,repository,now,scheduled_for,user_id))
            if user_id:
                db.execute("INSERT INTO resource_owners(kind,resource_id,user_id) VALUES('operation',?,?) ON CONFLICT(kind,resource_id) DO NOTHING", (oid,user_id))
            self.event(db,"operation_started",oid,now,{"source":source,"repository":repository})

    def record_suppressed_operation(self, source, repository, now, scheduled_for=None, reason="duplicate_slot", user_id=None):
        """Durably audit an invocation suppressed before a new operation row.

        Scheduled slots deliberately have one canonical operation row. Duplicate
        requests are attached to that row as audit receipts, preserving both the
        uniqueness guarantee and evidence that every invocation was handled.
        """
        with self.connect() as db:
            if source == "scheduled" and scheduled_for:
                row = db.execute(
                    "SELECT id FROM operations WHERE source='scheduled' AND scheduled_for=? AND ((user_id=? ) OR (user_id IS NULL AND ? IS NULL))",
                    (scheduled_for, user_id, user_id),
                ).fetchone()
            else:
                row = None
            subject = row["id"] if row else f"suppressed:{source}:{scheduled_for or now}"
            self.event(db, "operation_suppressed", subject, now, {
                "source": source, "repository": repository,
                "scheduled_for": scheduled_for, "result": "suppressed", "reason": reason,
            })
            return subject

    def acquire_lease(self, owner, oid, now, expires):
        with self.connect() as db:
            db.execute("DELETE FROM scan_lease WHERE expires_at<=?", (now,))
            if self.dialect == "postgres":
                # Avoid a caught unique violation leaving the Postgres
                # transaction aborted.
                return db.execute(
                    "INSERT INTO scan_lease VALUES(1,?,?,?,?) ON CONFLICT (id) DO NOTHING",
                    (owner, oid, expires, now),
                ).rowcount == 1
            try:
                db.execute("INSERT INTO scan_lease VALUES(1,?,?,?,?)", (owner,oid,expires,now))
                return True
            except Exception as exc:
                if is_integrity_error(exc):
                    return False
                raise

    def release_lease(self, owner, oid):
        with self.connect() as db: db.execute("DELETE FROM scan_lease WHERE owner=? AND operation_id=?",(owner,oid))

    def renew_lease(self, owner, oid, now, expires):
        """Extend only the lease still owned by this operation."""
        with self.connect() as db:
            return db.execute(
                "UPDATE scan_lease SET heartbeat_at=?,expires_at=? WHERE owner=? AND operation_id=?",
                (now, expires, owner, oid),
            ).rowcount == 1

    def finish_operation(self, oid, result, now, scan_id=None, pack_id=None, error=None):
        with self.connect() as db:
            db.execute("UPDATE operations SET status='completed',result=?,scan_id=?,pack_id=?,error=?,finished_at=? WHERE id=?",(result,scan_id,pack_id,error,now,oid))
            self.event(db,"operation_finished",oid,now,{"result":result,"error":error})

    def operation(self, oid):
        with self.connect() as db:
            row=db.execute("SELECT * FROM operations WHERE id=?",(oid,)).fetchone()
            if not row: raise KeyError(oid)
            return dict(row)

    def operations(self):
        with self.connect() as db:
            rows=db.execute("SELECT * FROM operations ORDER BY started_at DESC,id DESC").fetchall()
            operations = [dict(row) for row in rows]
            for operation in operations:
                operation["activity"] = [record for record in self.audit() if record["subject_id"] == operation["id"]]
                if operation["pack_id"]:
                    pack = db.execute("SELECT status FROM packs WHERE id=?", (operation["pack_id"],)).fetchone()
                    operation["pack_status"] = pack["status"] if pack else None
            return operations

    def scheduled_users(self):
        """Return enabled schedules with their owner's connection metadata."""
        with self.connect() as db:
            rows = db.execute("""SELECT s.user_id,s.expression,s.enabled,s.updated_at,
                g.selected_repository,g.status FROM user_schedules s
                JOIN user_github_connections g ON g.user_id=s.user_id
                WHERE s.enabled=1 AND g.status='connected' AND g.selected_repository IS NOT NULL
                ORDER BY s.user_id""").fetchall()
        return [dict(row) for row in rows]

    def user_schedule(self, user_id):
        from .cron import next_run
        from datetime import datetime, timezone
        with self.connect() as db:
            row = db.execute("SELECT * FROM user_schedules WHERE user_id=?", (user_id,)).fetchone()
        data = dict(row) if row else {"user_id": user_id, "expression": "0 * * * *", "enabled": 0,
                                     "updated_at": "1970-01-01T00:00:00+00:00"}
        data["enabled"] = bool(data["enabled"]); data["timezone"] = "UTC"
        data["health"] = {"heartbeat_at": None, "last_run_at": None, "last_result": None, "last_error": None}
        data["next_run"] = next_run(data["expression"], datetime.now(timezone.utc)).isoformat() if data["enabled"] else None
        return data

    def update_user_schedule(self, user_id, expression, enabled, now):
        from .cron import parse
        parse(expression)
        with self.connect() as db:
            db.execute("""INSERT INTO user_schedules(user_id,expression,enabled,updated_at) VALUES(?,?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET expression=excluded.expression,enabled=excluded.enabled,updated_at=excluded.updated_at""",
                       (user_id, expression.strip(), int(enabled), now))
            self.event(db, "schedule", user_id, now, {"expression": expression.strip(), "enabled": bool(enabled)})
        return self.user_schedule(user_id)

    def scoped_audit(self, user_id):
        owned = {(kind, r["resource_id"]) for kind in ("pack", "scan", "operation")
                 for r in self._owned_rows(kind, user_id)}
        return [record for record in self.audit()
                if (record["kind"].split("_")[0], record["subject_id"]) in owned
                or ("pack", record["subject_id"]) in owned
                or record["subject_id"] == user_id]

    def schedule(self):
        from .cron import next_run
        from datetime import datetime, timezone
        with self.connect() as db:
            row=dict(db.execute("SELECT * FROM schedules WHERE id=1").fetchone())
            health=dict(db.execute("SELECT * FROM scheduler_state WHERE id=1").fetchone())
        row["enabled"]=bool(row["enabled"]); row["timezone"]="UTC"; row["health"]=health
        row["next_run"]=next_run(row["expression"],datetime.now(timezone.utc)).isoformat() if row["enabled"] else None
        return row

    def update_schedule(self, expression, enabled, now):
        from .cron import parse
        parse(expression)
        with self.connect() as db:
            db.execute("UPDATE schedules SET expression=?,enabled=?,updated_at=? WHERE id=1",(expression.strip(),int(enabled),now))
            self.event(db,"schedule","1",now,{"expression":expression.strip(),"enabled":bool(enabled)})
        return self.schedule()

    def pack_detail(self, pid):
        pack=self.pack(pid); pack["evidence"]=self.scan(pack["scan_id"]); pack["activity"]=self.pack_audit(pid)
        with self.connect() as db:
            decision=db.execute("SELECT * FROM decisions WHERE pack_id=?",(pid,)).fetchone()
            attempts=db.execute("SELECT * FROM attempts WHERE pack_id=? ORDER BY id",(pid,)).fetchall()
            operation=db.execute("SELECT id FROM operations WHERE pack_id=?",(pid,)).fetchone()
        pack["decision"]=dict(decision) if decision else None; pack["publication"]=[dict(x) for x in attempts]
        pack["operation_id"]=operation["id"] if operation else None
        return pack

    def audit(self):
        """Return chronological, JSON-native audit records.

        Important receipt fields are also promoted to the record's top level
        for straightforward operator/API inspection while retaining detail.
        """
        with self.connect() as db:
            records = []
            for row in db.execute("SELECT * FROM audit ORDER BY id"):
                record = dict(row)
                detail = json.loads(record["detail"])
                record["detail"] = detail
                for key, value in detail.items():
                    record.setdefault(key, value)
                records.append(record)
            return records
