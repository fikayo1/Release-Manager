"""Stdlib-only authenticated encryption for OAuth tokens at rest.

No third-party dependency is introduced. Confidentiality comes from an
HMAC-SHA256 keystream (a CTR-style construction) seeded with a per-record
random nonce; integrity comes from a separate HMAC-SHA256 tag over the
nonce and ciphertext. Key material is taken from ``TOKEN_ENCRYPTION_KEY``
when set, otherwise derived from the already-required ``SESSION_SECRET``
with a fixed domain-separation label so the two secrets never collide.

The ciphertext is an opaque, versioned, URL-safe base64 string. The
plaintext token therefore never appears verbatim in the database file.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

_PREFIX = "rmenc.v1."
_LABEL = b"release-manager/token-encryption/v1"
_NONCE_BYTES = 16
_TAG_BYTES = 32


def token_key(settings) -> bytes:
    """Derive the 32-byte token key from settings, or ``b""`` when unset."""
    material = (getattr(settings, "token_encryption_key", "") or "").strip()
    if not material:
        material = (getattr(settings, "session_secret", "") or "").strip()
    if not material:
        return b""
    return hashlib.pbkdf2_hmac("sha256", material.encode("utf-8"), _LABEL, 200_000, dklen=32)


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest())
        counter += 1
    return bytes(out[:length])


def encrypt_token(plaintext, *, key: bytes):
    """Return versioned ciphertext for ``plaintext`` (``None``/empty pass through)."""
    if plaintext is None or plaintext == "":
        return plaintext
    if not key:
        return plaintext
    data = str(plaintext).encode("utf-8")
    nonce = secrets.token_bytes(_NONCE_BYTES)
    ciphertext = bytes(b ^ k for b, k in zip(data, _keystream(key, nonce, len(data))))
    tag = hmac.new(key, _LABEL + nonce + ciphertext, hashlib.sha256).digest()
    return _PREFIX + base64.urlsafe_b64encode(nonce + tag + ciphertext).decode("ascii")


def decrypt_token(value, *, key: bytes):
    """Inverse of :func:`encrypt_token`; legacy plaintext rows pass through."""
    if value is None or value == "":
        return value
    if not isinstance(value, str) or not value.startswith(_PREFIX):
        return value
    if not key:
        raise ValueError("token decryption key is unavailable")
    raw = base64.urlsafe_b64decode(value[len(_PREFIX):].encode("ascii"))
    nonce = raw[:_NONCE_BYTES]
    tag = raw[_NONCE_BYTES:_NONCE_BYTES + _TAG_BYTES]
    ciphertext = raw[_NONCE_BYTES + _TAG_BYTES:]
    expected = hmac.new(key, _LABEL + nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected):
        raise ValueError("token ciphertext failed integrity verification")
    return bytes(b ^ k for b, k in zip(ciphertext, _keystream(key, nonce, len(ciphertext)))).decode("utf-8")
