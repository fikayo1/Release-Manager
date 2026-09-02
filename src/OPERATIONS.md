# Release Manager operations

See [`README.md`](../README.md) for local startup and the complete Vercel deployment guide. Locally, open `http://127.0.0.1:13000/settings/github`; in production open `https://<production-domain>/settings/github`. Health is `GET /health`.

The Vercel entrypoint `api/index.py` disables the lifespan polling scheduler. Scheduled work there runs only when Vercel Cron sends `GET /api/cron/scheduler` with its `Authorization: Bearer <CRON_SECRET>` and documented `User-Agent: vercel-cron/1.0`; the route verifies both before forwarding to protected `POST /scheduler/tick`. Standalone `uvicorn src.app:app` retains the in-process UTC scheduler.

Production persistence requires managed Postgres selected by `DATABASE_URL` or `POSTGRES_URL`. A production cutover starts empty; there is no SQLite import. Automatic versioned migrations are idempotent and serialized under a Postgres advisory transaction lock. An operator may safely run them explicitly with `.venv/bin/python -m src.migrate`. SQLite selected by the absence of both URLs is for local development and CI; its database includes OAuth credentials and must be protected and backed up.

GitHub access is OAuth-only. The callback is the web-origin `/auth/github/callback`; the Next.js route forwards the opaque HttpOnly session cookie to FastAPI. A selected repository is captured on each scan, so later selection changes affect only future scans and never retarget existing publication or reconciliation work.

Approval and rejection require an actor and reason. Approval immediately publishes. An uncertain publish must be reconciled before retrying. Navigation is read-only; explicit **Scan now** or a due schedule starts work. Inspect `/operations`, `/releases`, and backend `GET /api/audit` for durable outcomes and receipts.
