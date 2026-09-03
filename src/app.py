"""Release Manager application factory.

``create_app`` builds the same app for two topologies:

* standalone dev / tests — ``uvicorn src.app:app`` keeps an in-process lifespan
  scheduler (``enable_scheduler=True``, the default);
* Vercel serverless — ``api/index.py`` calls ``create_app(enable_scheduler=False)``
  so no always-on thread is launched; scheduled scans are driven by
  ``POST /scheduler/tick`` (Vercel Cron).
"""
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from .config import Settings
from .db import resolve_dialect
from .github_client import GitHubAccountClient, GitHubClient
from .github_oauth import OAuthService
from .routes import router
from .store import Store
from .operations import OperationRunner
from .scheduler import Scheduler


def _build_store(cfg: Settings) -> Store:
    dialect = resolve_dialect(cfg)
    return Store(cfg.database, dialect=dialect, database_url=cfg.database_url)


def create_app(settings: Settings | None = None, github=None, validate: bool = True,
               oauth_service_factory=None, account_client_factory=None,
               github_client_factory=None, enable_scheduler: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # A dependency-free app is useful for the isolated health probe test.
        if not validate and settings is None and not hasattr(app.state, "store"):
            yield
            return
        try:
            cfg = settings or Settings.from_env()
            if not hasattr(app.state, "store"):
                app.state.store = _build_store(cfg)
                app.state.settings = cfg
                # An explicitly injected GitHub double is a unit-test convenience and
                # bypasses OAuth credential resolution entirely.
                app.state.github = github
                if github is None:
                    oauth_factory = oauth_service_factory or OAuthService
                    app.state.oauth = oauth_factory(app.state.store, cfg.oauth_client_id, cfg.oauth_client_secret,
                                                    cfg.oauth_callback_url, cfg.session_secret, cfg.secure_cookie)
                    app.state.account_client_factory = account_client_factory or GitHubAccountClient
                    repository_factory = github_client_factory or GitHubClient

                    def provider(slug):
                        credentials = app.state.store.github_credentials()
                        if not credentials or credentials["status"] != "connected":
                            raise RuntimeError("GitHub connection requires reconnect")
                        owner, repo = slug.split("/", 1)
                        return repository_factory(owner, repo, credentials["access_token"])

                    app.state.github_provider = provider
        except ValueError as exc:
            # Configuration names and callback-shape errors are safe to report;
            # secret values are never included in these messages.
            app.state.startup_failure = {"kind": "configuration", "detail": str(exc)}
            yield
            return
        except Exception:
            # Do not expose a DSN, credentials, or driver traceback to callers.
            app.state.startup_failure = {"kind": "database", "detail": "database initialization failed"}
            yield
            return
        if enable_scheduler:
            scheduler = Scheduler(
                app.state.store,
                OperationRunner(app.state.store, app.state.github,
                                client_provider=getattr(app.state, "github_provider", None)),
                interval=cfg.scheduler_interval,
            )
            app.state.scheduler = scheduler
            await scheduler.start()
            try:
                yield
            finally:
                await scheduler.stop()
        else:
            yield

    application = FastAPI(title="release-manager", lifespan=lifespan)
    application.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
    application.include_router(router)

    @application.get("/health")
    def health():
        failure = getattr(application.state, "startup_failure", None)
        if failure:
            return JSONResponse({"status": "unavailable", **failure}, status_code=503)
        return {"status": "ok"}

    # Explicit injected dependencies may be used without lifespan in unit tests.
    if settings and github:
        application.state.store = _build_store(settings)
        application.state.settings = settings
        application.state.github = github
    return application


# Import remains safe for health tooling; production validation occurs at startup.
app = create_app()
