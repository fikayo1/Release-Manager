"""C3-C6: repository selection is durable, retargets only future scans, and
never retargets existing A work when the selection changes to B."""
import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from src.operations import OperationRunner
from src.scheduler import Scheduler
from src.store import Store
from tests.fakes import JOURNAL, PUBLISHED, REPO_A, REPO_B, seed_pack
from tests.test_oauth_flow import build_app, complete_oauth


@pytest.fixture
def journal():
    JOURNAL.reset()
    yield JOURNAL
    JOURNAL.reset()


def connect_and_select(client, repository):
    complete_oauth(client)
    assert client.put("/api/github/repository", json={"full_name": repository}).status_code == 200


def test_c3_selection_survives_a_fresh_process_on_the_same_file(tmp_path, journal):
    db = tmp_path / "operator.db"
    with TestClient(build_app(db)) as client:
        connect_and_select(client, REPO_A)
        assert client.get("/api/github").json()["selected_repository"] == REPO_A

    # A brand-new Store object on the exact same path == a fresh process.
    assert Store(str(db)).github_connection()["selected_repository"] == REPO_A

    with TestClient(build_app(db)) as restarted:
        settings = restarted.get("/api/github").json()
        assert settings["status"] == "connected"
        assert settings["selected_repository"] == REPO_A


def test_c4_manual_scan_retargets_to_b_and_leaves_a_work_alone(tmp_path, journal):
    db = tmp_path / "operator.db"
    with TestClient(build_app(db)) as client:
        connect_and_select(client, REPO_A)
        first = client.post("/api/scans").json()
        assert first["repository"] == REPO_A
        pack_a, op_a = first["pack_id"], first["id"]

        assert client.put("/api/github/repository", json={"full_name": REPO_B}).status_code == 200
        journal.reset()

        second = client.post("/api/scans").json()
        assert second["repository"] == REPO_B
        assert second["result"] == "draft_created"
        assert journal.for_repo(REPO_B) and journal.for_repo(REPO_A) == []

        # The retained A work is still A everywhere it is observable.
        assert client.get(f"/api/operations/{op_a}").json()["repository"] == REPO_A
        assert client.get(f"/api/releases/{pack_a}").json()["evidence"]["repository"] == REPO_A


def test_c5_next_due_scheduled_scan_targets_b(tmp_path, journal):
    db = tmp_path / "operator.db"
    app = build_app(db)
    with TestClient(app) as client:
        connect_and_select(client, REPO_B)
        assert client.put("/api/schedule", json={"expression": "* * * * *", "enabled": True}).status_code == 200
        journal.reset()

        fixed = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
        runner = OperationRunner(app.state.store, None,
                                 client_provider=app.state.github_provider, clock=lambda: fixed)
        asyncio.run(Scheduler(app.state.store, runner, clock=lambda: fixed).tick())

        scheduled = [op for op in client.get("/api/operations").json() if op["source"] == "scheduled"]
        assert len(scheduled) == 1
        assert scheduled[0]["repository"] == REPO_B
        assert scheduled[0]["result"] == "draft_created"
        assert journal.for_repo(REPO_B) and journal.for_repo(REPO_A) == []


def test_c6_existing_a_work_actions_never_touch_b(tmp_path, journal):
    db = tmp_path / "operator.db"
    app = build_app(db)
    with TestClient(app) as client:
        connect_and_select(client, REPO_A)
        store = app.state.store
        seed_pack(store, "approve-me", REPO_A, "pending")
        seed_pack(store, "reject-me", REPO_A, "pending")
        seed_pack(store, "publish-me", REPO_A, "approved")
        seed_pack(store, "reconcile-me", REPO_A, "uncertain")

        assert client.put("/api/github/repository", json={"full_name": REPO_B}).status_code == 200
        journal.reset()

        assert client.post("/api/packs/approve-me/approve", json={"actor": "a", "reason": "reviewed"}).status_code == 200
        assert client.post("/api/packs/reject-me/reject", json={"actor": "a", "reason": "not now"}).status_code == 200
        assert client.post("/api/packs/publish-me/publish").status_code == 200
        assert client.post("/api/packs/reconcile-me/reconcile").status_code == 200

        # Every GitHub interaction produced by an existing-work action named A.
        assert journal.repositories() == [REPO_A]
        assert {pub["repository"] for pub in PUBLISHED} == {REPO_A}

        for pid, expected in {
            "approve-me": "published", "reject-me": "rejected",
            "publish-me": "published", "reconcile-me": "retry_safe",
        }.items():
            detail = client.get(f"/api/releases/{pid}").json()
            assert detail["status"] == expected
            assert detail["evidence"]["repository"] == REPO_A
