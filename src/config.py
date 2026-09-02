"""Environment-only configuration. Secret values are never represented."""
from dataclasses import dataclass
import os
from urllib.parse import urlparse


@dataclass(frozen=True, repr=False)
class Settings:
    # Complete legacy automation triple. Empty in interactive OAuth mode.
    owner: str = ""
    repo: str = ""
    token: str = ""
    database: str = "release-manager.db"
    scheduler_interval: float = 30.0
    oauth_client_id: str = ""
    oauth_client_secret: str = ""
    oauth_callback_url: str = ""
    session_secret: str = ""
    web_url: str = ""

    def __post_init__(self):
        legacy = (bool(self.owner.strip()), bool(self.repo.strip()), bool(self.token.strip()))
        oauth = tuple(bool(x.strip()) for x in (self.oauth_client_id, self.oauth_client_secret,
                                                self.oauth_callback_url, self.session_secret, self.web_url))
        if any(legacy) and not all(legacy):
            missing = [n for n, present in zip(("GITHUB_OWNER", "GITHUB_REPO", "GITHUB_TOKEN"), legacy) if not present]
            raise ValueError("Missing required configuration: " + ", ".join(missing))
        if not all(legacy) and not all(oauth):
            names = ("GITHUB_OAUTH_CLIENT_ID", "GITHUB_OAUTH_CLIENT_SECRET", "GITHUB_OAUTH_CALLBACK_URL",
                     "SESSION_SECRET", "RELEASE_MANAGER_WEB_URL")
            missing = [n for n, present in zip(names, oauth) if not present]
            raise ValueError("Missing required configuration: " + ", ".join(missing))
        if all(oauth) and not self.oauth_callback_url.endswith("/auth/github/callback"):
            raise ValueError("GITHUB_OAUTH_CALLBACK_URL must end with /auth/github/callback")

    @classmethod
    def from_env(cls):
        return cls(os.getenv("GITHUB_OWNER", ""), os.getenv("GITHUB_REPO", ""), os.getenv("GITHUB_TOKEN", ""),
                   os.getenv("RELEASE_MANAGER_DB", "release-manager.db"), float(os.getenv("SCHEDULER_INTERVAL_SECONDS", "30")),
                   os.getenv("GITHUB_OAUTH_CLIENT_ID", ""), os.getenv("GITHUB_OAUTH_CLIENT_SECRET", ""),
                   os.getenv("GITHUB_OAUTH_CALLBACK_URL", ""), os.getenv("SESSION_SECRET", ""),
                   os.getenv("RELEASE_MANAGER_WEB_URL", ""))

    @property
    def legacy(self): return bool(self.owner and self.repo and self.token)
    @property
    def interactive(self): return bool(self.oauth_client_id)
    @property
    def secure_cookie(self): return urlparse(self.web_url).scheme == "https"
    @property
    def slug(self): return f"{self.owner}/{self.repo}"

    def __repr__(self):
        return (f"Settings(owner={self.owner!r}, repo={self.repo!r}, token='***', database={self.database!r}, "
                f"scheduler_interval={self.scheduler_interval!r}, oauth_client_id='***', "
                "oauth_client_secret='***', session_secret='***')")
