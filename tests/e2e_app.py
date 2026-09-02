"""Deterministic OAuth and multi-repository GitHub double for browser tests."""
import os
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from fastapi import Request
from fastapi.responses import RedirectResponse

from src.app import create_app
from src.config import Settings
from src.github_client import GitHubAccountClient
from src.github_oauth import OAuthService
from src.models import Evidence, Release, Repository

DB = os.getenv("E2E_DB", "/tmp/release-manager-e2e.db")
Path(DB).unlink(missing_ok=True)
CALLBACK = "http://127.0.0.1:18000/auth/github/callback"
WEB = "http://127.0.0.1:13000"
PUBLISHED: list[dict] = []


class TestOAuth(OAuthService):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token_request = lambda code: {"access_token": "browser-test-token"} if code == "accepted" else {}

    def begin(self, session_id=None):
        url, cookie = super().begin(session_id)
        query = urlparse(url).query
        return "http://127.0.0.1:18000/test/github/authorize?" + query, cookie


class GitHubResponse:
    def __init__(self, payload, link=""):
        self.status_code = 200
        self.headers = {"Link": link} if link else {}
        self._payload = payload

    def json(self):
        return self._payload


def account_github_transport(method, url, **kwargs):
    """Two actual REST pages, so browser tests cross the production paginator."""
    assert method == "GET"
    assert kwargs["headers"]["Authorization"] == "Bearer browser-test-token"
    if url == "https://api.github.com/user":
        return GitHubResponse({"login": "oauth-fixture", "id": 42})
    if url == "https://api.github.com/user/repos":
        return GitHubResponse([
            {"full_name": "fixture/repository-a", "private": True,
             "html_url": "https://example.test/a", "default_branch": "main"},
        ], '<https://api.github.test/user/repos?page=2>; rel="next"')
    if url == "https://api.github.test/user/repos?page=2":
        # The production client must not resend first-page query parameters here.
        assert kwargs.get("params") == {}
        return GitHubResponse([
            {"full_name": "fixture/repository-b", "private": False,
             "html_url": "https://example.test/b", "default_branch": "main"},
        ])
    raise AssertionError(f"unexpected GitHub URL: {url}")


class AccountGitHub(GitHubAccountClient):
    def __init__(self, token):
        super().__init__(token, request=account_github_transport)


class RepositoryGitHub:
    def __init__(self, owner, repo, token):
        assert token == "browser-test-token"
        self.owner, self.repo = owner, repo

    def repository(self):
        return Repository("main", "2025-01-01T00:00:00+00:00", f"https://example.test/{self.repo}")

    def latest_release(self):
        return Release("v1.0.0", "Release v1.0.0", "Initial", "2025-01-01T00:00:00+00:00", "https://example.test/v1")

    def commits_since(self, *args):
        return (Evidence(f"commit-{self.repo}", "commit", f"feat: add deterministic dashboard to {self.repo}", "fixture-user", "2025-01-02T00:00:00+00:00", f"https://example.test/{self.repo}/commit/1", sha="abc123"),)

    def merged_pulls_since(self, *args):
        return ()

    def create_release(self, tag, title, body):
        PUBLISHED.append({"repository": f"{self.owner}/{self.repo}", "tag": tag})
        return Release(tag, title, body, "2025-01-03T00:00:00+00:00", f"https://example.test/{self.repo}/releases/{tag}")

    def release_for_tag(self, tag):
        return None


app = create_app(
    Settings(database=DB, scheduler_interval=0.05, oauth_client_id="fixture-client",
             oauth_client_secret="fixture-secret", oauth_callback_url=CALLBACK,
             session_secret="deterministic-browser-session-secret", web_url=WEB),
    validate=False, oauth_service_factory=TestOAuth,
    account_client_factory=AccountGitHub, github_client_factory=RepositoryGitHub,
)


@app.get("/test/github/authorize")
def authorize(request: Request, state: str, error: str = ""):
    query = {"state": state}
    query["error" if error else "code"] = "access_denied" if error else "accepted"
    return RedirectResponse(CALLBACK + "?" + urlencode(query), 302)


@app.get("/test/publications")
def publications():
    return PUBLISHED
