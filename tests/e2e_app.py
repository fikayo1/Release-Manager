"""Deterministic OAuth + multi-repository GitHub fixture for browser tests.

Started only by Playwright. All GitHub behaviour comes from ``tests.fakes`` so
the browser suite and the backend suites share one set of doubles and one token
canary. The operator database is a real on-disk SQLite file; it is reset on
startup unless ``E2E_KEEP_DB=1`` (set by the restart helper so a respawned
process keeps the data the previous process wrote).
"""
import asyncio
from functools import partial
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from src.app import create_app
from src.config import Settings
from src.operations import OperationRunner
from src.scheduler import Scheduler
from tests.fakes import (
    JOURNAL,
    PUBLISHED,
    REPO_A,
    FakeAccountGitHub,
    FakeOAuth,
    FakeRepositoryGitHub,
    seed_pack,
)

PORT = os.getenv("E2E_API_PORT", "18000")
API_ORIGIN = f"http://127.0.0.1:{PORT}"
WEB = os.getenv("E2E_WEB_URL", "http://127.0.0.1:13000")
CALLBACK = f"{WEB}/auth/github/callback"

DB = os.getenv("E2E_DB", "/tmp/release-manager-e2e.db")
if os.getenv("E2E_KEEP_DB") != "1":
    Path(DB).unlink(missing_ok=True)

# A high interval keeps the lifespan scheduler from firing scans on its own:
# scheduled scans in the acceptance suite are driven deterministically through
# ``/test/scheduler/tick`` below.
app = create_app(
    Settings(database=DB, scheduler_interval=3600, oauth_client_id="fixture-client",
             oauth_client_secret="fixture-secret", oauth_callback_url=CALLBACK,
             session_secret="deterministic-browser-session-secret", web_url=WEB,
             cron_secret=os.getenv("CRON_SECRET", "cron-fixed-browser-test-secret")),
    validate=False, enable_scheduler=False,
    oauth_service_factory=partial(FakeOAuth, authorize_origin=API_ORIGIN),
    account_client_factory=FakeAccountGitHub, github_client_factory=FakeRepositoryGitHub,
)


@app.get("/test/github/authorize")
def authorize(request: Request, state: str, error: str = ""):
    query = {"state": state}
    query["error" if error else "code"] = "access_denied" if error else "accepted"
    return RedirectResponse(CALLBACK + "?" + urlencode(query), 302)


@app.get("/test/publications")
def publications():
    return PUBLISHED


@app.get("/test/github/journal")
def github_journal():
    return {"entries": JOURNAL.entries(), "repositories": JOURNAL.repositories()}


@app.post("/test/github/journal/reset")
def github_journal_reset():
    JOURNAL.reset()
    return {"ok": True}


class SeedRequest(BaseModel):
    pack_id: str
    repository: str = REPO_A
    status: str = "pending"
    tag: str | None = None


@app.post("/test/seed")
def seed(request: Request, body: SeedRequest):
    seed_pack(request.app.state.store, body.pack_id, body.repository, body.status, tag=body.tag)
    return {"pack_id": body.pack_id, "repository": body.repository, "status": body.status}


@app.post("/test/scheduler/tick")
async def scheduler_tick(request: Request):
    """Drive the real ``Scheduler.tick`` once against a deterministically due slot."""
    store = request.app.state.store
    fixed = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    runner = OperationRunner(store, None, client_provider=request.app.state.github_provider, clock=lambda: fixed)
    await Scheduler(store, runner, clock=lambda: fixed).tick()
    return {"slot": fixed.replace(second=0, microsecond=0).isoformat()}
