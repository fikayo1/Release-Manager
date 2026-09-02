"""C7 (backend half): the access-token canary and server-only secrets never
appear in any client-visible response body or header, nor in object reprs."""
import pytest
from fastapi.testclient import TestClient

from src.app import create_app
from src.github_oauth import OAuthError
from tests.fakes import (
    CANARY_TOKEN, JOURNAL, REPO_A, FakeAccountGitHub, FakeOAuth, FakeRepositoryGitHub,
)
from tests.test_oauth_flow import complete_oauth
from tests.test_review_ui import oauth_settings

CLIENT_SECRET = "oauth-client-secret-must-not-leak"
CRON_SECRET = "cron-secret-must-not-leak"
DB_URL = "postgres://rmuser:dbpw-must-not-leak@db.internal/rm"

SECRETS = [CANARY_TOKEN, CLIENT_SECRET, CRON_SECRET, DB_URL, "dbpw-must-not-leak"]


@pytest.fixture
def journal():
    JOURNAL.reset()
    yield JOURNAL
    JOURNAL.reset()


@pytest.fixture
def client(tmp_path, journal):
    settings = oauth_settings(
        tmp_path, oauth_client_secret=CLIENT_SECRET, cron_secret=CRON_SECRET,
        oauth_callback_url="http://127.0.0.1:18000/auth/github/callback",
        web_url="http://127.0.0.1:13000",
    )
    app = create_app(settings, validate=False, enable_scheduler=False, oauth_service_factory=FakeOAuth,
                     account_client_factory=FakeAccountGitHub, github_client_factory=FakeRepositoryGitHub)
    with TestClient(app) as c:
        yield c


def test_secrets_never_reach_a_client_surface(client):
    complete_oauth(client)
    client.put("/api/github/repository", json={"full_name": REPO_A})
    client.post("/api/scans")

    responses = [
        client.get("/api/github"),
        client.put("/api/github/repository", json={"full_name": REPO_A}),
        client.get("/api/operations"),
        client.get("/api/releases"),
        client.get("/api/audit"),
        client.get("/auth/github/callback", params={"state": "x", "code": "y"}),
        client.post("/scheduler/tick", headers={"Authorization": f"Bearer {CRON_SECRET}"}),
    ]
    for response in responses:
        haystack = response.text + "\n" + "\n".join(response.headers.values())
        for secret in SECRETS:
            assert secret not in haystack


def test_reprs_and_errors_redact_secrets(client, tmp_path):
    settings = client.app.state.settings
    redacted_database_settings = oauth_settings(tmp_path, database_url=DB_URL)
    for secret in (CLIENT_SECRET, CRON_SECRET):
        assert secret not in repr(settings)
    assert "dbpw-must-not-leak" not in repr(redacted_database_settings)
    oauth = client.app.state.oauth
    assert CLIENT_SECRET not in repr(oauth)
    assert CANARY_TOKEN not in repr(FakeRepositoryGitHub("fixture", "repository-a", CANARY_TOKEN))
    assert CANARY_TOKEN not in str(OAuthError("GitHub token exchange failed"))


def test_connection_view_excludes_credentials_but_credentials_accessor_returns_token(client):
    complete_oauth(client)
    store = client.app.state.store
    assert "access_token" not in store.github_connection()
    assert CANARY_TOKEN not in str(store.github_connection())
    assert store.github_credentials()["access_token"] == CANARY_TOKEN
