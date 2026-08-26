"""Operator JSON API and progressively enhanced server-rendered review UI."""
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .models import primitive
from .phases import approve, draft, publish, reconcile, reject, scan
from .store import StateError

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def now():
    return datetime.now(timezone.utc).isoformat()


def deps(request: Request):
    return request.app.state.store, request.app.state.github


class Decision(BaseModel):
    actor: str
    reason: str


def _detail_context(request, pack_id, error=None, values=None):
    store, _ = deps(request)
    pack = store.pack(pack_id)
    try:
        evidence = store.scan(pack["scan_id"])
    except (KeyError, TypeError):
        evidence = {"commits": [], "pulls": []}
    return {
        "request": request,
        "pack": pack,
        "evidence": evidence,
        "activity": store.pack_audit(pack_id),
        "error": error,
        "values": values or {},
    }


def _pack_view(store, pack):
    activity = store.pack_audit(pack["id"])
    view = {**pack, "activity": activity}
    if pack["status"] == "published":
        try:
            snapshot = store.scan(pack["scan_id"])
        except (KeyError, TypeError):
            snapshot = {}
        view["metrics"] = {
            "commits": len(snapshot.get("commits", [])),
            "pull requests": len(snapshot.get("pulls", [])),
            "changelog items": sum(1 for line in pack.get("body", "").splitlines() if line.strip().startswith("-")),
        }
    return view


@router.get("/")
def index(request: Request):
    """Retain the original JSON service discovery response."""
    store, _ = deps(request)
    return {"service": "release-manager", "audit": store.audit()[-20:]}


@router.get("/review", name="review_list")
def review_list(request: Request, selected: str | None = None):
    store, _ = deps(request)
    packs = [_pack_view(store, pack) for pack in store.packs()]
    ids = {pack["id"] for pack in packs}
    selected_id = selected if selected in ids else (packs[0]["id"] if packs else None)
    return templates.TemplateResponse(
        request, "review_list.html", {"packs": packs, "selected_id": selected_id}
    )


@router.get("/review/packs/{pack_id}", name="review_detail")
def review_detail(pack_id: str, request: Request):
    try:
        context = _detail_context(request, pack_id)
    except KeyError:
        raise HTTPException(404, "pack not found")
    return templates.TemplateResponse(request, "pack_detail.html", context)


async def _form_values(request):
    # These forms use application/x-www-form-urlencoded; parsing directly keeps
    # the no-JavaScript flow free of a multipart upload dependency.
    fields = parse_qs((await request.body()).decode("utf-8"), keep_blank_values=True)
    return {key: values[-1] for key, values in fields.items()}


@router.post("/review/packs/{pack_id}/{decision}")
async def review_decision(pack_id: str, decision: str, request: Request):
    if decision not in {"approve", "reject"}:
        raise HTTPException(404, "action not found")
    values = await _form_values(request)
    store, github = deps(request)
    try:
        if decision == "approve":
            approve(store, pack_id, values.get("actor", ""), values.get("reason", ""), now())
            publish(store, github, pack_id, now())
        else:
            reject(store, pack_id, values.get("actor", ""), values.get("reason", ""), now())
    except KeyError:
        raise HTTPException(404, "pack not found")
    except StateError as exc:
        context = _detail_context(request, pack_id, str(exc), values)
        return templates.TemplateResponse(request, "pack_detail.html", context, status_code=409)
    except Exception:
        context = _detail_context(
            request,
            pack_id,
            "GitHub publication failed; the outcome is uncertain. Reconcile before retrying.",
            values,
        )
        return templates.TemplateResponse(request, "pack_detail.html", context, status_code=502)
    return RedirectResponse(request.url_for("review_detail", pack_id=pack_id), status_code=303)


@router.post("/api/scans", status_code=201)
def start(request: Request):
    store, gh = deps(request)
    snapshot, verdict = scan(store, gh, now())
    pack = draft(store, snapshot, verdict, now())
    return {"scan": primitive(snapshot), "verdict": primitive(verdict), "pack": primitive(pack) if pack else None}


@router.get("/api/packs/{pack_id}")
def get_pack(pack_id: str, request: Request):
    try:
        return deps(request)[0].pack(pack_id)
    except KeyError:
        raise HTTPException(404, "pack not found")


@router.post("/api/packs/{pack_id}/approve")
def approve_pack(pack_id: str, data: Decision, request: Request):
    store, github = deps(request)
    try:
        approve(store, pack_id, data.actor, data.reason, now())
        publish(store, github, pack_id, now())
        return store.pack(pack_id)
    except KeyError:
        raise HTTPException(404, "pack not found")
    except StateError as exc:
        raise HTTPException(409, str(exc))
    except Exception:
        raise HTTPException(502, "GitHub publication failed; reconcile the uncertain outcome")


@router.post("/api/packs/{pack_id}/reject")
def reject_pack(pack_id: str, data: Decision, request: Request):
    try:
        reject(deps(request)[0], pack_id, data.actor, data.reason, now())
        return deps(request)[0].pack(pack_id)
    except KeyError:
        raise HTTPException(404, "pack not found")
    except StateError as exc:
        raise HTTPException(409, str(exc))


@router.post("/api/packs/{pack_id}/publish")
def publish_pack(pack_id: str, request: Request):
    try:
        return primitive(publish(*deps(request), pack_id, now()))
    except KeyError:
        raise HTTPException(404, "pack not found")
    except StateError as exc:
        raise HTTPException(409, str(exc))
    except Exception:
        raise HTTPException(502, "GitHub publication failed; reconcile the uncertain outcome")


@router.post("/api/packs/{pack_id}/reconcile")
def reconcile_pack(pack_id: str, request: Request):
    try:
        return {"result": reconcile(*deps(request), pack_id, now())}
    except KeyError:
        raise HTTPException(404, "pack not found")
    except StateError as exc:
        raise HTTPException(409, str(exc))


@router.get("/api/audit")
def audit(request: Request):
    return deps(request)[0].audit()
