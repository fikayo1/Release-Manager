"""Authorization for the serverless scheduler-tick endpoint.

A tick does work only when it carries **both** a valid ``CRON_SECRET`` bearer
token **and** the header that proves a Vercel Cron invocation. Header values and
the secret are never logged.
"""
import hmac


_INTERNAL_CRON_PROOF_HEADER = "x-vercel-cron"


def authorize_cron(headers, settings) -> bool:
    secret = (getattr(settings, "cron_secret", "") or "").strip()
    if not secret:
        return False
    presented = headers.get("authorization", "") or headers.get("Authorization", "")
    if not hmac.compare_digest(presented.strip(), f"Bearer {secret}"):
        return False
    return bool(
        headers.get(_INTERNAL_CRON_PROOF_HEADER)
        or headers.get(_INTERNAL_CRON_PROOF_HEADER.lower())
    )
