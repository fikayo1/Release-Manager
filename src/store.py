"""SQLite persistence and compare-and-set governance transitions."""
import json
import sqlite3
from typing import Any

from .models import primitive


class StateError(RuntimeError):
    pass


class Store:
    def __init__(self, path: str):
        self.path = path
        self.init()

    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def init(self):
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS scans(id TEXT PRIMARY KEY, data TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS verdicts(scan_id TEXT PRIMARY KEY REFERENCES scans(id), data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS packs(id TEXT PRIMARY KEY,scan_id TEXT UNIQUE REFERENCES scans(id),status TEXT NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS decisions(id INTEGER PRIMARY KEY,pack_id TEXT UNIQUE REFERENCES packs(id),decision TEXT NOT NULL,actor TEXT NOT NULL,reason TEXT,created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY,pack_id TEXT REFERENCES packs(id),result TEXT NOT NULL,error TEXT,url TEXT,created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS reconciliations(id INTEGER PRIMARY KEY,pack_id TEXT REFERENCES packs(id),result TEXT NOT NULL,detail TEXT,created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,kind TEXT NOT NULL,subject_id TEXT NOT NULL,actor TEXT,detail TEXT NOT NULL,created_at TEXT NOT NULL);
                """
            )

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
