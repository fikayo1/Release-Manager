# Release Manager

A FastAPI workflow service and responsive Next.js operator dashboard for evidence-based, human-governed GitHub releases.

## Setup and run

```bash
./init.sh
export GITHUB_OWNER=my-org GITHUB_REPO=my-repo GITHUB_TOKEN=github-token
export RELEASE_MANAGER_DB=/var/lib/release-manager/state.db # optional
.venv/bin/uvicorn src.app:app --port 8000
RELEASE_MANAGER_API_URL=http://127.0.0.1:8000 npm --prefix frontend run dev
```

Open **http://127.0.0.1:3000/**. Routes are `/`, `/releases`, `/operations`, and `/settings/schedule`; release details are `/releases/{id}`. The backend health endpoint is http://127.0.0.1:8000/health. `RELEASE_MANAGER_API_URL` is server-only; never use a `NEXT_PUBLIC_` secret. `SCHEDULER_INTERVAL_SECONDS` optionally controls backend polling.

The singleton schedule accepts exactly five cron fields and is evaluated in UTC. It is disabled by default. Schedule, operations, leases, scans, packs, decisions, publication attempts, reconciliation, and audit records persist in SQLite. Startup applies additive versioned migrations; back up the database before an upgrade. Expired leases permit recovery after process death, while overlapping attempts are retained as suppressed operations. Approval requires a nonblank actor and reason and immediately attempts publication; rejection is terminal. An uncertain publication must be reconciled before retrying.

Page navigation and refresh are read-only. Only the explicit **Scan now** button or a due enabled schedule starts a scan. There is no application role gate, so restrict network access. GitHub credentials remain in FastAPI and must not be sent to the browser.

## Verification

Browser binaries are provisioned by an operator with `shipyard setup --browser-tests`, not by package scripts.

```bash
.venv/bin/python -m pytest -q
npm --prefix frontend test
npm --prefix frontend run test:e2e
npm --prefix frontend run build
```
