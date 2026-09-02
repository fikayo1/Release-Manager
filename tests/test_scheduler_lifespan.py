import time
from fastapi.testclient import TestClient

from src.app import create_app
from src.config import Settings
from src.models import Repository


class EmptyGitHub:
    owner = "owner"
    repo = "repo"
    def repository(self): return Repository("main", "2025-01-01T00:00:00+00:00", "url")
    def latest_release(self): return None
    def commits_since(self, *args): return ()
    def merged_pulls_since(self, *args): return ()


def test_lifespan_starts_scheduler_and_heartbeat(tmp_path):
    settings = Settings(
        database=str(tmp_path / "state.db"), scheduler_interval=0.01,
        oauth_client_id="unit-client", oauth_client_secret="unit-secret",
        oauth_callback_url="http://testserver/auth/github/callback",
        session_secret="unit-session-secret-0123456789abcdef", web_url="http://testserver",
    )
    app = create_app(settings, EmptyGitHub(), validate=False)
    with TestClient(app) as client:
        for _ in range(50):
            schedule = client.get("/api/schedule").json()
            if schedule["health"]["heartbeat_at"]:
                break
            time.sleep(0.01)
        assert schedule["health"]["heartbeat_at"] is not None
        assert hasattr(app.state, "scheduler")
