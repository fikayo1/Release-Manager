"""Environment-only configuration. Secret values are never represented.

GitHub access is interactive OAuth only; the former non-interactive
``GITHUB_OWNER`` / ``GITHUB_REPO`` / ``GITHUB_TOKEN`` triple has been removed.
Postgres is selected when ``DATABASE_URL`` / ``POSTGRES_URL`` is set and SQLite
is the default otherwise (see :mod:`src.db`).
"""
from dataclasses import dataclass
import os
from urllib.parse import urlparse

_OAUTH_ENV = (
    ("oauth_client_id", "GITHUB_OAUTH_CLIENT_ID"),
    ("oauth_client_secret", "GITHUB_OAUTH_CLIENT_SECRET"),
    ("oauth_callback_url", "GITHUB_OAUTH_CALLBACK_URL"),
    ("session_secret", "SESSION_SECRET"),
    ("web_url", "RELEASE_MANAGER_WEB_URL"),
)


@dataclass(frozen=True, repr=False)
class Settings:
    database: str = "release-manager.db"
    scheduler_interval: float = 30.0
    oauth_client_id: str = ""
    oauth_client_secret: str = ""
    oauth_callback_url: str = ""
    session_secret: str = ""
    web_url: str = ""
    # Managed Postgres DSN (either variable). Empty -> SQLite fallback (dev/CI).
    database_url: str = ""
    # Shared secret Vercel Cron sends as ``Authorization: Bearer``.
    cron_secret: str = ""

    def __post_init__(self):
        missing = [env for attr, env in _OAUTH_ENV if not getattr(self, attr).strip()]
        if missing:
            raise ValueError("Missing required configuration: " + ", ".join(missing))
        if not self.oauth_callback_url.endswith("/auth/github/callback"):
            raise ValueError("GITHUB_OAUTH_CALLBACK_URL must end with /auth/github/callback")

    @classmethod
    def from_env(cls):
        return cls(
            database=os.getenv("RELEASE_MANAGER_DB", "release-manager.db"),
            scheduler_interval=float(os.getenv("SCHEDULER_INTERVAL_SECONDS", "30")),
            oauth_client_id=os.getenv("GITHUB_OAUTH_CLIENT_ID", ""),
            oauth_client_secret=os.getenv("GITHUB_OAUTH_CLIENT_SECRET", ""),
            oauth_callback_url=os.getenv("GITHUB_OAUTH_CALLBACK_URL", ""),
            session_secret=os.getenv("SESSION_SECRET", ""),
            web_url=os.getenv("RELEASE_MANAGER_WEB_URL", ""),
            database_url=os.getenv("DATABASE_URL", "") or os.getenv("POSTGRES_URL", ""),
            cron_secret=os.getenv("CRON_SECRET", ""),
        )

    @property
    def secure_cookie(self):
        return urlparse(self.web_url).scheme == "https"

    def __repr__(self):
        return (
            f"Settings(database={self.database!r}, scheduler_interval={self.scheduler_interval!r}, "
            "oauth_client_id='***', oauth_client_secret='***', session_secret='***', "
            "cron_secret='***', database_url='***')"
        )
