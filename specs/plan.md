# Production hardening for Release Manager — implementation plan

> This plan supersedes the earlier "GitHub OAuth and repository-targeting
> completion" plan (kept in git history). That increment is delivered:
> `tests/fakes.py`, `tests/e2e_app.py`, `tests/test_oauth_flow.py`,
> `tests/test_repository_targeting.py`, `frontend/e2e/oauth.spec.ts`, and
> `frontend/e2e/repository-targeting.spec.ts` already exist and pass. This
> increment turns the single-tenant service into a multi-user product while
> keeping the two deployable roots (`backend` FastAPI, `frontend` Next.js) and
> every existing route path, screen, and workflow state.
>
> Designed against `criteria.json` C1–C8 (unedited). No implementation code is
> written in this phase.

## Objective

Close C1–C8 without redesigning the product surface:

1. **C1 dashboard resilience** — `/`, `/releases`, `/operations` always settle
   into content or a bounded, retryable error; never an indefinite spinner.
2. **C2 state-change protection** — every scan trigger and mutating route
   enforces authentication (401), ownership (generic 403), same-origin request
   protection, and a per-user scan-concurrency limit (429, no GitHub call);
   trusted scheduled scans stay `CRON_SECRET`-only and concurrency-exempt.
3. **C3 identity isolation** — two independently authenticated GitHub accounts
   have isolated connections, repositories, records, actions, and
   encrypted-at-rest tokens; the token canary is never plaintext in the DB,
   browser payloads, or logs.
4. **C4 route matrix** — every sidebar route, `/releases/{id}`, and the
   `/github` / `/schedule` compatibility aliases are directly loadable and
   refresh-safe.
5. **C5 pack idempotency** — release packs are unique per (user, repository,
   version); rescan updates/reuses the current pack; scan + audit history is
   retained.
6. **C6 polished operations** — human-readable operation labels + timestamps,
   `GET /api/scans` (401 unauthenticated, own-scans-only authenticated), ≥24px
   mobile interactive targets, accessible skeleton and error/retry states.
7. **C7 operator docs** — route policy, one-account-per-user identity boundary,
   token protection, concurrency limit, scheduler auth + exemption, all
   environment-variable **names**, migration + verification steps, two Vercel
   project roots with a server-only backend URL, and the legacy/compatibility
   status of `GITHUB_TOKEN` / `GITHUB_OWNER` / `GITHUB_REPO`. No values.
8. **C8 offline verification** — all four gates pass with no deployment and no
   cloud resource creation.

## Current state (what exists and constrains the design)

- **No user concept.** `github_connection`, `schedules`, `scheduler_state`, and
  `scan_lease` are hard singletons (`id=1 CHECK(id=1)`). `scans`, `packs`,
  `operations`, `decisions`, `attempts`, `reconciliations`, `audit` have no
  owner column. `store.audit()` and `GET /` return **global** audit.
- **Session cookie already exists.** `OAuthService` issues a signed, opaque,
  HttpOnly `release_manager_session` cookie (SameSite=Lax, Secure when
  `web_url` is https). Today it only binds OAuth `state`; it is never mapped to
  an identity, and `lib/api.ts` / most Next route handlers **do not forward it**
  to FastAPI.
- **Tokens are plaintext.** `github_connection.access_token` is stored raw;
  `store.github_connection()` already excludes credential columns from the
  browser-facing view, and `store.github_credentials()` returns the raw token
  server-side only.
- **Scan concurrency** is a single global lease in `OperationRunner` /
  `store.acquire_lease` (`scan_lease` singleton). Scheduled and manual scans
  share it. `Scheduler` evaluates one global schedule.
- **Repository targeting** is captured on the `Scan` and re-resolved for pack
  actions via `client_for_pack` — this behavior must be preserved per-user.
- **Deploy topology** is already two Vercel roots: `backend/vercel.json`
  rewrites `/(.*)` → its own `api/index.py`; `frontend/vercel.json` has only the
  Next build + the cron proxy; `RELEASE_MANAGER_API_URL` is `server-only`
  (`lib/api.ts` imports `server-only`). `tests/test_deployment_config.py`
  guards this. **Preserve it exactly.**
- **Fakes** in `tests/fakes.py` provide one OAuth identity, `CANARY_TOKEN`,
  `REPO_A`/`REPO_B`, a `Journal`, and `seed_pack`. `tests/e2e_app.py` exposes
  `/test/*` controls and runs a real on-disk SQLite DB.
- **Gates** (from `init.sh`): `.venv/bin/python -m pytest -q` &&
  `npm --prefix frontend test` && `npm --prefix frontend run test:e2e` &&
  `npm --prefix frontend run build`.

## Design decisions (read before implementing)

- **Identity = one GitHub account.** A `users` row keyed by GitHub `account_id`
  (unique, immutable). OAuth callback upserts the user and binds the current
  signed session → `user_id` in a persistent `sessions` table. No orgs, teams,
  or roles anywhere. Missing/invalid session → **401**; valid session acting on
  another user's resource → **generic 403** with no resource detail.
- **Same-origin protection.** Mutating routes (`POST`/`PUT`/`DELETE`) require an
  `Origin` (fallback `Referer`) header whose scheme+host matches
  `RELEASE_MANAGER_WEB_URL`. Every Next route handler forwards the browser
  `origin` and `cookie` headers to FastAPI. `POST /scheduler/tick` is exempt
  (authenticated by `CRON_SECRET` + Vercel proof header, unchanged).
- **Scan concurrency.** New `MAX_CONCURRENT_SCANS` setting: default **1**,
  validated to `1..10` (out-of-range → clamp + a startup-safe note; never
  crash health). `scan_lease` generalized to allow up to N rows **per user**;
  `POST /api/scans` (and the backend scan alias) refuse with **429** and make
  **no GitHub call** when the user is at the limit. `source="scheduled"` runs
  (only reachable through `CRON_SECRET`) bypass the per-user counter and keep
  their existing durable per-slot uniqueness. Each user has an independent
  allowance.
- **Token encryption at rest.** New `src/crypto.py` using the Python standard
  library only (no new dependency): per-record random nonce, an
  HMAC-SHA256–derived keystream (CTR construction) for confidentiality, and an
  HMAC-SHA256 tag for integrity. Key material comes from `TOKEN_ENCRYPTION_KEY`
  if set, otherwise an HKDF-style derivation from the already-required
  `SESSION_SECRET` with a fixed domain-separation label. `github_credentials()`
  decrypts; `github_connection()` still never returns credential columns.
  Stored `access_token` / `refresh_token` ciphertext is opaque base64 — the
  canary string never appears verbatim in the DB file.
- **Pack idempotency.** Add a partial unique index on
  `packs(user_id, repository, version)` for the *current* (non-superseded)
  pack. `draft()` becomes an upsert: if a current pack already exists for that
  (user, repo, version) it is updated/reused (same `id`), not duplicated; the
  new `scan` row and all `audit` rows are still written. `repository` is copied
  onto the pack from its scan.
- **Dashboard resilience.** `lib/api.ts` keeps `cache:'no-store'` (stable,
  predictable) and adds an `AbortController` timeout (~8s, below C1's 10s
  budget) so a hung backend rejects instead of suspending forever. 401 →
  typed `UnauthorizedError`; server components catch it and
  `redirect('/settings/github')`. Other failures propagate to a route
  `error.tsx` boundary. Skeletons use fixed dimensions (no layout shift),
  `role="status"`, `aria-busy`, and meaningful text; error states use
  `role="alert"` and a `Retry` button wired to `reset()`.
- **Route aliases.** `/github` → `/settings/github` and `/schedule` →
  `/settings/schedule` via `next.config.mjs` `redirects()` (307, refresh- and
  bookmark-safe). Unauthenticated protected UI routes redirect to
  `/settings/github` via `middleware.ts` (cookie-presence check) with page-level
  401→redirect as defense in depth.
- **Migrations stay additive.** One new version (4) with parallel SQLite and
  Postgres statement lists; idempotent; run under the existing advisory lock.
  Existing rows backfill to a single synthetic `legacy` user so SQLite
  dev/CI data remains queryable; production Postgres starts empty.
- **Never** deploy, invent credentials, or write secret values into any file.

## Files to create

### Backend — source

- `backend/src/identity.py`
  - `SessionError` (→ 401) and `OwnershipError` (→ 403, generic message).
  - `current_user(request)` FastAPI dependency: read + verify the signed
    session cookie via `request.app.state.oauth`, resolve
    `store.user_for_session(session_id)`; raise `SessionError` if absent.
  - `require_same_origin(request)` dependency: compare `Origin`/`Referer` to
    `settings.web_url`; raise `OwnershipError`/400 on mismatch.
  - `owned_pack(request, user, pack_id)` / `owned_operation(...)` helpers that
    raise `OwnershipError` when the record's `user_id` differs.
- `backend/src/crypto.py`
  - `encrypt_token(plaintext, *, settings) -> str` / `decrypt_token(...)`,
    stdlib-only, versioned ciphertext prefix, random nonce, integrity tag.
  - `token_key(settings)` — use `TOKEN_ENCRYPTION_KEY` or derive from
    `SESSION_SECRET`.

### Backend — tests (offline, deterministic, real temp DB)

- `tests/test_identity_isolation.py` — **C3**: two users via the two-account
  fake OAuth; disjoint repositories and scans; each API session sees only its
  own connection, `GET /api/github`, `GET /api/scans`, `/api/releases`,
  `/api/operations`, `/api/audit`; cross-user read/scan/approve/reject/publish
  all return generic 403 and change nothing (no record mutation, no GitHub
  call); no org/team/role path exists.
- `tests/test_scan_concurrency.py` — **C2**: `POST /api/scans` and the backend
  scan alias with no session → 401 + zero GitHub calls; at
  `MAX_CONCURRENT_SCANS=1` a second concurrent user scan → 429 + zero GitHub
  calls; `MAX_CONCURRENT_SCANS` accepts 1..10 and a value >10 is clamped;
  user B has an independent allowance; a `CRON_SECRET` scheduled tick during an
  active user scan runs and is not counted; scheduled tick still 403s without a
  valid `CRON_SECRET`.
- `tests/test_same_origin.py` — **C2**: repository selection, scan start,
  schedule change, approve, reject, publish, reconcile each reject a
  cross-origin / missing-origin request and accept a matching-origin request;
  `/scheduler/tick` is unaffected by Origin.
- `tests/test_pack_idempotency.py` — **C5**: two identical deterministic scans
  for one (user, repo, version) leave exactly one current pack and no duplicate
  in `/api/releases`; both scans and their audit rows remain queryable; a
  second user (or repo) at the same version gets a distinct current pack
  without touching the first.
- `tests/test_operations_view.py` — **C6 backend half**: `GET /api/scans`
  returns 401 unauthenticated and only the caller's scans authenticated;
  operation records expose the fields the UI needs for a human label + a
  timestamp for every operation (including `legacy` backfill rows).
- `tests/test_token_encryption.py` — **C3**: after OAuth the on-disk SQLite
  file bytes do not contain `CANARY_TOKEN`; `store.github_credentials()`
  round-trips to `CANARY_TOKEN`; `store.github_connection()` still has no
  credential columns; `crypto` rejects a tampered ciphertext.
- `tests/test_migrations_multiuser.py` — migration 4 is additive and
  idempotent for both dialects (run twice = no-op); legacy rows are backfilled
  to one `legacy` user; new unique indexes exist.
- `tests/test_docs_policy.py` — **C7**: README + `OPERATIONS.md` mention public
  vs protected routes, one-account-per-user ownership, token protection, the
  scan concurrency limit, scheduler `CRON_SECRET` auth + exemption, separate
  `backend`/`frontend` Vercel roots, `RELEASE_MANAGER_API_URL` server-only,
  every required env var name, `python -m src.migrate`, the four verification
  commands, and the legacy status of `GITHUB_TOKEN`/`GITHUB_OWNER`/
  `GITHUB_REPO`; and that no `ghp_`/`ghs_`/long-secret material is present.

### Frontend — source

- `frontend/middleware.ts` — redirect unauthenticated requests for protected
  paths (`/`, `/releases`, `/operations`, `/settings/*`, `/releases/*`) to
  `/settings/github`; leave `/settings/github`, `/auth/*`, static assets, and
  API routes alone.
- `frontend/lib/labels.ts` — `operationTitle(op)`, `sourceLabel(source)`,
  `statusLabel(value)` mapping raw tokens (`non_release`, `draft_created`,
  `reconnect_required`, `manual`, `scheduled`, `legacy`, …) to human wording.
- `frontend/lib/guard.ts` — `loadOrRedirect(fn)` helper: run an `api()` call,
  catch `UnauthorizedError` → `redirect('/settings/github')`, rethrow the rest.
- `frontend/components/Skeleton.tsx` — accessible, fixed-dimension skeleton
  blocks (`role="status"`, `aria-busy`, visually-hidden label), honoring
  `prefers-reduced-motion`.
- `frontend/components/RetryableError.tsx` — `role="alert"` message + `Retry`
  button (≥24px) calling the passed `reset()`.
- `frontend/app/releases/loading.tsx`, `frontend/app/releases/error.tsx`
- `frontend/app/operations/loading.tsx`, `frontend/app/operations/error.tsx`

### Frontend — tests

- `frontend/lib/api.test.ts` — `api()` forwards the incoming `cookie`, applies
  the abort timeout (rejects, does not hang), maps 401 → `UnauthorizedError`,
  409/429 → typed errors with the server `detail`.
- `frontend/lib/labels.test.ts` — every raw token maps to human wording; the
  string `Non Release manual` never appears.
- `frontend/e2e/dashboard-resilience.spec.ts` — **C1**: with a seeded
  authenticated session, directly load + reload + fresh-navigate `/`,
  `/releases`, `/operations` ≥10× each, all render expected data; with the
  backend put in `delay` then `fail` mode via `/test/backend/mode`, an
  accessible skeleton appears with no material layout movement and the route
  reaches its error state within 10s; restoring the backend and activating
  `Retry` renders data without a full browser reload.
- `frontend/e2e/identity-isolation.spec.ts` — **C3**: two browser contexts sign
  in as the two fake accounts; each sees only its repositories, scans, packs,
  operations; cross-user navigation/actions are denied and mutate nothing;
  token canary absent from every response body, rendered HTML, Web Storage,
  console, and the captured server logs.
- `frontend/e2e/route-matrix.spec.ts` — **C4**: authenticated direct load +
  refresh of `/`, `/releases`, `/operations`, `/settings/github`,
  `/settings/schedule`, a valid `/releases/{id}` → none 404; `/github` and
  `/schedule` resolve/redirect to their settings page with a usable
  refresh/bookmark URL; every sidebar link lands on the intended page.
- `frontend/e2e/mobile-targets.spec.ts` — **C6**: at a 390px viewport the
  sidebar, retry, scan, decision, and settings controls each measure ≥24×24
  CSS px; the skeleton and the error/retry state expose meaningful accessible
  text to keyboard/AT inspection.

## Files to update

### Backend

- `backend/src/migrations.py` — **migration 4** (sqlite + postgres):
  - `users(id TEXT PK, github_account_id TEXT UNIQUE NOT NULL, login TEXT, created_at TEXT)`.
  - `sessions(session_id TEXT PK, user_id TEXT NOT NULL REFERENCES users(id), created_at TEXT, last_seen_at TEXT)`.
  - Add `user_id` to `github_connection` (drop the `id=1` singleton: PK becomes
    `user_id`), `scans`, `packs`, `operations`, `schedules` (per-user singleton
    keyed by `user_id`), `scheduler_state`, `scan_lease` (composite PK
    `(user_id, operation_id)`), `audit`. `decisions`/`attempts`/
    `reconciliations` inherit ownership through `packs`.
  - Partial unique index `packs(user_id, repository, version)` for current
    packs; keep the `scheduled_for` slot index but scope it per user.
  - `oauth_states` already carries `session_id` — no change.
  - Legacy backfill: create one `legacy` user, assign every pre-existing row to
    it (SQLite path only; Postgres cutover starts empty).
- `backend/src/store.py` — thread `user_id` through every read/write; new:
  `upsert_user`, `bind_session`, `user_for_session`, `scans_for_user`,
  `active_scan_count(user_id)`, per-user `acquire_lease`/`release_lease`,
  per-user `github_connection`/`github_credentials`/`select_repository`/
  `save_github_connection` (encrypt on write, decrypt on
  `github_credentials`), per-user `schedule`/`update_schedule`/
  `scheduler_state`, `audit(user_id)`, pack upsert-by-identity in `save_pack`.
- `backend/src/routes.py` —
  - Attach `current_user` to every protected route; add `require_same_origin`
    to every mutating route.
  - New `GET /api/scans` → `store.scans_for_user(user.id)` (401 unauthenticated).
  - `POST /api/scans` + review-form scan alias: check
    `store.active_scan_count(user.id) < settings.max_concurrent_scans` before
    any GitHub work; else `HTTPException(429)`.
  - `client_for_pack`, pack actions, operation reads: ownership-checked → 403.
  - Keep `/health`, `/auth/github`, `/auth/github/callback`, `/scheduler/tick`
    public per their current policy; scope `GET /` to the caller (or reduce to
    `{"service": "release-manager"}` when unauthenticated) so it never leaks
    another user's audit.
  - Map `SessionError`→401, `OwnershipError`→403 via exception handlers.
- `backend/src/github_oauth.py` — in the callback path (or a thin hook the
  route calls) `store.upsert_user(account)` then
  `store.bind_session(session_id, user_id)`. Session/cookie signing unchanged.
- `backend/src/operations.py` — `OperationRunner` takes `user_id`; resolves
  *that user's* `github_connection().selected_repository`; per-user lease;
  `create_operation`/`finish_operation` carry `user_id`; scheduled path passes
  the schedule owner's `user_id` and skips the per-user concurrency counter.
- `backend/src/scheduler.py` — iterate enabled per-user schedules; evaluate and
  claim each due user's slot independently; scheduled runs stay
  concurrency-exempt; `scheduler_state` updated per user.
- `backend/src/phases/scan.py`, `backend/src/phases/draft.py`,
  `backend/src/pack.py` — carry `user_id` + `repository` into the scan and into
  the idempotent pack upsert.
- `backend/src/config.py` — add `max_concurrent_scans: int = 1` (env
  `MAX_CONCURRENT_SCANS`, validate/clamp to 1..10) and
  `token_encryption_key: str = ""` (env `TOKEN_ENCRYPTION_KEY`, optional);
  keep `__repr__` redaction (`token_encryption_key` → `'***'`).
- `backend/src/app.py` — pass the new settings through; `github_provider`
  becomes `provider(user_id, slug)`; wire `current_user`/exception handlers.
- `backend/src/migrate.py` — no logic change; covered by the new migration test.
- `backend/.env.example` — add `MAX_CONCURRENT_SCANS=` and
  `TOKEN_ENCRYPTION_KEY=` (names + placeholder comments only); note
  `MAX_CONCURRENT_SCANS=1` for the current Vercel deployment.
- `backend/api/index.py` — unchanged (re-verify it still just re-exports
  `create_app(enable_scheduler=False)`).

### Backend — shared fakes / e2e app

- `tests/fakes.py` — add a second OAuth identity (`FakeAccountGitHubB`, e.g.
  `login="oauth-fixture-b"`, `id=43`, repos `fixture/repo-b-1`,
  `fixture/repo-b-2` disjoint from user A's `REPO_A`/`REPO_B`); a second
  distinct `CANARY_TOKEN_B`; `FakeOAuth` selects the identity by an `account`
  query param on `/test/github/authorize`; `seed_pack(store, ..., user_id=...)`;
  keep the single-identity helpers working for the existing OAuth/targeting
  specs.
- `tests/e2e_app.py` — accept `?account=a|b` through `/test/github/authorize`;
  add `POST /test/backend/mode` (`normal` | `delay:<ms>` | `fail`) implemented
  as middleware for C1; make `/test/seed` and `/test/scheduler/tick` user-aware;
  keep the existing `/test/*` endpoints. DB reset behavior and `E2E_KEEP_DB`
  unchanged.

### Frontend

- `frontend/lib/api.ts` — forward the request `cookie` (via `next/headers`) and
  a same-origin `origin` header to FastAPI; add an `AbortController` timeout;
  map 401→`UnauthorizedError`, 403→`ForbiddenError`, 429→`RateLimitedError`;
  keep `import 'server-only'` and `cache:'no-store'`.
- `frontend/app/api/*/route.ts` (`scans`, `github/repository`, `schedule`,
  `releases/[id]/approve`, `releases/[id]/reject`, and new GET on `scans`) —
  forward `cookie` + `origin` headers; pass through 401/403/429 with the
  upstream `detail`; add `GET` to `scans/route.ts` proxying `GET /api/scans`.
- `frontend/app/page.tsx`, `frontend/app/releases/page.tsx`,
  `frontend/app/operations/page.tsx`, `frontend/app/releases/[id]/page.tsx`,
  `frontend/app/settings/github/page.tsx`,
  `frontend/app/settings/schedule/page.tsx` — load through `loadOrRedirect`;
  render human labels + a timestamp for every operation on the overview and
  Operations pages.
- `frontend/app/loading.tsx`, `frontend/app/error.tsx` — replace the one-line
  placeholders with `Skeleton` / `RetryableError`.
- `frontend/components/AppNav.tsx` — ≥24px link targets, current-route
  `aria-current`; no alias links.
- `frontend/components/ScanNowButton.tsx` — surface a 429 as "Another scan is
  already running for your account"; ≥24px button.
- `frontend/components/GitHubRepositoryForm.tsx`,
  `frontend/components/DecisionForm.tsx`,
  `frontend/components/ScheduleForm.tsx` — ≥24px controls; pass through
  403/429 messages.
- `frontend/app/globals.css` — `min-height`/`min-width: 24px` (and adequate hit
  area) for `nav a`, `button`, `.button`, `select`, form controls, retry;
  skeleton classes with reserved dimensions; `@media (prefers-reduced-motion)`.
- `frontend/next.config.mjs` — `async redirects()` for `/github` →
  `/settings/github` and `/schedule` → `/settings/schedule`; keep
  `output: 'standalone'`.
- `frontend/e2e/dashboard.spec.ts` — adapt to the authenticated model (browser
  context now carries a session cookie); trim assertions now owned by the new
  specs; keep a smoke path.
- `frontend/e2e/oauth.spec.ts`, `frontend/e2e/repository-targeting.spec.ts`,
  `frontend/e2e/cron.spec.ts` — update `page.request.*` calls to carry the
  session cookie / a `CRON_SECRET` header as appropriate; behavior assertions
  unchanged.
- `frontend/playwright.config.ts` — add any new fixture env; keep
  `workers: 1`, `reuseExistingServer: false`, single non-skipping project, the
  `run-logged.mjs` wrappers, and the log paths.
- `frontend/.env.example` — unchanged (still only `RELEASE_MANAGER_API_URL` +
  `CRON_SECRET`); re-confirm the server-only comment.
- `frontend/vercel.json` — unchanged (cron `0 9 * * *`, no rewrites).
- `.gitignore` — add `frontend/e2e/.tmp/` if not already ignored.

### Documentation (C7)

- `README.md` — add/expand:
  - **Route policy**: public = `GET /health`, `GET /auth/github`,
    `GET /auth/github/callback`; protected UI routes redirect to
    `/settings/github` when unauthenticated and never render another user's
    data; protected API routes return 401 (no session) / 403 (cross-user) /
    429 (scan limit).
  - **Identity boundary**: one GitHub account = one user; no shared org, team,
    or application role; connections, tokens, repository selections, scans,
    packs, operations, decisions, schedules, and audit are per-user.
  - **Token protection**: OAuth tokens stay server-side, are encrypted at rest,
    and never appear in browser payloads or logs; `RELEASE_MANAGER_API_URL` is
    server-only; no `NEXT_PUBLIC_` variables.
  - **Scan concurrency**: `MAX_CONCURRENT_SCANS` (configurable 1..10; the
    Vercel deployment uses 1); excess user scans get 429 without calling
    GitHub; trusted scheduled scans require `CRON_SECRET` and are exempt.
  - **Environment-variable names** (no values): `DATABASE_URL` /
    `POSTGRES_URL`, `RELEASE_MANAGER_WEB_URL`, `GITHUB_OAUTH_CLIENT_ID`,
    `GITHUB_OAUTH_CLIENT_SECRET`, `GITHUB_OAUTH_CALLBACK_URL`, `SESSION_SECRET`,
    `CRON_SECRET`, `MAX_CONCURRENT_SCANS`, `TOKEN_ENCRYPTION_KEY` (optional),
    `RELEASE_MANAGER_API_URL` (frontend, server-only),
    `SCHEDULER_INTERVAL_SECONDS` + `RELEASE_MANAGER_DB` (standalone only).
  - **Two Vercel projects**: `backend` root (FastAPI, `api/index.py`,
    self-contained rewrite) and `frontend` root (Next.js + cron proxy). One
    Next deployment does **not** and cannot route to the Python function
    through rewrites; the console reaches the API only via the server-only
    `RELEASE_MANAGER_API_URL`.
  - **Migration + verification**: `PYTHONPATH=backend .venv/bin/python -m
    src.migrate` (additive, idempotent, advisory-locked); post-migration
    verification checklist; the four gate commands.
  - **`GITHUB_TOKEN` / `GITHUB_OWNER` / `GITHUB_REPO`**: legacy / local
    topology-compatibility variables only; they are **not** shared production
    authorization for multi-user operations and are ignored by the OAuth path.
- `backend/src/OPERATIONS.md` — one section on per-user isolation, the
  concurrency limit + scheduled exemption, encrypted token storage, and the
  legacy `GITHUB_TOKEN`/`GITHUB_OWNER`/`GITHUB_REPO` triple status.

## Deployment readiness

- **Build**
  - Backend: no build step; Vercel installs `backend/requirements.txt`
    (unchanged — stdlib crypto, no new dependency). Standalone/CI: `./init.sh`.
  - Frontend: `npm --prefix frontend run build` (`next build`,
    `output: 'standalone'`).
- **Start**
  - Backend standalone: `PYTHONPATH=backend .venv/bin/uvicorn src.app:app
    --host 127.0.0.1 --port 8000` (keeps the in-process per-user scheduler).
  - Backend on Vercel: `backend/api/index.py` →
    `create_app(enable_scheduler=False)`; scheduled work is driven by
    `POST /scheduler/tick`.
  - Frontend standalone: `npm --prefix frontend start`; on Vercel: the Next.js
    runtime plus the `/api/cron/scheduler` cron proxy.
- **Health / readiness**
  - `GET /health` → `{"status":"ok"}` only after configuration validation, DB
    connection, and migrations (now including version 4) succeed; otherwise
    `503 {"status":"unavailable", "kind": "configuration"|"database", ...}`
    with no secret values. Unchanged contract; migration set is larger.
  - Protected routes: 401 (no/invalid session), 403 (cross-user), 429 (scan
    limit). Protected UI routes redirect to `/settings/github` unauthenticated.
- **Required environment variables (names only)**
  - Backend: `DATABASE_URL` or `POSTGRES_URL`; `RELEASE_MANAGER_WEB_URL`;
    `GITHUB_OAUTH_CLIENT_ID`; `GITHUB_OAUTH_CLIENT_SECRET`;
    `GITHUB_OAUTH_CALLBACK_URL`; `SESSION_SECRET`; `CRON_SECRET`;
    `MAX_CONCURRENT_SCANS` (optional, default 1, range 1..10);
    `TOKEN_ENCRYPTION_KEY` (optional; derived from `SESSION_SECRET` if unset).
    Standalone-only: `SCHEDULER_INTERVAL_SECONDS`, `RELEASE_MANAGER_DB`.
  - Frontend: `RELEASE_MANAGER_API_URL` (server-only); `CRON_SECRET`
    (identical to backend). No `NEXT_PUBLIC_` variables.
  - Topology-compatibility only, **not** production auth: `GITHUB_TOKEN`,
    `GITHUB_OWNER`, `GITHUB_REPO`.
  - No secret values are placed in any tracked file; `.env.example` files carry
    names + placeholder comments only.
- **Persistence / runtime assumptions**
  - Production: managed Postgres (`DATABASE_URL` / `POSTGRES_URL`); every
    domain row is per-user; migrations are additive, idempotent, and serialized
    with the Postgres advisory transaction lock (SQLite: immediate
    transaction). Production cutover starts empty (no SQLite import).
  - Dev/CI: SQLite fallback; its file contains encrypted OAuth tokens and must
    still be access-restricted and backed up before upgrades.
  - OAuth access/refresh tokens are encrypted at rest; sessions are persisted
    server-side and bound to a `user_id`; the session cookie stays HttpOnly,
    SameSite=Lax, Secure on https origins.
  - Serverless has no always-on scheduler; Vercel Cron invokes
    `GET /api/cron/scheduler` (validates `CRON_SECRET` + `User-Agent:
    vercel-cron/1.0`) → forwards trusted `POST /scheduler/tick`, which
    evaluates every user's due slot. Vercel Hobby cron runs once daily
    (`0 9 * * *`); **Scan now** remains the primary trigger. The Vercel
    deployment sets `MAX_CONCURRENT_SCANS=1`.
- **Provider configuration / operator documentation the spec requires**
  - `README.md`: route policy, identity boundary, token protection, concurrency
    limit + scheduler exemption, all env-var names, two-project Vercel setup
    with a server-only backend URL, migration + verification instructions, and
    the legacy status of `GITHUB_TOKEN` / `GITHUB_OWNER` / `GITHUB_REPO`.
  - `backend/src/OPERATIONS.md`: per-user isolation, concurrency, encrypted
    tokens, `python -m src.migrate`.
  - GitHub OAuth App: Homepage `https://<console-domain>`, Authorization
    callback `https://<console-domain>/auth/github/callback` (documented, not
    configured here).
- **No deployment is performed. No cloud resource is created. No credential is
  invented or written.**

## Implementation order

1. **Baseline.** Run all four gates on the intake revision; record current
   pass/fail so regressions are attributable.
2. **Migration 4 + `store.py` scoping.** Add `users`/`sessions`, `user_id`
   columns, indexes, legacy backfill; make every `Store` method user-scoped.
   Land `tests/test_migrations_multiuser.py`.
3. **`src/crypto.py` + token encryption.** Encrypt on write, decrypt in
   `github_credentials()`. Land `tests/test_token_encryption.py`.
4. **Identity plumbing.** `src/identity.py`, OAuth callback session→user bind,
   `current_user` on protected routes, 401/403 exception handlers, `GET /`
   scoping. Land `tests/test_identity_isolation.py` (API half).
5. **Same-origin guard.** `require_same_origin` on mutating routes + Next route
   handlers forwarding `origin`/`cookie`. Land `tests/test_same_origin.py`.
6. **Scan concurrency.** `MAX_CONCURRENT_SCANS` setting, per-user lease/counter,
   429 path, scheduled exemption; per-user `OperationRunner` + `Scheduler`.
   Land `tests/test_scan_concurrency.py`.
7. **Pack idempotency.** Upsert-by-(user, repo, version) in `draft`/`save_pack`;
   partial unique index. Land `tests/test_pack_idempotency.py`.
8. **`GET /api/scans` + operation labels.** Backend route + `lib/labels.ts` +
   Operations/overview rendering. Land `tests/test_operations_view.py` and
   `frontend/lib/labels.test.ts`.
9. **Dashboard resilience.** `lib/api.ts` timeout + typed errors, `guard.ts`,
   `Skeleton`, `RetryableError`, per-route `loading`/`error`, `globals.css`
   skeleton + 24px targets, `middleware.ts`, `next.config.mjs` redirects. Land
   `frontend/lib/api.test.ts`.
10. **Multi-user fakes + e2e app.** Second identity, `/test/backend/mode`,
    user-aware seed/tick.
11. **Playwright specs.** `dashboard-resilience`, `identity-isolation`,
    `route-matrix`, `mobile-targets`; adapt `dashboard`, `oauth`,
    `repository-targeting`, `cron` specs to the authenticated model.
12. **Docs.** `README.md`, `backend/src/OPERATIONS.md`, `.env.example` files.
    Land `tests/test_docs_policy.py`.
13. **Gates in order.** `.venv/bin/python -m pytest -q`,
    `npm --prefix frontend test`, `npm --prefix frontend run test:e2e`,
    `npm --prefix frontend run build` — all exit 0, no skips, no deployment.

## Acceptance criteria being designed to (from `criteria.json`, unedited)

- **C1** — `tests` in `frontend/lib/api.test.ts` +
  `frontend/e2e/dashboard-resilience.spec.ts`: ≥10× fresh/reload/direct-nav
  renders for `/`, `/releases`, `/operations`; delayed then failed backend →
  accessible non-jumping skeleton → bounded error within 10s; `Retry` restores
  without a browser restart.
- **C2** — `tests/test_scan_concurrency.py`, `tests/test_same_origin.py`,
  `tests/test_identity_isolation.py`: 401 without a session (no GitHub call),
  generic 403 cross-user (no mutation/GitHub call), success + exactly one
  GitHub call for the owner, 429 at the configured limit (no GitHub call),
  configurable up to 10, independent per-user allowance, scheduled scans
  `CRON_SECRET`-only and concurrency-exempt, matrix covers repo selection /
  schedule / approve / reject / publish / reconcile / backend aliases.
- **C3** — `tests/test_identity_isolation.py`,
  `tests/test_token_encryption.py`, `frontend/e2e/identity-isolation.spec.ts`:
  two disjoint accounts; selectors, `GET /api/scans`, and every dashboard/API
  view are own-only; cross-user read/scan/approve/reject/publish denied with no
  change; no team/org/role path; canary absent from browser responses, logs,
  and DB plaintext.
- **C4** — `frontend/e2e/route-matrix.spec.ts`: direct load + refresh of all
  sidebar routes, `/releases/{id}`, `/github`, `/schedule` → no 404; aliases
  resolve/redirect with a usable refresh/bookmark URL; every sidebar link lands
  correctly.
- **C5** — `tests/test_pack_idempotency.py`: identical repeated scan → one
  current pack, no duplicate in `/api/releases`, both scans + audit still
  queryable; a different user/repo at the same version → a distinct pack that
  does not affect the first.
- **C6** — `tests/test_operations_view.py`,
  `frontend/lib/labels.test.ts`, `frontend/e2e/mobile-targets.spec.ts`:
  human-readable operation labels (`Non Release manual` gone) + a timestamp on
  every operation; `GET /api/scans` 401 unauthenticated / own-only
  authenticated; ≥24×24px interactive targets at a mobile viewport; skeleton
  and error/retry states carry meaningful accessible text.
- **C7** — `tests/test_docs_policy.py` + manual doc review: README /
  `OPERATIONS.md` describe public vs protected routes, one-account-per-user
  ownership, token protection, concurrency limits, scheduler auth + exemption,
  separate `backend`/`frontend` Vercel roots, server-only
  `RELEASE_MANAGER_API_URL`, all env-var names, migration steps, verification
  commands, and the legacy status of `GITHUB_TOKEN`/`GITHUB_OWNER`/
  `GITHUB_REPO`; no real secret or token value anywhere in docs or tracked
  examples.
- **C8** — the four gates run in order at step 13 and exit 0 using loopback
  services and deterministic fakes; no deployment command runs and no cloud
  resource or deployment artifact is created.

## Explicitly not changed

- `criteria.json` (acceptance phase only edits `passes`).
- The two Vercel project roots, `backend/vercel.json`, `frontend/vercel.json`
  rewrites/crons, and the server-only `RELEASE_MANAGER_API_URL` contract.
- Any existing route path, screen name, or workflow state.
- `OAuthService` session-cookie signing and the OAuth state machine.
- The GitHub REST client's request shapes and token redaction.
