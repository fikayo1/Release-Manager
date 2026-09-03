# Release Manager operations

See [`README.md`](../README.md) for local startup and the complete Vercel deployment guide. Locally, open `http://127.0.0.1:13000/settings/github`; in production open `https://<production-domain>/settings/github`. Health is `GET /health`.

The Vercel entrypoint `api/index.py` disables the lifespan polling scheduler. Scheduled work there runs only when Vercel Cron sends `GET /api/cron/scheduler` with its `Authorization: Bearer <CRON_SECRET>` and documented `User-Agent: vercel-cron/1.0`; the route verifies both before forwarding to protected `POST /scheduler/tick`. Standalone `uvicorn src.app:app` retains the in-process UTC scheduler.

Production persistence requires managed Postgres selected by `DATABASE_URL` or `POSTGRES_URL`. A production cutover starts empty; there is no SQLite import. Automatic versioned migrations are idempotent and serialized under a Postgres advisory transaction lock. From the repository root, an operator may safely run them explicitly with `PYTHONPATH=backend .venv/bin/python -m src.migrate`. SQLite selected by the absence of both URLs is for local development and CI; its database includes OAuth credentials and must be protected and backed up.

GitHub access is OAuth-only. The callback is the web-origin `/auth/github/callback`; the Next.js route forwards the opaque HttpOnly session cookie to FastAPI. A selected repository is captured on each scan, so later selection changes affect only future scans and never retarget existing publication or reconciliation work.

## Per-user isolation, token encryption, and concurrency

One authenticated GitHub account is one user. There is no shared organization,
team, or application role. Every domain row (GitHub connection, OAuth tokens,
repository selection, scans, packs, decisions, schedule, operations, audit) is
owned by a `user_id`. Protected API routes return `401` without a session, a
generic `403` across users, and `429` at the scan-concurrency limit; protected
dashboard routes redirect unauthenticated browsers to `/settings/github`.

OAuth access and refresh tokens are **encrypted at rest** with a stdlib-only
authenticated construction (`src/crypto.py`). The key comes from
`TOKEN_ENCRYPTION_KEY`, or is derived from `SESSION_SECRET` when that variable
is unset; rotating `TOKEN_ENCRYPTION_KEY` re-keys token storage without
touching the session key. The deprecated singleton accessors are not used by
the application; only `store.user_github_credentials(user_id)` decrypts a
credential, server-side, for that same user.

`MAX_CONCURRENT_SCANS` (integer `1..10`, clamped, default `1`) caps concurrent
in-flight scans per user. Trusted scheduled scans authenticate with
`CRON_SECRET` and are exempt from that per-user cap.

The legacy `GITHUB_TOKEN` / `GITHUB_OWNER` / `GITHUB_REPO` triple is a
topology-compatibility artifact only and is ignored by the OAuth path.

Approval and rejection require an actor and reason. Approval immediately publishes. An uncertain publish must be reconciled before retrying. Navigation is read-only; explicit **Scan now** or a due schedule starts work. Inspect `/operations`, `/releases`, and backend `GET /api/audit` for durable outcomes and receipts.
