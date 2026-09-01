"""Deterministic, release-worthy API used only by browser tests."""
import os
from pathlib import Path

from src.app import create_app
from src.config import Settings
from src.models import Evidence, Release, Repository

DB = os.getenv("E2E_DB", "/tmp/release-manager-e2e.db")
Path(DB).unlink(missing_ok=True)


class GitHub:
    owner = "fixture"
    repo = "repository"

    def repository(self):
        return Repository("main", "2025-01-01T00:00:00+00:00", "https://example.test/repository")

    def latest_release(self):
        return Release("v1.0.0", "Release v1.0.0", "Initial", "2025-01-01T00:00:00+00:00", "https://example.test/v1")

    def commits_since(self, *args):
        return (Evidence("commit-1", "commit", "feat: add deterministic dashboard", "fixture-user", "2025-01-02T00:00:00+00:00", "https://example.test/commit/1", sha="abc123"),)

    def merged_pulls_since(self, *args):
        return ()

    def create_release(self, tag, title, body):
        return Release(tag, title, body, "2025-01-03T00:00:00+00:00", f"https://example.test/releases/{tag}")


app = create_app(
    Settings("fixture", "repository", "not-a-real-token", DB, scheduler_interval=0.05),
    GitHub(),
    validate=False,
)
