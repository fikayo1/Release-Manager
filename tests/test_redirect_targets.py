"""C4: the OAuth callback lands a successful sign-in on `<web_url>/dashboard`
and every failure mode on `<web_url>/login?error=<status>`, without changing
status codes or the OAuth journal."""
import pytest
from fastapi.testclient import TestClient

from tests.fakes import JOURNAL
from tests.test_oauth_flow import build_app, _authorize_state

WEB = "http://127.0.0.1:13000"


@pytest.fixture
def journal():
    JOURNAL.reset()
    yield JOURNAL
    JOURNAL.reset()


def test_successful_callback_redirects_to_dashboard(tmp_path, journal):
    with TestClient(build_app(tmp_path / "operator.db")) as client:
        state = _authorize_state(client)
        callback = client.get("/auth/github/callback", params={"state": state, "code": "accepted"},
                              follow_redirects=False)
        assert callback.status_code == 303
        assert callback.headers["location"] == f"{WEB}/dashboard"


@pytest.mark.parametrize("params,expected", [
    ({"code": "accepted"}, "invalid_state"),
    ({"state": "not-a-real-state", "code": "accepted"}, "invalid_state"),
])
def test_state_failures_redirect_to_login_with_error(tmp_path, journal, params, expected):
    with TestClient(build_app(tmp_path / "operator.db")) as client:
        callback = client.get("/auth/github/callback", params=params, follow_redirects=False)
        assert callback.status_code == 303
        assert callback.headers["location"] == f"{WEB}/login?error={expected}"


def test_denied_authorization_redirects_to_login(tmp_path, journal):
    with TestClient(build_app(tmp_path / "operator.db")) as client:
        state = _authorize_state(client)
        callback = client.get("/auth/github/callback", params={"state": state, "error": "access_denied"},
                              follow_redirects=False)
        assert callback.status_code == 303
        assert callback.headers["location"] == f"{WEB}/login?error=denied"


def test_replayed_state_redirects_to_login(tmp_path, journal):
    with TestClient(build_app(tmp_path / "operator.db")) as client:
        state = _authorize_state(client)
        first = client.get("/auth/github/callback", params={"state": state, "code": "accepted"},
                           follow_redirects=False)
        assert first.headers["location"] == f"{WEB}/dashboard"
        replay = client.get("/auth/github/callback", params={"state": state, "code": "accepted"},
                            follow_redirects=False)
        assert replay.status_code == 303
        assert replay.headers["location"] == f"{WEB}/login?error=invalid_state"


def test_missing_code_redirects_to_login(tmp_path, journal):
    with TestClient(build_app(tmp_path / "operator.db")) as client:
        state = _authorize_state(client)
        callback = client.get("/auth/github/callback", params={"state": state},
                              follow_redirects=False)
        assert callback.status_code == 303
        assert callback.headers["location"] == f"{WEB}/login?error=invalid_state"
