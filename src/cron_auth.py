"""Authorization for the serverless scheduler-tick endpoint.

A tick does work only when it carries **both** a valid ``CRON_SECRET`` bearer
token **and** the header that proves a Vercel Cron invocation. Header values and
the secret are never logged.
"""
import hmac


def authorize_cron(headers, settings) -> bool:
    secret = (getattr(settings, "cron_secret", "") or "").strip()
    if not secret:
        return False
    presented = headers.get("authorization", "") or headers.get("Authorization", "")
    if not hmac.compare_digest(presented.strip(), f"Bearer {secret}"):
        return False
    header_name = getattr(settings, "cron_header", "x-vercel-cron") or "x-vercel-cron"
    return bool(headers.get(header_name) or headers.get(header_name.lower()))
