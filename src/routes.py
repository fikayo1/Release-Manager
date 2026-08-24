"""JSON operator API. No endpoint accepts repository credentials or autonomy."""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from .models import primitive
from .phases import approve,draft,publish,reconcile,reject,scan
from .store import StateError

router=APIRouter()
def now(): return datetime.now(timezone.utc).isoformat()
def deps(request:Request): return request.app.state.store,request.app.state.github
class Decision(BaseModel): actor:str; reason:str|None=None

@router.get("/")
def index(request:Request):
    store,_=deps(request); return {"service":"release-manager","audit":store.audit()[-20:]}
@router.post("/api/scans",status_code=201)
def start(request:Request):
    store,gh=deps(request); snapshot,verdict=scan(store,gh,now()); pack=draft(store,snapshot,verdict,now())
    return {"scan":primitive(snapshot),"verdict":primitive(verdict),"pack":primitive(pack) if pack else None}
@router.get("/api/packs/{pack_id}")
def get_pack(pack_id:str,request:Request):
    try: return deps(request)[0].pack(pack_id)
    except KeyError: raise HTTPException(404,"pack not found")
@router.post("/api/packs/{pack_id}/approve")
def approve_pack(pack_id:str,data:Decision,request:Request):
    try: approve(deps(request)[0],pack_id,data.actor,now()); return deps(request)[0].pack(pack_id)
    except StateError as exc: raise HTTPException(409,str(exc))
@router.post("/api/packs/{pack_id}/reject")
def reject_pack(pack_id:str,data:Decision,request:Request):
    try: reject(deps(request)[0],pack_id,data.actor,data.reason,now()); return deps(request)[0].pack(pack_id)
    except StateError as exc: raise HTTPException(409,str(exc))
@router.post("/api/packs/{pack_id}/publish")
def publish_pack(pack_id:str,request:Request):
    try: return primitive(publish(*deps(request),pack_id,now()))
    except StateError as exc: raise HTTPException(409,str(exc))
@router.post("/api/packs/{pack_id}/reconcile")
def reconcile_pack(pack_id:str,request:Request):
    try: return {"result":reconcile(*deps(request),pack_id,now())}
    except StateError as exc: raise HTTPException(409,str(exc))
@router.get("/api/audit")
def audit(request:Request): return deps(request)[0].audit()
