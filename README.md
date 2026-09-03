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

Open **http://127.0.0.1:13000/**, the public marketing landing page, then **http://127.0.0.1:13000/login** and choose **Continue with GitHub**, authorize the `repo` scope, and select a repository on **/dashboard/settings/github**. Completing OAuth lands you on **/dashboard**. The authenticated console lives under `/dashboard`: `/dashboard` (overview), `/dashboard/releases`, `/dashboard/operations`, `/dashboard/settings/github`, and `/dashboard/settings/schedule`; release details are `/dashboard/releases/{id}`. `/` and `/login` are public and render with no session. Backend health is **http://127.0.0.1:8000/health**. `RELEASE_MANAGER_API_URL` is server-only; never expose secrets through `NEXT_PUBLIC_` variables.

Each connected GitHub user has an independent five-field UTC schedule. Standalone FastAPI owns an in-process scheduler; `SCHEDULER_INTERVAL_SECONDS` controls its polling interval. Navigation and refresh are read-only: only **Scan now** or a due enabled schedule starts a scan. Operations, leases, scans, release packs, decisions, publication attempts, reconciliation, audit records, OAuth tokens, and repository selection are persistent and user-owned. Approval requires an actor and reason and immediately attempts publication. An uncertain publication must be reconciled before retrying.

## Deploy to Vercel

Deploy this repository as **two Vercel projects**. This is still Vercel-only: separating the Next.js console from FastAPI avoids the route collision that occurs when a Next output and a Python function share one Vercel project.

1. Create the **Release Manager API** project with Root Directory `backend`. Its native Vercel Python entrypoint is `api/index.py`; the API project's own rewrite sends public API paths to that function. This is not a bridge to the separate Next.js Console project. Configure `DATABASE_URL` (or `POSTGRES_URL`), `RELEASE_MANAGER_WEB_URL=https://<console-domain>`, `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET`, `GITHUB_OAUTH_CALLBACK_URL=https://<console-domain>/auth/github/callback`, `SESSION_SECRET`, and `CRON_SECRET`. Use `backend/.env.example` as the non-secret checklist. If an existing API project was created at the repository root, the root `pyproject.toml` explicitly selects `backend.api.index:app`; redeploy after pulling rather than relying on FastAPI auto-detection.
2. Create the **Release Manager Console** project with Root Directory `frontend`. Configure `RELEASE_MANAGER_API_URL=https://<api-domain>` and the same `CRON_SECRET`; `frontend/.env.example` lists only those values. Do not expose any value through `NEXT_PUBLIC_` variables.
3. In the GitHub OAuth App set Homepage URL to `https://<console-domain>` and Authorization callback URL to `https://<console-domain>/auth/github/callback`.
4. The Console project's Vercel Cron invokes `GET /api/cron/scheduler`, verifies Vercel's `User-Agent: vercel-cron/1.0` and `CRON_SECRET`, then forwards a trusted `POST /scheduler/tick` to the API project. On Vercel Hobby its schedule is once daily at `0 9 * * *` (09:00 UTC; 10:00 Lagos). **Scan now** remains the primary trigger.
5. Probe **https://<api-domain>/health**. It returns `{"status":"ok"}` only once configuration and database initialization succeed.

Migrations are additive, versioned, automatic, idempotent, and serialized with a Postgres advisory transaction lock (SQLite uses an immediate transaction). They can also be run explicitly and repeatedly:

```bash
# with the same required OAuth/origin variables and DATABASE_URL in the environment
PYTHONPATH=backend .venv/bin/python -m src.migrate
```

After deployment, open **https://<production-domain>/login**, click **Continue with GitHub**, authorize, land on `/dashboard`, open **/dashboard/settings/github**, confirm **Connected as**, select a repository, click **Scan now** on `/dashboard`, and confirm that a draft appears under `/dashboard/releases`.

Without `DATABASE_URL`/`POSTGRES_URL`, SQLite remains the local/CI fallback. Back it up before upgrades and restrict/encrypt backups because it contains OAuth tokens. In production use HTTPS; the session cookie is HttpOnly, SameSite=Lax, and Secure. There is no application role gate, so restrict network access.

## Route policy and the multi-user model

**Public routes** (no session required): `GET /health`, `GET /auth/github`,
`GET /auth/github/callback`, and the Cron boundary `GET /api/cron/scheduler`
(`CRON_SECRET` + `User-Agent: vercel-cron/1.0`). The internal
`POST /scheduler/tick` is reachable only with a valid `CRON_SECRET` and is not
subject to the browser same-origin check.

**Protected routes** are bound to one identity. Identity is a single GitHub
account: one authenticated GitHub account is exactly one user, and there is no
shared organization, team, or application role anywhere. A user's GitHub
connection, OAuth tokens, repository selection, scans, release packs, decisions,
schedule, operations, and audit are per-user. Protected API routes answer
`401` without a session, a generic `403` for a cross-user resource, and `429`
when the caller is at the scan-concurrency limit. Protected dashboard routes
(everything under `/dashboard`) redirect to `/login` when the browser has no
session and never render another user's data; `/` and `/login` are public.
Completing OAuth redirects to `/dashboard`; an OAuth failure redirects to
`/login?error=<status>`.

**Token protection.** OAuth access and refresh tokens never leave the FastAPI
process, are **encrypted at rest** (stdlib-only authenticated encryption; key
from `TOKEN_ENCRYPTION_KEY`, or derived from `SESSION_SECRET` when unset), and
never appear in browser payloads or logs. `RELEASE_MANAGER_API_URL` is
server-only and there are no `NEXT_PUBLIC_` variables.

**Scan concurrency.** `MAX_CONCURRENT_SCANS` bounds the number of concurrent
in-flight scans per user (integer `1..10`; out-of-range values are clamped;
the Vercel deployment uses `1`). A manual scan over the limit is refused with
`429` and makes no GitHub call. Trusted scheduled scans authenticate with
`CRON_SECRET` and are exempt from this per-user cap.

**Environment variable names** (values live only in your deployment settings):

- Backend: `DATABASE_URL` or `POSTGRES_URL`, `RELEASE_MANAGER_WEB_URL`,
  `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET`,
  `GITHUB_OAUTH_CALLBACK_URL`, `SESSION_SECRET`, `CRON_SECRET`,
  `MAX_CONCURRENT_SCANS` (optional, default `1`), `TOKEN_ENCRYPTION_KEY`
  (optional). Standalone-only: `SCHEDULER_INTERVAL_SECONDS`, `RELEASE_MANAGER_DB`.
- Frontend: `RELEASE_MANAGER_API_URL` (server-only) and `CRON_SECRET`
  (identical to the backend value).

**`GITHUB_TOKEN` / `GITHUB_OWNER` / `GITHUB_REPO`** are legacy
topology-compatibility names only. They are **not** shared production
authorization for multi-user operation and are ignored by the OAuth path.

**Two Vercel projects.** The `backend` root (FastAPI, `api/index.py`, with its
own self-contained rewrite) and the `frontend` root (Next.js plus the Cron
proxy) deploy as separate projects. One Next.js deployment does not and cannot
route to the Python function through Next rewrites; the console reaches the API
only through the server-only `RELEASE_MANAGER_API_URL`.

## Verification

Browser binaries are provisioned once by an operator with `shipyard setup --browser-tests`, never by package scripts.

```bash
.venv/bin/python -m pytest -q
npm --prefix frontend test
npm --prefix frontend run test:e2e
npm --prefix frontend run build
```

Acceptance is offline. `tests/fakes.py` provides deterministic OAuth and multi-repository GitHub doubles with a distinctive token canary. Playwright starts explicit loopback servers at `127.0.0.1:18000` and `127.0.0.1:13000`, writes process logs under `frontend/e2e/.logs/`, and uses a real temporary SQLite database to verify restart durability.
