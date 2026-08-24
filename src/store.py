"""SQLite persistence and compare-and-set governance transitions."""
import json, sqlite3
from typing import Any
from .models import PackStatus, primitive

class StateError(RuntimeError): pass
class Store:
    def __init__(self,path:str): self.path=path; self.init()
    def connect(self):
        db=sqlite3.connect(self.path); db.row_factory=sqlite3.Row; db.execute("PRAGMA foreign_keys=ON"); return db
    def init(self):
        with self.connect() as db: db.executescript('''
        CREATE TABLE IF NOT EXISTS scans(id TEXT PRIMARY KEY, data TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS verdicts(scan_id TEXT PRIMARY KEY REFERENCES scans(id), data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS packs(id TEXT PRIMARY KEY,scan_id TEXT UNIQUE REFERENCES scans(id),status TEXT NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS decisions(id INTEGER PRIMARY KEY,pack_id TEXT UNIQUE REFERENCES packs(id),decision TEXT NOT NULL,actor TEXT NOT NULL,reason TEXT,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY,pack_id TEXT REFERENCES packs(id),result TEXT NOT NULL,error TEXT,url TEXT,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS reconciliations(id INTEGER PRIMARY KEY,pack_id TEXT REFERENCES packs(id),result TEXT NOT NULL,detail TEXT,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,kind TEXT NOT NULL,subject_id TEXT NOT NULL,actor TEXT,detail TEXT NOT NULL,created_at TEXT NOT NULL);
        ''')
    def event(self,db,kind,subject,now,detail=None,actor=None): db.execute("INSERT INTO audit(kind,subject_id,actor,detail,created_at) VALUES(?,?,?,?,?)",(kind,subject,actor,json.dumps(detail or {}),now))
    def save_scan(self,scan,verdict,now):
        valid={x.id for x in (*scan.commits,*scan.pulls)}
        if not set(verdict.evidence_ids)<=valid: raise StateError("verdict cites evidence outside scan")
        with self.connect() as db:
            db.execute("INSERT INTO scans VALUES(?,?,?)",(scan.id,json.dumps(primitive(scan)),now)); db.execute("INSERT INTO verdicts VALUES(?,?)",(scan.id,json.dumps(primitive(verdict)))); self.event(db,"scan",scan.id,now,{"worthy":verdict.worthy})
    def save_pack(self,pack,now):
        with self.connect() as db: db.execute("INSERT INTO packs VALUES(?,?,?,?,?)",(pack.id,pack.scan_id,pack.status.value,json.dumps(primitive(pack)),now)); self.event(db,"pack",pack.id,now,{"version":pack.version})
    def pack(self,pid):
        with self.connect() as db:
            row=db.execute("SELECT * FROM packs WHERE id=?",(pid,)).fetchone()
            if not row: raise KeyError(pid)
            return {**json.loads(row["data"]),"status":row["status"]}
    def decide(self,pid,decision,actor,reason,now):
        actor=actor.strip(); reason=(reason or "").strip()
        if not actor or (decision=="rejected" and not reason): raise StateError("actor and rejection reason are required")
        target="approved" if decision=="approved" else "rejected"
        with self.connect() as db:
            if db.execute("UPDATE packs SET status=? WHERE id=? AND status='pending'",(target,pid)).rowcount!=1: raise StateError("pack is not pending")
            db.execute("INSERT INTO decisions(pack_id,decision,actor,reason,created_at) VALUES(?,?,?,?,?)",(pid,decision,actor,reason,now)); self.event(db,"decision",pid,now,{"decision":decision,"reason":reason},actor)
    def claim_publish(self,pid,now):
        with self.connect() as db:
            if db.execute("UPDATE packs SET status='publishing' WHERE id=? AND status IN ('approved','retry_safe')",(pid,)).rowcount!=1: raise StateError("human approval or retry-safe reconciliation required")
            cur=db.execute("INSERT INTO attempts(pack_id,result,created_at) VALUES(?,'started',?)",(pid,now)); self.event(db,"publish_started",pid,now,{"attempt":cur.lastrowid}); return cur.lastrowid
    def finish(self,pid,attempt,result,now,url=None,error=None,status=None):
        with self.connect() as db:
            db.execute("UPDATE attempts SET result=?,url=?,error=? WHERE id=? AND result='started'",(result,url,error,attempt)); db.execute("UPDATE packs SET status=? WHERE id=?",(status or ("published" if result=="success" else "uncertain"),pid)); self.event(db,"publish_"+result,pid,now,{"url":url,"error":error})
    def reconcile(self,pid,result,now,detail=""):
        status={"matching":"published","absent":"retry_safe","conflict":"conflict"}[result]
        with self.connect() as db: db.execute("UPDATE packs SET status=? WHERE id=? AND status='uncertain'",(status,pid)); db.execute("INSERT INTO reconciliations(pack_id,result,detail,created_at) VALUES(?,?,?,?)",(pid,result,detail,now)); self.event(db,"reconcile",pid,now,{"result":result,"detail":detail})
    def audit(self):
        with self.connect() as db: return [dict(x) for x in db.execute("SELECT * FROM audit ORDER BY id")]
