# Release Manager

A FastAPI workflow service and responsive Next.js operator dashboard for evidence-based, human-governed GitHub releases.

## Local setup and run

```bash
./init.sh
export GITHUB_OAUTH_CLIENT_ID=... GITHUB_OAUTH_CLIENT_SECRET=...
export GITHUB_OAUTH_CALLBACK_URL=http://127.0.0.1:13000/auth/github/callback
export SESSION_SECRET='a-long-random-secret'
export RELEASE_MANAGER_WEB_URL=http://127.0.0.1:13000
export RELEASE_MANAGER_API_URL=http://127.0.0.1:8000
export RELEASE_MANAGER_DB=/var/lib/release-manager/state.db # optional
.venv/bin/uvicorn src.app:app --host 127.0.0.1 --port 8000
npm --prefix frontend run dev -- --hostname 127.0.0.1 --port 13000
```

Open **http://127.0.0.1:13000/settings/github**, choose **Continue with GitHub**, authorize the `repo` scope, and select a repository. Dashboard routes are `/`, `/releases`, `/operations`, `/settings/github`, and `/settings/schedule`; release details are `/releases/{id}`. Backend health is **http://127.0.0.1:8000/health**. `RELEASE_MANAGER_API_URL` is server-only; never expose secrets through `NEXT_PUBLIC_` variables.

The singleton schedule has five cron fields and runs in UTC. Standalone FastAPI owns an in-process scheduler; `SCHEDULER_INTERVAL_SECONDS` controls its polling interval. Navigation and refresh are read-only: only **Scan now** or a due enabled schedule starts a scan. Operations, leases, scans, release packs, decisions, publication attempts, reconciliation, audit records, OAuth tokens, and repository selection are persistent. Approval requires an actor and reason and immediately attempts publication. An uncertain publication must be reconciled before retrying.

## Deploy to Vercel

This repository is configured as one Vercel project by `vercel.json`: Next.js builds from `frontend/`, while `api/index.py` exposes FastAPI with its background scheduler disabled. Vercel Cron calls `/api/cron/scheduler`, whose server-side route verifies both the bearer secret and Vercel cron marker before forwarding to `POST /scheduler/tick`. Do not run a separate always-on worker.

1. Import the repository into Vercel using the Next.js framework preset. The configured install/build commands are `npm --prefix frontend ci` and `npm --prefix frontend run build`; the root `requirements.txt` supplies Python dependencies.
2. Provision a Vercel-compatible managed Postgres database and set `DATABASE_URL` or `POSTGRES_URL`. Production starts empty; there is no SQLite-to-Postgres import. Reconnect GitHub and select a repository after cutover.
3. Set `RELEASE_MANAGER_WEB_URL=https://<production-domain>`, server-only `RELEASE_MANAGER_API_URL=https://<production-domain>/_api`, `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET`, `GITHUB_OAUTH_CALLBACK_URL=https://<production-domain>/auth/github/callback`, `SESSION_SECRET`, and `CRON_SECRET`. `.env.example` documents all names. Never put the client secret, session secret, cron secret, database URL, internal API URL, or GitHub token in a `NEXT_PUBLIC_` variable.
4. In the GitHub OAuth App set Homepage URL to `https://<production-domain>` and Authorization callback URL to `https://<production-domain>/auth/github/callback`.
5. Keep the cron declaration in `vercel.json` and configure `CRON_SECRET` in Vercel. The application additionally requires the `x-vercel-cron` marker (overridable with `VERCEL_CRON_HEADER`).
6. Configure an uptime/readiness probe for **https://<production-domain>/health**, which returns `{"status":"ok"}`. Data migrations run during application startup; a database failure causes startup/request failure rather than reporting data-layer readiness.
7. Keep the configured function duration above the outbound GitHub client's 20-second timeout. Serverless instances are stateless and concurrent; Postgres is the sole production persistence layer.

Migrations are additive, versioned, automatic, idempotent, and serialized with a Postgres advisory transaction lock (SQLite uses an immediate transaction). They can also be run explicitly and repeatedly:

```bash
# with the same required OAuth/origin variables and DATABASE_URL in the environment
.venv/bin/python -m src.migrate
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
