"""C1 + backend half of C2: OAuth completes through deterministic doubles and
the access token never leaves the backend boundary."""
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from src.app import create_app
from src.config import Settings
from tests.fakes import (
    CANARY_TOKEN,
    JOURNAL,
    REPO_A,
    REPO_B,
    FakeAccountGitHub,
    FakeOAuth,
    FakeRepositoryGitHub,
)


def build_app(db_path):
    settings = Settings(
        database=str(db_path), scheduler_interval=3600,
        oauth_client_id="fixture-client", oauth_client_secret="fixture-secret",
        oauth_callback_url="http://127.0.0.1:18000/auth/github/callback",
        session_secret="deterministic-test-session-secret-0123456789",
        web_url="http://127.0.0.1:13000",
    )
    return create_app(settings, validate=False, oauth_service_factory=FakeOAuth,
                      account_client_factory=FakeAccountGitHub,
                      github_client_factory=FakeRepositoryGitHub)


def _authorize_state(client):
    redirect = client.get("/auth/github", follow_redirects=False)
    assert redirect.status_code == 302
    location = redirect.headers["location"]
    assert location.startswith("http://127.0.0.1:18000/test/github/authorize?")
    return parse_qs(urlparse(location).query)["state"][0]


def complete_oauth(client):
    state = _authorize_state(client)
    callback = client.get("/auth/github/callback", params={"state": state, "code": "accepted"},
                          follow_redirects=False)
    assert callback.status_code == 303
    return callback


@pytest.fixture
def journal():
    JOURNAL.reset()
    yield JOURNAL
    JOURNAL.reset()


def test_oauth_completes_and_lists_repositories(tmp_path, journal):
    app = build_app(tmp_path / "operator.db")
    with TestClient(app) as client:
        callback = complete_oauth(client)
        assert callback.headers["location"] == "http://127.0.0.1:13000/settings/github?github=connected"

        settings = client.get("/api/github").json()
        assert settings["status"] == "connected"
        assert settings["account"] == "oauth-fixture"
        assert {repo["full_name"] for repo in settings["repositories"]} == {REPO_A, REPO_B}

        assert client.put("/api/github/repository", json={"full_name": REPO_A}).status_code == 200
        assert client.put("/api/github/repository", json={"full_name": "unauthorized/repo"}).status_code == 422

        # The double journal shows only the expected offline interactions.
        kinds = journal.kinds()
        assert kinds[:3] == ["authorize", "token_exchange", "user"]
        assert set(kinds) == {"authorize", "token_exchange", "user", "repos_page"}
        assert kinds.count("repos_page") == 6
        assert all(entry["repository"] is None for entry in journal.entries())


def test_access_token_never_leaves_the_backend(tmp_path, journal):
    app = build_app(tmp_path / "operator.db")
    with TestClient(app) as client:
        callback = complete_oauth(client)
        client.put("/api/github/repository", json={"full_name": REPO_A})
        client.post("/api/scans")

        exposed = [
            callback,
            client.get("/api/github"),
            client.put("/api/github/repository", json={"full_name": REPO_A}),
            client.get("/api/operations"),
            client.get("/api/releases"),
            client.get("/api/audit"),
        ]
        for response in exposed:
            assert CANARY_TOKEN not in response.text
            for value in response.headers.values():
                assert CANARY_TOKEN not in value

        store = app.state.store
        assert CANARY_TOKEN not in str(store.github_connection())
        assert "access_token" not in store.github_connection()
        assert store.github_credentials()["access_token"] == CANARY_TOKEN

        # Client reprs and error text redact the token.
        assert CANARY_TOKEN not in repr(FakeAccountGitHub(CANARY_TOKEN))
        assert CANARY_TOKEN not in repr(FakeRepositoryGitHub("fixture", "repository-a", CANARY_TOKEN))


def test_invalid_state_paths_keep_their_existing_status_codes(tmp_path, journal):
    app = build_app(tmp_path / "operator.db")
    with TestClient(app) as client:
        missing = client.get("/auth/github/callback", params={"code": "accepted"}, follow_redirects=False)
        assert "github=invalid_state" in missing.headers["location"]

        wrong = client.get("/auth/github/callback", params={"state": "not-a-real-state", "code": "accepted"},
                           follow_redirects=False)
        assert "github=invalid_state" in wrong.headers["location"]

        state = _authorize_state(client)
        denied = client.get("/auth/github/callback", params={"state": state, "error": "access_denied"},
                            follow_redirects=False)
        assert "github=denied" in denied.headers["location"]

        # A consumed state cannot be replayed.
        state = _authorize_state(client)
        assert client.get("/auth/github/callback", params={"state": state, "code": "accepted"},
                          follow_redirects=False).status_code == 303
        replay = client.get("/auth/github/callback", params={"state": state, "code": "accepted"},
                            follow_redirects=False)
        assert "github=invalid_state" in replay.headers["location"]
