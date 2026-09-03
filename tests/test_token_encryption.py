"""C3: OAuth tokens are encrypted at rest with a stdlib-only construction.

The canary access token must never appear as plaintext in the SQLite file,
``github_credentials()`` must still round-trip it server-side, and the
browser-facing connection view must never carry credential columns.
"""
import pytest
from fastapi.testclient import TestClient

from src.config import Settings
from src.crypto import decrypt_token, encrypt_token, token_key
from tests.fakes import CANARY_TOKEN, JOURNAL
from tests.test_oauth_flow import build_app, complete_oauth


@pytest.fixture
def journal():
    JOURNAL.reset()
    yield JOURNAL
    JOURNAL.reset()


def test_sqlite_file_never_contains_the_plaintext_token(tmp_path, journal):
    db = tmp_path / "operator.db"
    app = build_app(db)
    with TestClient(app) as client:
        complete_oauth(client)
        store = app.state.store
        assert store.user_github_credentials("github:42")["access_token"] == CANARY_TOKEN
        assert "access_token" not in store.user_github_connection("github:42")
        assert CANARY_TOKEN not in str(store.user_github_connection("github:42"))

    raw = db.read_bytes()
    assert CANARY_TOKEN.encode() not in raw
    assert b"ghp_FaKeCaNaRy" not in raw


def test_crypto_round_trips_and_rejects_tampering():
    key = token_key(Settings(
        oauth_client_id="c", oauth_client_secret="s",
        oauth_callback_url="https://x.example/auth/github/callback",
        session_secret="a-long-deterministic-session-secret", web_url="https://x.example",
    ))
    assert key and len(key) == 32
    blob = encrypt_token(CANARY_TOKEN, key=key)
    assert blob.startswith("rmenc.v1.")
    assert CANARY_TOKEN not in blob
    assert decrypt_token(blob, key=key) == CANARY_TOKEN

    tampered = blob[:-2] + ("aa" if not blob.endswith("aa") else "bb")
    with pytest.raises(ValueError):
        decrypt_token(tampered, key=key)

    # Legacy / unencrypted values pass through unchanged.
    assert decrypt_token("plain-legacy-token", key=key) == "plain-legacy-token"


def test_token_key_is_absent_without_secret_material():
    assert token_key(object()) == b""
