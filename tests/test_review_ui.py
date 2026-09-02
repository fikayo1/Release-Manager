from fastapi.testclient import TestClient

from src.app import create_app
from src.config import Settings
from src.models import Claim, Pack, Release
from src.store import Store


class GitHub:
    def __init__(self, fail=False): self.fail, self.writes = fail, 0
    def create_release(self, tag, title, body):
        self.writes += 1
        if self.fail: raise RuntimeError("secret transport detail")
        return Release(tag, title, body, "now", "https://github.test/release")


def oauth_settings(tmp_path, **overrides):
    base = dict(
        database=str(tmp_path / "state.db"),
        oauth_client_id="unit-client", oauth_client_secret="unit-secret",
        oauth_callback_url="http://testserver/auth/github/callback",
        session_secret="unit-session-secret-0123456789abcdef", web_url="http://testserver",
    )
    return Settings(**{**base, **overrides})


def client_for(tmp_path, github=None):
    app = create_app(oauth_settings(tmp_path), github or GitHub(), validate=False)
    return TestClient(app), app.state.store


def add_pack(store, pid="p", created="2026-01-01", status=None):
    with store.connect() as db:
        db.execute("INSERT INTO scans VALUES(?,?,?)", ("s" + pid, '{"commits":[],"pulls":[]}', created))
    pack = Pack(pid, "s" + pid, "1.2.3", "v1.2.3", "Release v1.2.3", "## Changes\n- One", "Ready", "Patch because safe", (Claim("Changes", "One", "e"),))
    store.save_pack(pack, created)
    if status == "rejected": store.decide(pid, "rejected", "alice", "not ready", created)


def test_empty_and_ordered_review_pages(tmp_path):
    client, store = client_for(tmp_path)
    assert "No release packs yet" in client.get("/review").text
    add_pack(store, "old", "2026-01-01"); add_pack(store, "new", "2026-02-01")
    text = client.get("/review").text
    assert text.index("pack-new") < text.index("pack-old")
    assert client.get("/review/packs/new").status_code == 200
    assert client.get("/review/packs/missing").status_code == 404


def test_form_decisions_validate_publish_and_redirect(tmp_path):
    gh = GitHub(); client, store = client_for(tmp_path, gh); add_pack(store)
    response = client.post("/review/packs/p/approve", data={"actor":"alice", "reason":"  "})
    assert response.status_code == 409 and gh.writes == 0 and store.pack("p")["status"] == "pending"
    response = client.post("/review/packs/p/approve", data={"actor":"alice", "reason":"ship it"}, follow_redirects=False)
    assert response.status_code == 303 and gh.writes == 1 and store.pack("p")["status"] == "published"


def test_publication_failure_is_truthful(tmp_path):
    gh = GitHub(True); client, store = client_for(tmp_path, gh); add_pack(store)
    response = client.post("/review/packs/p/approve", data={"actor":"alice", "reason":"ship it"})
    assert response.status_code == 502
    assert "outcome is uncertain" in response.text
    assert store.pack("p")["status"] == "uncertain"
