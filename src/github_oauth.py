"""Server-only GitHub OAuth helpers.

Only digests of OAuth state are persisted. The browser cookie is an opaque,
signed session identifier and never contains GitHub credentials.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import secrets
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class OAuthError(RuntimeError):
    pass


def _utcnow():
    return datetime.now(timezone.utc)


@dataclass(repr=False)
class OAuthService:
    store: object
    client_id: str
    client_secret: str
    callback_url: str
    session_secret: str
    secure_cookie: bool = False
    token_request: object | None = None

    cookie_name = "release_manager_session"

    def __repr__(self):
        return "OAuthService(client_id='***', client_secret='***', session_secret='***')"

    def sign_session(self, session_id: str) -> str:
        signature = hmac.new(self.session_secret.encode(), session_id.encode(), hashlib.sha256).hexdigest()
        return session_id + "." + signature

    def read_session(self, cookie: str | None) -> str | None:
        if not cookie or "." not in cookie:
            return None
        session, signature = cookie.rsplit(".", 1)
        expected = hmac.new(self.session_secret.encode(), session.encode(), hashlib.sha256).hexdigest()
        return session if len(session) >= 32 and hmac.compare_digest(signature, expected) else None

    def begin(self, session_id: str | None = None):
        session_id = session_id or secrets.token_urlsafe(32)
        state = secrets.token_urlsafe(32)
        digest = hashlib.sha256(state.encode()).hexdigest()
        now = _utcnow()
        self.store.create_oauth_state(digest, session_id, now.isoformat(), (now + timedelta(minutes=10)).isoformat())
        url = "https://github.com/login/oauth/authorize?" + urlencode({
            "client_id": self.client_id, "redirect_uri": self.callback_url,
            "scope": "repo", "state": state,
        })
        return url, self.sign_session(session_id)

    def consume(self, state: str, signed_cookie: str | None):
        session = self.read_session(signed_cookie)
        if not session or not state:
            raise OAuthError("OAuth state is missing or invalid")
        digest = hashlib.sha256(state.encode()).hexdigest()
        if not self.store.consume_oauth_state(digest, session, _utcnow().isoformat()):
            raise OAuthError("OAuth state is invalid, expired, or already used")

    def exchange(self, code: str):
        if not code:
            raise OAuthError("GitHub did not provide an authorization code")
        if self.token_request:
            data = self.token_request(code)
        else:
            body = urlencode({"client_id": self.client_id, "client_secret": self.client_secret,
                              "code": code, "redirect_uri": self.callback_url}).encode()
            req = Request("https://github.com/login/oauth/access_token", body,
                          {"Accept": "application/json", "User-Agent": "release-manager/1"})
            try:
                with urlopen(req, timeout=20) as response:
                    data = json.loads(response.read())
            except Exception as exc:
                raise OAuthError("GitHub token exchange failed") from exc
        token = data.get("access_token") if isinstance(data, dict) else None
        if not token:
            raise OAuthError("GitHub token exchange failed")
        return token, data.get("refresh_token"), data.get("expires_in")
