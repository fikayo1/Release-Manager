"""Deterministic, offline GitHub OAuth + repository doubles.

Shared by ``tests/e2e_app.py`` (Playwright) and the backend pytest suites so
both prove the same behaviour against the same fakes and the same token canary.
No test that imports this module ever touches the network: any unexpected URL
raises ``AssertionError``.
"""
from urllib.parse import urlparse

from src.github_client import GitHubAccountClient
from src.github_oauth import OAuthService
from src.models import Bump, Claim, Evidence, Pack, Release, Repository, Scan, Verdict
from src.phases import approve

# One distinctive, obviously-fake access token. If this exact string ever shows
# up in a browser-visible URL, a rendered page, a browser-observed response
# body, Web Storage, browser console output, or a captured backend/frontend
# process log, acceptance criterion C2 has regressed.
CANARY_TOKEN = "ghp_FaKeCaNaRy0000NeverLogMe0000DEADBEEFcafe"

REPO_A = "fixture/repository-a"
REPO_B = "fixture/repository-b"
ACCEPTED_CODE = "accepted"

# Populated by ``FakeRepositoryGitHub.create_release`` and surfaced through the
# fixture's ``/test/publications`` endpoint.
PUBLISHED: list[dict] = []


class Journal:
    """Append-only record of every interaction the GitHub doubles observe."""

    def __init__(self) -> None:
        self._entries: list[dict] = []

    def record(self, kind, repository=None, detail=""):
        self._entries.append({"kind": kind, "repository": repository, "detail": detail})

    def entries(self):
        return list(self._entries)

    def reset(self):
        self._entries.clear()
        PUBLISHED.clear()

    def for_repo(self, name):
        return [entry for entry in self._entries if entry["repository"] == name]

    def repositories(self):
        return sorted({entry["repository"] for entry in self._entries if entry["repository"]})

    def kinds(self):
        return [entry["kind"] for entry in self._entries]


# Process-global: every fixture process is short-lived, and the backend tests
# reset it explicitly (see the ``journal`` fixture in each test module).
JOURNAL = Journal()


class FakeOAuth(OAuthService):
    """Deterministic token exchange; authorization stays on the local fixture."""

    def __init__(self, *args, authorize_origin=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.authorize_origin = authorize_origin

        def exchange(code):
            JOURNAL.record("token_exchange", detail="accepted" if code == ACCEPTED_CODE else "rejected")
            return {"access_token": CANARY_TOKEN} if code == ACCEPTED_CODE else {}

        self.token_request = exchange

    def begin(self, session_id=None):
        url, cookie = super().begin(session_id)
        JOURNAL.record("authorize", detail="oauth begin")
        # The callback may be on the web origin while the deterministic fake
        # authorization endpoint remains on the API fixture origin.
        origin = self.authorize_origin or self.callback_url.rsplit("/auth/github/callback", 1)[0]
        return f"{origin}/test/github/authorize?" + urlparse(url).query, cookie


class _GitHubResponse:
    def __init__(self, payload, link=""):
        self.status_code = 200
        self.headers = {"Link": link} if link else {}
        self._payload = payload

    def json(self):
        return self._payload


def _account_transport(method, url, **kwargs):
    """Two genuine REST pages so browser tests cross the production paginator."""
    assert method == "GET"
    assert kwargs["headers"]["Authorization"] == f"Bearer {CANARY_TOKEN}", "account call must carry the canary bearer token"
    if url == "https://api.github.com/user":
        JOURNAL.record("user", detail="account identity")
        return _GitHubResponse({"login": "oauth-fixture", "id": 42})
    if url == "https://api.github.com/user/repos":
        JOURNAL.record("repos_page", detail="page 1")
        return _GitHubResponse(
            [{"full_name": REPO_A, "private": True, "html_url": "https://example.test/a", "default_branch": "main"}],
            '<https://api.github.test/user/repos?page=2>; rel="next"',
        )
    if url == "https://api.github.test/user/repos?page=2":
        # The production client must not resend first-page query parameters here.
        assert kwargs.get("params") == {}
        JOURNAL.record("repos_page", detail="page 2")
        return _GitHubResponse(
            [{"full_name": REPO_B, "private": False, "html_url": "https://example.test/b", "default_branch": "main"}]
        )
    raise AssertionError(f"unexpected GitHub URL (no live network permitted): {url}")


class FakeAccountGitHub(GitHubAccountClient):
    def __init__(self, token):
        super().__init__(token, request=_account_transport)


class FakeRepositoryGitHub:
    """Repository-aware scan reads and release writes, every call journalled."""

    def __init__(self, owner, repo, token):
        assert token == CANARY_TOKEN, "repository client must use the canary token"
        self.owner, self.repo = owner, repo

    def __repr__(self):
        return f"FakeRepositoryGitHub(repository={self.owner}/{self.repo}, token='***')"

    @property
    def full_name(self):
        return f"{self.owner}/{self.repo}"

    def _note(self, kind, detail=""):
        JOURNAL.record(kind, repository=self.full_name, detail=detail)

    def repository(self):
        self._note("repo_read", "repository metadata")
        return Repository("main", "2025-01-01T00:00:00+00:00", f"https://example.test/{self.repo}")

    def latest_release(self):
        self._note("repo_read", "latest release")
        return Release("v1.0.0", "Release v1.0.0", "Initial", "2025-01-01T00:00:00+00:00", "https://example.test/v1")

    def commits_since(self, *args):
        self._note("repo_read", "commits")
        return (
            Evidence(
                f"commit-{self.repo}", "commit", f"feat: add deterministic dashboard to {self.full_name}",
                "fixture-user", "2025-01-02T00:00:00+00:00",
                f"https://example.test/{self.repo}/commit/1", sha="abc123",
            ),
        )

    def merged_pulls_since(self, *args):
        self._note("repo_read", "pulls")
        return ()

    def create_release(self, tag, title, body):
        self._note("release_write", f"create {tag}")
        PUBLISHED.append({"repository": self.full_name, "tag": tag})
        return Release(tag, title, body, "2025-01-03T00:00:00+00:00", f"https://example.test/{self.repo}/releases/{tag}")

    def release_for_tag(self, tag):
        self._note("tag_lookup", f"tag {tag}")
        return None


def seed_pack(store, pack_id, repository, status, *, tag=None):
    """Insert a ``repository``-targeted scan + pack (+ operation) directly in a
    state where reconcile / rollback / approval / publish is each applicable.

    ``status`` is one of ``pending`` (approve or reject), ``approved`` (publish),
    or ``uncertain`` (reconcile).
    """
    moment = "2026-01-01T00:00:00+00:00"
    tag = tag or f"v9.9.{abs(hash(pack_id)) % 97}"
    scan_id = f"scan-{pack_id}"
    commit = Evidence(f"c-{pack_id}", "commit", "feat: seeded change", "seed", moment,
                      "https://example.test/seed/1", sha=f"seed-{pack_id}")
    snapshot = Scan(scan_id, repository, moment, moment, False, "v9.9.0", (commit,), ())
    verdict = Verdict(True, Bump.PATCH, "seeded", (commit.id,))
    store.save_scan(snapshot, verdict, moment)
    pack = Pack(pack_id, scan_id, "9.9.1", tag, f"Release {tag}", "## Features\n\n- seeded change",
                f"Release {tag} is ready.", "Patch bump: seeded", (Claim("Features", "seeded change", commit.id),))
    store.save_pack(pack, moment)
    op_id = f"op-{pack_id}"
    store.create_operation(op_id, "manual", repository, moment)
    store.finish_operation(op_id, "draft_created", moment, scan_id, pack_id)
    if status == "pending":
        return
    if status == "approved":
        approve(store, pack_id, "seed-approver", "seed approval", moment)
        return
    if status == "uncertain":
        approve(store, pack_id, "seed-approver", "seed approval", moment)
        store.claim_publish(pack_id, moment)
        with store.connect() as db:
            db.execute("UPDATE packs SET status='uncertain' WHERE id=?", (pack_id,))
        return
    raise ValueError(f"unsupported seed status: {status}")
