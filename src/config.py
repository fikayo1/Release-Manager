"""Environment-only configuration (credentials are never serialized)."""
from dataclasses import dataclass
import os


@dataclass(frozen=True, repr=False)
class Settings:
    owner: str
    repo: str
    token: str
    database: str = "release-manager.db"
    scheduler_interval: float = 30.0

    def __post_init__(self) -> None:
        missing = [name for name, value in (("GITHUB_OWNER", self.owner), ("GITHUB_REPO", self.repo), ("GITHUB_TOKEN", self.token)) if not value.strip()]
        if missing:
            raise ValueError("Missing required configuration: " + ", ".join(missing))

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(os.getenv("GITHUB_OWNER", ""), os.getenv("GITHUB_REPO", ""), os.getenv("GITHUB_TOKEN", ""), os.getenv("RELEASE_MANAGER_DB", "release-manager.db"), float(os.getenv("SCHEDULER_INTERVAL_SECONDS", "30")))

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}"

    def __repr__(self) -> str:
        return f"Settings(owner={self.owner!r}, repo={self.repo!r}, token='***', database={self.database!r}, scheduler_interval={self.scheduler_interval!r})"
