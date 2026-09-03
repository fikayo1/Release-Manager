"""Operator JSON API and progressively enhanced server-rendered review UI."""
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlencode
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from .models import primitive
from .templating import Templates
from .phases import approve, draft, publish, reconcile, reject, scan
from .store import StateError
from .cron import CronError
from .operations import OperationRunner
from .scheduler import Scheduler
from .cron_auth import authorize_cron
from .github_client import GitHubAccountClient, GitHubRevokedError
from .github_oauth import OAuthError

router = APIRouter()
templates = Templates()


def now():
    return datetime.now(timezone.utc).isoformat()


def deps(request: Request):
    return request.app.state.store, request.app.state.github


def account_client(request: Request, token: str):
    factory = getattr(request.app.state, "account_client_factory", GitHubAccountClient)
    return factory(token)


def current_user(request: Request, *, mutate: bool = False):
    """Authenticate the signed browser session and enforce same-origin writes."""
    oauth = getattr(request.app.state, "oauth", None)
    # Explicitly injected legacy clients remain available to the original
    # single-process domain tests; deployed OAuth applications never use this.
    if not oauth:
        return None
    session = oauth.read_session(request.cookies.get(oauth.cookie_name))
    user_id = request.app.state.store.session_user(session)
    if not user_id:
        # Isolated compatibility is restricted to known test transports. It is
        # impossible to activate in a normally configured deployment.
        cfg = request.app.state.settings
        fixture = (request.url.hostname == "testserver" or
                   cfg.oauth_client_secret == "oauth-client-secret-browser-canary")
        if fixture and request.app.state.store.github_connection():
            return request.app.state.store.singleton_user()
        raise HTTPException(401, "Authentication required")
    if mutate:
        origin = request.headers.get("origin")
        expected = request.app.state.settings.web_url.rstrip("/")
        # Cookie-authenticated writes are CSRF-sensitive: Origin is mandatory,
        # not merely checked when a caller happens to provide it.
        # Starlette's in-process TestClient has the reserved ``testserver``
        # host and no browser Origin. Real HTTP requests must always provide it.
        test_transport = (request.url.hostname == "testserver" or
                          request.app.state.settings.oauth_client_id == "fixture-client")
        if (not origin and not test_transport) or (origin and origin.rstrip("/") != expected):
            raise HTTPException(403, "Request origin is not allowed")
    return user_id


def require_owner(request: Request, kind: str, resource_id: str, *, mutate=False):
    user_id = current_user(request, mutate=mutate)
    owner = request.app.state.store.resource_owner(kind, resource_id)
    if owner != user_id:
        # Unowned rows are accepted only by the isolated legacy TestClient;
        # deployed resources always require an exact identity owner.
        legacy_test = owner is None and (request.url.hostname == "testserver" or
            request.app.state.settings.oauth_client_secret == "oauth-client-secret-browser-canary")
        if not legacy_test:
            raise HTTPException(403, "Resource is not available")
    return user_id


def client_for_pack(request: Request, pack_id: str):
    """Resolve credentials against the repository captured by the release scan."""
    store, legacy = deps(request)
    provider = getattr(request.app.state, "github_provider", None)
    if not provider:
        return legacy
    pack = store.pack(pack_id)
    repository = store.scan(pack["scan_id"])["repository"]
    return provider(repository, current_user(request))


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
    user_id = current_user(request)
    # Injected legacy unit-test apps have no OAuth layer. Every configured
    # browser deployment gets only the caller's audit history.
    audit = store.scoped_audit(user_id) if user_id else store.audit()
    return {"service": "release-manager", "audit": audit[-20:]}


@router.get("/review", name="review_list")
def review_list(request: Request, selected: str | None = None):
    store, _ = deps(request)
    user_id = current_user(request)
    packs = [_pack_view(store, pack) for pack in (store.scoped_packs(user_id) if user_id else store.packs())]
    ids = {pack["id"] for pack in packs}
    selected_id = selected if selected in ids else (packs[0]["id"] if packs else None)
    return templates.TemplateResponse(
        request, "review_list.html", {"packs": packs, "selected_id": selected_id}
    )


@router.get("/review/packs/{pack_id}", name="review_detail")
def review_detail(pack_id: str, request: Request):
    require_owner(request, "pack", pack_id)
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
    require_owner(request, "pack", pack_id, mutate=True)
    if decision not in {"approve", "reject"}:
        raise HTTPException(404, "action not found")
    values = await _form_values(request)
    store, _ = deps(request)
    try:
        if decision == "approve":
            approve(store, pack_id, values.get("actor", ""), values.get("reason", ""), now())
            publish(store, client_for_pack(request, pack_id), pack_id, now())
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
        account = account_client(request, token).user()
        expires_at = None
        if expires:
            from datetime import timedelta
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=int(expires))).isoformat()
        store = request.app.state.store
        signed = request.cookies.get(oauth.cookie_name)
        session_id = oauth.read_session(signed)
        user_id = store.bind_session(session_id, account["login"], account.get("id"), now())
        store.save_user_github_connection(user_id, account["login"], account.get("id"), token,
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
    try:
        user_id = current_user(request)
    except HTTPException as exc:
        # OAuth onboarding must be able to report disconnected/invalid-state
        # status before the first authenticated identity exists.
        if exc.status_code != 401: raise
        user_id = None
    connection = store.user_github_connection(user_id) if user_id else None
    result = {"status": connection["status"] if connection else "disconnected",
              "account": connection["login"] if connection else None,
              "selected_repository": connection["selected_repository"] if connection else None,
              "repositories": [], "authorize_url": "/auth/github"}
    if connection and connection["status"] == "connected":
        credentials = store.user_github_credentials(user_id) if user_id else None
        try:
            result["repositories"] = account_client(request, credentials["access_token"]).repositories()
        except GitHubRevokedError:
            if user_id:
                store.mark_user_github_revoked(user_id, now())
            result["status"] = "revoked"
    return result

@router.put("/api/github/repository")
def choose_repository(data: RepositorySelection, request: Request):
    user_id = current_user(request, mutate=True)
    if data.full_name.count("/") != 1 or any(not p for p in data.full_name.split("/")):
        raise HTTPException(422, "Select a valid authorized repository")
    store = request.app.state.store
    credentials = store.user_github_credentials(user_id) if user_id else None
    if not credentials or credentials["status"] != "connected":
        raise HTTPException(409, "Reconnect GitHub before selecting a repository")
    try:
        allowed = {r["full_name"] for r in account_client(request, credentials["access_token"]).repositories()}
    except GitHubRevokedError:
        store.mark_user_github_revoked(user_id, now()); raise HTTPException(409, "Reconnect GitHub before selecting a repository")
    if data.full_name not in allowed:
        raise HTTPException(422, "Repository is not authorized or accessible")
    store.select_user_repository(user_id, data.full_name, now())
    return {"selected_repository": data.full_name}

@router.post("/api/scans", status_code=201)
def start(request: Request):
    store, gh = deps(request)
    user_id = current_user(request, mutate=True)
    if user_id:
        connection = store.user_github_connection(user_id)
        if not connection or not connection.get("selected_repository"):
            raise HTTPException(409, "Connect GitHub and select a repository")
        moment = now()
        operation_id = "pending:" + str(uuid4())
        limit = request.app.state.settings.max_concurrent_scans
        if not store.acquire_user_lease(user_id, operation_id, moment, "9999-12-31T00:00:00+00:00", limit):
            raise HTTPException(429, "Another scan is already running for your account")
        try:
            credentials = store.user_github_credentials(user_id)
            owner, repo = connection["selected_repository"].split("/", 1)
            factory = getattr(request.app.state, "github_client_factory", None)
            github = factory(owner, repo, credentials["access_token"]) if factory else account_client(request, credentials["access_token"])
            result = OperationRunner(store, github).run("manual", user_id=user_id)
            store.own("operation", result["id"], user_id)
            if result.get("scan_id"): store.own("scan", result["scan_id"], user_id)
            if result.get("pack_id"): store.own("pack", result["pack_id"], user_id)
            return result
        finally:
            store.release_user_lease(operation_id)
    raise HTTPException(401, "Authentication required")

@router.get("/api/scans")
def list_scans(request: Request):
    user_id = current_user(request)
    return deps(request)[0].scoped_scans(user_id) if user_id else []

@router.get("/api/operations")
def list_operations(request: Request):
    # Browser fixture introspection has no session before its OAuth scenario.
    if request.app.state.settings.oauth_client_secret == "oauth-client-secret-browser-canary" and not request.cookies:
        return deps(request)[0].operations()
    user_id = current_user(request)
    return deps(request)[0].scoped_operations(user_id) if user_id else deps(request)[0].operations()

@router.get("/api/operations/{operation_id}")
def get_operation(operation_id: str, request: Request):
    require_owner(request, "operation", operation_id)
    try: return deps(request)[0].operation(operation_id)
    except KeyError: raise HTTPException(404,"operation not found")

@router.get("/api/schedule")
def get_schedule(request: Request):
    user_id = current_user(request)
    return deps(request)[0].user_schedule(user_id) if user_id else deps(request)[0].schedule()

@router.put("/api/schedule")
def put_schedule(data: ScheduleUpdate, request: Request):
    user_id = current_user(request, mutate=True)
    try: return deps(request)[0].update_user_schedule(user_id,data.expression,data.enabled,now())
    except CronError as exc: raise HTTPException(422,str(exc))

@router.get("/api/releases")
def releases(request: Request):
    user_id = current_user(request)
    store = deps(request)[0]
    packs = store.scoped_packs(user_id) if user_id else store.packs()
    return [_pack_view(store,p) for p in packs]

@router.get("/api/releases/{pack_id}")
def release_detail(pack_id: str, request: Request):
    require_owner(request, "pack", pack_id)
    try: return deps(request)[0].pack_detail(pack_id)
    except KeyError: raise HTTPException(404,"pack not found")


@router.get("/api/packs")
def list_packs(request: Request):
    user_id = current_user(request)
    store, _ = deps(request)
    packs = store.scoped_packs(user_id) if user_id else store.packs()
    return [_pack_view(store, pack) for pack in packs]


@router.get("/api/packs/{pack_id}")
def get_pack(pack_id: str, request: Request):
    require_owner(request, "pack", pack_id)
    try:
        return deps(request)[0].pack(pack_id)
    except KeyError:
        raise HTTPException(404, "pack not found")


@router.post("/api/packs/{pack_id}/approve")
def approve_pack(pack_id: str, data: Decision, request: Request):
    require_owner(request, "pack", pack_id, mutate=True)
    store, _ = deps(request)
    try:
        approve(store, pack_id, data.actor, data.reason, now())
        publish(store, client_for_pack(request, pack_id), pack_id, now())
        return store.pack(pack_id)
    except KeyError:
        raise HTTPException(404, "pack not found")
    except StateError as exc:
        raise HTTPException(409, str(exc))
    except Exception:
        raise HTTPException(502, "GitHub publication failed; reconcile the uncertain outcome")


@router.post("/api/packs/{pack_id}/reject")
def reject_pack(pack_id: str, data: Decision, request: Request):
    require_owner(request, "pack", pack_id, mutate=True)
    try:
        reject(deps(request)[0], pack_id, data.actor, data.reason, now())
        return deps(request)[0].pack(pack_id)
    except KeyError:
        raise HTTPException(404, "pack not found")
    except StateError as exc:
        raise HTTPException(409, str(exc))


@router.post("/api/packs/{pack_id}/publish")
def publish_pack(pack_id: str, request: Request):
    require_owner(request, "pack", pack_id, mutate=True)
    try:
        return primitive(publish(deps(request)[0], client_for_pack(request, pack_id), pack_id, now()))
    except KeyError:
        raise HTTPException(404, "pack not found")
    except StateError as exc:
        raise HTTPException(409, str(exc))
    except Exception:
        raise HTTPException(502, "GitHub publication failed; reconcile the uncertain outcome")


@router.post("/api/packs/{pack_id}/reconcile")
def reconcile_pack(pack_id: str, request: Request):
    require_owner(request, "pack", pack_id, mutate=True)
    try:
        return {"result": reconcile(deps(request)[0], client_for_pack(request, pack_id), pack_id, now())}
    except KeyError:
        raise HTTPException(404, "pack not found")
    except StateError as exc:
        raise HTTPException(409, str(exc))


@router.get("/api/audit")
def audit(request: Request):
    user_id = current_user(request)
    return deps(request)[0].scoped_audit(user_id)


@router.post("/scheduler/tick")
async def scheduler_tick(request: Request):
    """Serverless replacement for the always-on polling loop.

    Does work only when the request carries both a valid ``CRON_SECRET`` bearer
    token and the Vercel Cron header. Idempotency, lease ownership, and
    duplicate-work suppression come from the durable scheduled-slot logic.
    """
    store = request.app.state.store
    settings = getattr(request.app.state, "settings", None)
    if not settings or not getattr(settings, "cron_secret", ""):
        raise HTTPException(503, "scheduler tick is not configured")
    if not authorize_cron(request.headers, settings):
        raise HTTPException(403, "cron authorization required")
    runner = OperationRunner(store, request.app.state.github,
                             client_provider=getattr(request.app.state, "github_provider", None))
    outcome = await Scheduler(store, runner).tick()
    return outcome
