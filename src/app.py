"""Release Manager application factory."""
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .config import Settings
from .github_client import GitHubClient
from .routes import router
from .store import Store

def create_app(settings:Settings|None=None, github=None, validate:bool=True) -> FastAPI:
    configured=settings is not None
    @asynccontextmanager
    async def lifespan(app:FastAPI):
        if validate:
            cfg=settings or Settings.from_env()
            app.state.store=Store(cfg.database)
            app.state.github=github or GitHubClient(cfg.owner,cfg.repo,cfg.token)
            app.state.github.repository()  # fail loud before serving
        yield
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
