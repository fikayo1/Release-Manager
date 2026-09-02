# Release Manager

A FastAPI workflow service and responsive Next.js operator dashboard for evidence-based, human-governed GitHub releases.

## Setup and run

```bash
./init.sh
# Register a GitHub OAuth App with callback http://127.0.0.1:8000/auth/github/callback
export GITHUB_OAUTH_CLIENT_ID=... GITHUB_OAUTH_CLIENT_SECRET=...
export GITHUB_OAUTH_CALLBACK_URL=http://127.0.0.1:8000/auth/github/callback
export SESSION_SECRET='a-long-random-secret'
export RELEASE_MANAGER_WEB_URL=http://127.0.0.1:3000
export RELEASE_MANAGER_DB=/var/lib/release-manager/state.db # optional; contains OAuth tokens
.venv/bin/uvicorn src.app:app --port 8000
RELEASE_MANAGER_API_URL=http://127.0.0.1:8000 npm --prefix frontend run dev
```

Open **http://127.0.0.1:3000/settings/github** first, choose **Continue with GitHub**, authorize the requested `repo` scope (needed for authorized private repositories), and select a repository. Dashboard routes are `/`, `/releases`, `/operations`, `/settings/github`, and `/settings/schedule`; release details are `/releases/{id}`. The backend health endpoint is http://127.0.0.1:8000/health. `RELEASE_MANAGER_API_URL` is server-only; never use a `NEXT_PUBLIC_` secret. `SCHEDULER_INTERVAL_SECONDS` optionally controls backend polling.

The singleton schedule accepts exactly five cron fields and is evaluated in UTC. It is disabled by default. Schedule, operations, leases, scans, packs, decisions, publication attempts, reconciliation, and audit records persist in SQLite. Startup applies additive versioned migrations; back up the database before an upgrade. Expired leases permit recovery after process death, while overlapping attempts are retained as suppressed operations. Approval requires a nonblank actor and reason and immediately attempts publication; rejection is terminal. An uncertain publication must be reconciled before retrying.

In production use HTTPS URLs; the session cookie is HttpOnly, SameSite=Lax, and Secure when `RELEASE_MANAGER_WEB_URL` is HTTPS. Restrict and encrypt SQLite backups because the database contains GitHub tokens. Revoked credentials are shown as requiring reconnection. A repository selection is captured when a scan starts, so changing selection affects only future scans and never retargets an existing release. For non-interactive legacy automation only, the complete `GITHUB_OWNER`, `GITHUB_REPO`, and `GITHUB_TOKEN` triple may replace OAuth configuration; partial triples are rejected.

Page navigation and refresh are read-only. Only the explicit **Scan now** button or a due enabled schedule starts a scan. There is no application role gate, so restrict network access. GitHub credentials remain in FastAPI and must not be sent to the browser.

## Verification

Browser binaries are provisioned by an operator with `shipyard setup --browser-tests`, not by package scripts.

```bash
.venv/bin/python -m pytest -q
npm --prefix frontend test
npm --prefix frontend run test:e2e
npm --prefix frontend run build
```
