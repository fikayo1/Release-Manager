"""Release Manager application factory."""
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .config import Settings
from .github_client import GitHubClient
from .routes import router
from .store import Store
from .operations import OperationRunner
from .scheduler import Scheduler

def create_app(settings:Settings|None=None, github=None, validate:bool=True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app:FastAPI):
        # A dependency-free app is useful for the isolated health probe test;
        # every configured/runtime app owns a scheduler for its full lifespan.
        if not validate and settings is None and not hasattr(app.state, "store"):
            yield
            return
        cfg=settings or Settings.from_env()
        if not hasattr(app.state, "store"):
            app.state.store=Store(cfg.database)
            app.state.github=github or GitHubClient(cfg.owner,cfg.repo,cfg.token)
        if validate:
            app.state.github.repository()  # fail loud before serving
        scheduler=Scheduler(
            app.state.store,
            OperationRunner(app.state.store, app.state.github),
            interval=cfg.scheduler_interval,
        )
        app.state.scheduler=scheduler
        await scheduler.start()
        try:
            yield
        finally:
            await scheduler.stop()
    application=FastAPI(title="release-manager",lifespan=lifespan)
    application.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
    application.include_router(router)
    @application.get("/health")
    def health(): return {"status":"ok"}
    # Explicit injected dependencies may be used without lifespan in unit tests.
    if settings and github:
        application.state.store=Store(settings.database); application.state.github=github
    return application

# Import remains safe for health tooling; production validation occurs at startup.
app=create_app()
