import pytest

from src.config import Settings

OAUTH = dict(
    oauth_client_id="client-id",
    oauth_client_secret="client-super-secret",
    oauth_callback_url="https://rm.example/auth/github/callback",
    session_secret="session-super-secret",
    web_url="https://rm.example",
)


def test_missing_oauth_configuration_is_rejected():
    with pytest.raises(ValueError):
        Settings(oauth_client_id="only-a-client-id")


def test_callback_url_must_be_the_web_origin_path():
    with pytest.raises(ValueError):
        Settings(**{**OAUTH, "oauth_callback_url": "https://rm.example/callback"})


def test_secrets_and_database_url_are_redacted():
    cfg = Settings(**OAUTH, database_url="postgres://user:hunter2@db.internal/rm",
                   cron_secret="cron-super-secret")
    text = repr(cfg)
    for secret in ("client-super-secret", "session-super-secret", "cron-super-secret",
                   "hunter2", "postgres://"):
        assert secret not in text


def test_legacy_triple_no_longer_configures_auth(monkeypatch):
    for name in ("GITHUB_OAUTH_CLIENT_ID", "GITHUB_OAUTH_CLIENT_SECRET",
                 "GITHUB_OAUTH_CALLBACK_URL", "SESSION_SECRET", "RELEASE_MANAGER_WEB_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GITHUB_OWNER", "acme")
    monkeypatch.setenv("GITHUB_REPO", "widget")
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    with pytest.raises(ValueError):
        Settings.from_env()
