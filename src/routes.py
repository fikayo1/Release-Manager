"""Operator JSON API and progressively enhanced server-rendered review UI."""
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from .models import primitive
from .templating import Templates
from .phases import approve, draft, publish, reconcile, reject, scan
from .store import StateError
from .cron import CronError
from .operations import OperationRunner
from .github_client import GitHubAccountClient, GitHubRevokedError
from .github_oauth import OAuthError

router = APIRouter()
templates = Templates()


def now():
    return datetime.now(timezone.utc).isoformat()


def deps(request: Request):
    return request.app.state.store, request.app.state.github


class Decision(BaseModel):
    actor: str
    reason: str

class ScheduleUpdate(BaseModel):
    expression: str
    enabled: bool

class RepositorySelection(BaseModel):
    full_name: str


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
            "changelog lines": len(pack.get("body", "").splitlines()),
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


@router.get("/auth/github")
def github_start(request: Request):
    oauth = getattr(request.app.state, "oauth", None)
    if not oauth: raise HTTPException(503, "GitHub OAuth is not configured")
    session = oauth.read_session(request.cookies.get(oauth.cookie_name))
    url, cookie = oauth.begin(session)
    response = RedirectResponse(url, 302)
    response.set_cookie(oauth.cookie_name, cookie, httponly=True, secure=oauth.secure_cookie,
                        samesite="lax", path="/", max_age=86400)
    return response

@router.get("/auth/github/callback")
def github_callback(request: Request, state: str = "", code: str = "", error: str = ""):
    oauth = getattr(request.app.state, "oauth", None)
    settings = getattr(request.app.state, "settings", None)
    if not oauth or not settings: raise HTTPException(503, "GitHub OAuth is not configured")
    status = "connected"
    try:
        oauth.consume(state, request.cookies.get(oauth.cookie_name))
        if error:
            raise OAuthError("GitHub authorization was denied")
        token, refresh, expires = oauth.exchange(code)
        account = GitHubAccountClient(token).user()
        expires_at = None
        if expires:
            from datetime import timedelta
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=int(expires))).isoformat()
        request.app.state.store.save_github_connection(account["login"], account.get("id"), token,
                                                        refresh, expires_at, now())
    except OAuthError as exc:
        status = "denied" if error else "invalid_state"
    except Exception:
        status = "exchange_failed"
    destination = settings.web_url.rstrip("/") + "/settings/github?" + urlencode({"github": status})
    return RedirectResponse(destination, 303)

@router.get("/api/github")
def github_settings(request: Request):
    store = request.app.state.store
    connection = store.github_connection()
    result = {"status": connection["status"] if connection else "disconnected",
              "account": connection["login"] if connection else None,
              "selected_repository": connection["selected_repository"] if connection else None,
              "repositories": [], "authorize_url": "/auth/github"}
    if connection and connection["status"] == "connected":
        credentials = store.github_credentials()
        try:
            result["repositories"] = GitHubAccountClient(credentials["access_token"]).repositories()
        except GitHubRevokedError:
            store.mark_github_revoked(now()); result["status"] = "revoked"
    return result

@router.put("/api/github/repository")
def choose_repository(data: RepositorySelection, request: Request):
    if data.full_name.count("/") != 1 or any(not p for p in data.full_name.split("/")):
        raise HTTPException(422, "Select a valid authorized repository")
    store = request.app.state.store; credentials = store.github_credentials()
    if not credentials or credentials["status"] != "connected":
        raise HTTPException(409, "Reconnect GitHub before selecting a repository")
    try:
        allowed = {r["full_name"] for r in GitHubAccountClient(credentials["access_token"]).repositories()}
    except GitHubRevokedError:
        store.mark_github_revoked(now()); raise HTTPException(409, "Reconnect GitHub before selecting a repository")
    if data.full_name not in allowed:
        raise HTTPException(422, "Repository is not authorized or accessible")
    store.select_repository(data.full_name, now())
    return {"selected_repository": data.full_name}

@router.post("/api/scans", status_code=201)
def start(request: Request):
    store, gh = deps(request)
    return OperationRunner(store, gh, client_provider=getattr(request.app.state,"github_provider",None)).run("manual")

@router.get("/api/operations")
def list_operations(request: Request):
    return deps(request)[0].operations()

@router.get("/api/operations/{operation_id}")
def get_operation(operation_id: str, request: Request):
    try: return deps(request)[0].operation(operation_id)
    except KeyError: raise HTTPException(404,"operation not found")

@router.get("/api/schedule")
def get_schedule(request: Request): return deps(request)[0].schedule()

@router.put("/api/schedule")
def put_schedule(data: ScheduleUpdate, request: Request):
    try: return deps(request)[0].update_schedule(data.expression,data.enabled,now())
    except CronError as exc: raise HTTPException(422,str(exc))

@router.get("/api/releases")
def releases(request: Request): return [_pack_view(deps(request)[0],p) for p in deps(request)[0].packs()]

@router.get("/api/releases/{pack_id}")
def release_detail(pack_id: str, request: Request):
    try: return deps(request)[0].pack_detail(pack_id)
    except KeyError: raise HTTPException(404,"pack not found")


@router.get("/api/packs")
def list_packs(request: Request):
    """Return the complete pack collection in dashboard display order.

    The review page and this endpoint intentionally share the same view
    builder so operators and API consumers see a one-to-one collection with
    identical status, activity, and published metrics.
    """
    store, _ = deps(request)
    return [_pack_view(store, pack) for pack in store.packs()]


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
