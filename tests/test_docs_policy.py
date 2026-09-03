"""C7: operator docs describe the route policy, identity boundary, token
protection, concurrency limit, scheduler auth, the two Vercel roots, the
migration + verification steps, and the legacy GITHUB_* status -- with no
real secret material anywhere in the docs or tracked env examples.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text()
OPERATIONS = (ROOT / "backend" / "src" / "OPERATIONS.md").read_text()
DOCS = README + "\n" + OPERATIONS

ENV_NAMES = [
    "DATABASE_URL", "POSTGRES_URL", "RELEASE_MANAGER_WEB_URL",
    "GITHUB_OAUTH_CLIENT_ID", "GITHUB_OAUTH_CLIENT_SECRET", "GITHUB_OAUTH_CALLBACK_URL",
    "SESSION_SECRET", "CRON_SECRET", "MAX_CONCURRENT_SCANS", "TOKEN_ENCRYPTION_KEY",
    "RELEASE_MANAGER_API_URL",
]


def test_readme_documents_route_policy_and_identity_boundary():
    for phrase in [
        "GET /health", "GET /auth/github", "/api/cron/scheduler",
        "one authenticated GitHub account is exactly one user",
        "shared organization, team, or application role",
        "401", "403", "429",
        "redirect to `/login`",
    ]:
        assert phrase in README, phrase


def test_readme_documents_token_protection_and_concurrency():
    assert "encrypted at rest" in README
    assert "TOKEN_ENCRYPTION_KEY" in README and "SESSION_SECRET" in README
    assert "server-only" in README and "NEXT_PUBLIC_" in README
    assert "MAX_CONCURRENT_SCANS" in README
    assert "1..10" in README
    assert "exempt" in README and "CRON_SECRET" in README


def test_docs_list_every_env_var_name():
    for name in ENV_NAMES:
        assert name in DOCS, f"{name} missing from docs"


def test_docs_cover_two_vercel_roots_and_migration_and_verification():
    assert "two Vercel projects" in README.lower() or "two Vercel projects" in README
    assert "route to the Python function through Next rewrites" in README
    assert "python -m src.migrate" in README
    for command in [
        ".venv/bin/python -m pytest -q",
        "npm --prefix frontend test",
        "npm --prefix frontend run test:e2e",
        "npm --prefix frontend run build",
    ]:
        assert command in README, command


def test_docs_state_legacy_triple_status():
    for name in ("GITHUB_TOKEN", "GITHUB_OWNER", "GITHUB_REPO"):
        assert name in DOCS
    assert "ignored by the OAuth path" in README and "ignored by the OAuth path" in OPERATIONS


def test_no_real_secret_material_in_docs_or_env_examples():
    blob = DOCS
    blob += (ROOT / "backend" / ".env.example").read_text()
    blob += (ROOT / "frontend" / ".env.example").read_text()
    assert "ghp_" not in blob
    assert "ghs_" not in blob
    # No long unbroken high-entropy runs that would look like a real secret.
    assert not re.search(r"[A-Za-z0-9+/]{40,}", blob)
