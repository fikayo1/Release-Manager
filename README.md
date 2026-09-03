# Release Manager

A FastAPI workflow service and responsive Next.js operator dashboard for evidence-based, human-governed GitHub releases.

## Local setup and run

```bash
./init.sh
export GITHUB_OAUTH_CLIENT_ID=... GITHUB_OAUTH_CLIENT_SECRET=...
export GITHUB_OAUTH_CALLBACK_URL=http://127.0.0.1:13000/auth/github/callback
export SESSION_SECRET='a-long-random-secret'
export RELEASE_MANAGER_WEB_URL=http://127.0.0.1:13000
export RELEASE_MANAGER_DB=/var/lib/release-manager/state.db # optional
PYTHONPATH=backend .venv/bin/uvicorn src.app:app --host 127.0.0.1 --port 8000
npm --prefix frontend run dev -- --hostname 127.0.0.1 --port 13000
```

Open **http://127.0.0.1:13000/settings/github**, choose **Continue with GitHub**, authorize the `repo` scope, and select a repository. Dashboard routes are `/`, `/releases`, `/operations`, `/settings/github`, and `/settings/schedule`; release details are `/releases/{id}`. Backend health is **http://127.0.0.1:8000/health**. `RELEASE_MANAGER_API_URL` is server-only; never expose secrets through `NEXT_PUBLIC_` variables.

The singleton schedule has five cron fields and runs in UTC. Standalone FastAPI owns an in-process scheduler; `SCHEDULER_INTERVAL_SECONDS` controls its polling interval. Navigation and refresh are read-only: only **Scan now** or a due enabled schedule starts a scan. Operations, leases, scans, release packs, decisions, publication attempts, reconciliation, audit records, OAuth tokens, and repository selection are persistent. Approval requires an actor and reason and immediately attempts publication. An uncertain publication must be reconciled before retrying.

## Deploy to Vercel

Deploy this repository as **two Vercel projects**. This is still Vercel-only: separating the Next.js console from FastAPI avoids the route collision that occurs when a Next output and a Python function share one Vercel project.

1. Create the **Release Manager API** project with Root Directory `backend`. Vercel detects `main.py` as the FastAPI entrypoint. Configure `DATABASE_URL` (or `POSTGRES_URL`), `RELEASE_MANAGER_WEB_URL=https://<console-domain>`, `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET`, `GITHUB_OAUTH_CALLBACK_URL=https://<console-domain>/auth/github/callback`, `SESSION_SECRET`, and `CRON_SECRET`. Use `backend/.env.example` as the non-secret checklist.
2. Create the **Release Manager Console** project with Root Directory `frontend`. Configure `RELEASE_MANAGER_API_URL=https://<api-domain>` and the same `CRON_SECRET`; `frontend/.env.example` lists only those values. Do not expose any value through `NEXT_PUBLIC_` variables.
3. In the GitHub OAuth App set Homepage URL to `https://<console-domain>` and Authorization callback URL to `https://<console-domain>/auth/github/callback`.
4. The Console project's Vercel Cron invokes `GET /api/cron/scheduler`, verifies Vercel's `User-Agent: vercel-cron/1.0` and `CRON_SECRET`, then forwards a trusted `POST /scheduler/tick` to the API project. On Vercel Hobby its schedule is once daily at `0 9 * * *` (09:00 UTC; 10:00 Lagos). **Scan now** remains the primary trigger.
5. Probe **https://<api-domain>/health**. It returns `{"status":"ok"}` only once configuration and database initialization succeed.

Migrations are additive, versioned, automatic, idempotent, and serialized with a Postgres advisory transaction lock (SQLite uses an immediate transaction). They can also be run explicitly and repeatedly:

```bash
# with the same required OAuth/origin variables and DATABASE_URL in the environment
PYTHONPATH=backend .venv/bin/python -m src.migrate
```

After deployment, open **https://<production-domain>/settings/github**, click **Continue with GitHub**, authorize, confirm **Connected as**, select a repository, click **Scan now** on `/`, and confirm that a draft appears under `/releases`.

Without `DATABASE_URL`/`POSTGRES_URL`, SQLite remains the local/CI fallback. Back it up before upgrades and restrict/encrypt backups because it contains OAuth tokens. In production use HTTPS; the session cookie is HttpOnly, SameSite=Lax, and Secure. There is no application role gate, so restrict network access.

## Verification

Browser binaries are provisioned once by an operator with `shipyard setup --browser-tests`, never by package scripts.

```bash
.venv/bin/python -m pytest -q
npm --prefix frontend test
npm --prefix frontend run test:e2e
npm --prefix frontend run build
```

Acceptance is offline. `tests/fakes.py` provides deterministic OAuth and multi-repository GitHub doubles with a distinctive token canary. Playwright starts explicit loopback servers at `127.0.0.1:18000` and `127.0.0.1:13000`, writes process logs under `frontend/e2e/.logs/`, and uses a real temporary SQLite database to verify restart durability.
