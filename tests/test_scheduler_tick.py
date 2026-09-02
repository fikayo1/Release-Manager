"""C3-C5: the serverless scheduler-tick endpoint.

* C3 - work happens only with both a valid CRON_SECRET bearer and the Vercel
  Cron header; rejected requests trigger no scan/publish.
* C4 - authorized ticks are idempotent; a concurrent duplicate is suppressed,
  not errored; a post-completion tick is a no-op.
* C5 - the serverless-shaped app launches no background scheduler.
"""
import concurrent.futures
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from src.app import create_app
from src.operations import OperationRunner
from src.scheduler import Scheduler
from tests.fakes import JOURNAL, FakeAccountGitHub, FakeOAuth, FakeRepositoryGitHub, REPO_A
from tests.test_oauth_flow import complete_oauth
from tests.test_review_ui import oauth_settings

SECRET = "cron-fixed-test-secret"
GOOD_HEADERS = {"Authorization": f"Bearer {SECRET}", "x-vercel-cron": "1"}


def build_app(tmp_path):
    settings = oauth_settings(
        tmp_path, scheduler_interval=3600, cron_secret=SECRET,
        oauth_callback_url="http://127.0.0.1:18000/auth/github/callback",
        web_url="http://127.0.0.1:13000",
    )
    return create_app(settings, validate=False, enable_scheduler=False,
                      oauth_service_factory=FakeOAuth, account_client_factory=FakeAccountGitHub,
                      github_client_factory=FakeRepositoryGitHub)


@pytest.fixture
def journal():
    JOURNAL.reset()
    yield JOURNAL
    JOURNAL.reset()


@pytest.fixture
def client(tmp_path, journal):
    app = build_app(tmp_path)
    with TestClient(app) as c:
        complete_oauth(c)
        assert c.put("/api/github/repository", json={"full_name": REPO_A}).status_code == 200
        assert c.put("/api/schedule", json={"expression": "* * * * *", "enabled": True}).status_code == 200
        JOURNAL.reset()  # authorization/setup calls are not scheduler work
        c.app = app
        yield c


def _scheduled(client):
    return [op for op in client.get("/api/operations").json() if op["source"] == "scheduled"]


def test_c5_serverless_app_starts_no_scheduler(tmp_path, journal):
    app = build_app(tmp_path)
    with TestClient(app):
        assert not hasattr(app.state, "scheduler")


def test_c3_rejects_without_both_factors(client, journal):
    assert client.post("/scheduler/tick").status_code == 403
    assert client.post("/scheduler/tick", headers={"Authorization": f"Bearer {SECRET}"}).status_code == 403
    assert client.post("/scheduler/tick", headers={"x-vercel-cron": "1"}).status_code == 403
    assert client.post("/scheduler/tick",
                       headers={"Authorization": "Bearer wrong", "x-vercel-cron": "1"}).status_code == 403
    assert _scheduled(client) == []
    assert journal.kinds() == []


def test_c3_returns_503_when_cron_secret_is_unset(tmp_path, journal):
    settings = oauth_settings(tmp_path, oauth_callback_url="http://127.0.0.1:18000/auth/github/callback",
                              web_url="http://127.0.0.1:13000")
    app = create_app(settings, validate=False, enable_scheduler=False, oauth_service_factory=FakeOAuth,
                     account_client_factory=FakeAccountGitHub, github_client_factory=FakeRepositoryGitHub)
    with TestClient(app) as c:
        assert c.post("/scheduler/tick", headers=GOOD_HEADERS).status_code == 503


def test_c4_authorized_tick_is_idempotent(client, journal):
    first = client.post("/scheduler/tick", headers=GOOD_HEADERS)
    assert first.status_code == 200 and first.json()["ran"] is True
    second = client.post("/scheduler/tick", headers=GOOD_HEADERS)
    assert second.status_code == 200 and second.json()["ran"] is False

    scheduled = _scheduled(client)
    assert len(scheduled) == 1
    assert scheduled[0]["result"] == "draft_created"
    assert JOURNAL.for_repo(REPO_A)


def test_c4_concurrent_ticks_converge_to_one_operation(client, journal):
    store = client.app.state.store
    slot = datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc).isoformat()

    def run_once():
        runner = OperationRunner(store, None, client_provider=client.app.state.github_provider)
        return runner.run("scheduled", slot)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = [f.result() for f in [pool.submit(run_once), pool.submit(run_once)]]

    outcomes = sorted(r["result"] for r in results)
    assert outcomes == ["draft_created", "suppressed"]
    scheduled = [op for op in store.operations() if op["scheduled_for"] == slot]
    assert len(scheduled) == 1
    assert any(event["kind"] == "operation_suppressed"
               for event in scheduled[0]["activity"])

    # A tick after completion for the same slot does not re-run it.
    after = OperationRunner(store, None, client_provider=client.app.state.github_provider).run("scheduled", slot)
    assert after["result"] == "suppressed"
