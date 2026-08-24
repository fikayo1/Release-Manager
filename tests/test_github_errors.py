import pytest

from src.github_client import GitHubClient, GitHubError, GitHubTransportError


class Response:
    def __init__(self, status, payload, headers=None):
        self.status_code = status
        self.payload = payload
        self.headers = headers or {}

    def json(self):
        return self.payload


def client(response):
    return GitHubClient("acme", "widget", "top-secret", lambda *a, **k: response)


def test_404_is_only_optional_for_release_lookups():
    response = Response(404, {"message": "Not Found"})
    assert client(response).latest_release() is None
    assert client(response).release_for_tag("v1") is None
    with pytest.raises(GitHubError, match="acme/widget not found or not readable"):
        client(response).repository()


def test_auth_rate_limit_and_safe_forbidden_errors():
    with pytest.raises(GitHubError, match="authentication failed"):
        client(Response(401, {"message": "bad credentials"})).repository()
    limited = Response(403, {"message": "rate limit"}, {
        "X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1893456000"
    })
    with pytest.raises(GitHubError, match="resets at 1893456000"):
        client(limited).repository()
    with pytest.raises(GitHubError, match="organization policy"):
        client(Response(403, {"message": "organization policy"})).repository()


def test_transport_is_clear_and_token_is_redacted():
    def broken(*args, **kwargs):
        raise OSError("top-secret leaked by transport")

    gh = GitHubClient("acme", "widget", "top-secret", broken)
    assert "top-secret" not in repr(gh)
    with pytest.raises(GitHubTransportError) as caught:
        gh.repository()
    assert "top-secret" not in str(caught.value)
