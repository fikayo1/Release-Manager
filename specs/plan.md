# Release Manager UX redesign — implementation plan

> This plan supersedes the earlier "Production hardening" plan (kept in git
> history). That increment is delivered: multi-user identity, token encryption,
> scan concurrency, pack idempotency, dashboard resilience, and the operator
> docs already exist and pass. **This increment is CSS/markup only** in the
> existing Next.js app plus **two FastAPI redirect-target changes**. No
> framework change, no new frontend runtime dependencies, no backend contract
> change, no migration.
>
> Designed against `criteria.json` C1–C8 (unedited). No implementation code is
> written in this phase.

## Objective

Rebuild the operator surface around an Impeccable-style editorial brief while
preserving every existing behavior:

1. **C1** — `/` becomes a public marketing landing page: product story, one
   clear primary CTA, a "Login with GitHub" action, renders with no session,
   exposes no dashboard data or actions.
2. **C2** — an authenticated visitor to `/` still sees the marketing page (no
   redirect); the primary CTA reads "Go to dashboard" and links to `/dashboard`.
3. **C3** — unauthenticated access to any `/dashboard` route redirects to
   `/login`, renders no dashboard data/actions; protected API routes still 401.
4. **C4** — `/login` is a dedicated editorial sign-in page whose GitHub button
   starts the existing `/auth/github` flow; completing OAuth lands on
   `/dashboard`.
5. **C5** — the authenticated dashboard uses a responsive left sidebar (no top
   nav) with Overview, Releases, Operations, GitHub, Schedule, and a sign-out
   control; each link marks itself active; the logo/wordmark links to `/`; the
   sidebar collapses to a toggle on narrow viewports.
6. **C6** — a gold accent is visibly applied to primary actions and/or the
   active nav item; `.impeccable.md` at the repo root documents audience,
   typography pairing, neumorphic tokens, the gold accent token, and
   accessibility rules; primary text/background pairs meet WCAG 2.1 AA contrast.
7. **C7** — existing release-workflow behavior is preserved through the
   redesigned UI: connect a repo, Scan now, draft appears under
   `/dashboard/releases`, open `/dashboard/releases/{id}`, approval without
   actor/reason is rejected, approval with actor + reason attempts publication,
   navigation/refresh alone start no scan.
8. **C8** — `pytest`, `vitest`, Playwright e2e (including new auth-gate,
   post-login-landing, sidebar, and logo-link tests), and `next build` all pass
   offline with the existing deterministic OAuth/GitHub fakes.

## Current state (what exists and constrains the design)

- **Next.js App Router**, `output: 'standalone'`. App routes today live at the
  top level: `app/page.tsx` (overview, calls `api()`), `app/releases/`,
  `app/releases/[id]/`, `app/operations/`, `app/settings/github/`,
  `app/settings/schedule/`, plus `app/auth/github/route.ts`,
  `app/auth/github/callback/route.ts`, and `app/api/*` proxy route handlers.
- **`app/layout.tsx`** renders a dark top `<header>` with a `<strong>Release
  Manager</strong>` wordmark and `<AppNav/>` (top navigation). `app/globals.css`
  is a single-line utility sheet: light theme, flat cards, blue buttons
  (`#214da6`), a `@media(max-width:650px)` block, an explicit "≥24×24 CSS px
  interactive target" block, and accessible skeleton classes with
  `prefers-reduced-motion`.
- **`components/AppNav.tsx`** is a client component: `usePathname()`, a `LINKS`
  array, `aria-current="page"` on the active link. No sign-out control exists
  anywhere today.
- **`lib/api.ts`** (`server-only`) forwards the browser `cookie` + a same-origin
  `origin` header to FastAPI, applies an 8s abort timeout, and maps
  401→`UnauthorizedError`, 403→`ForbiddenError`, 429→`RateLimitedError`
  (`lib/http.ts`). Pages call `api()` directly and do **not** catch 401 today;
  there is **no `middleware.ts`**.
- **`next.config.mjs`** has `output: 'standalone'` and `async redirects()` for
  `/github → /settings/github` and `/schedule → /settings/schedule` (307).
- **Backend redirect targets** (only these two move):
  - `backend/src/routes.py` `github_callback` (~line 245):
    `RedirectResponse(web_url + "/settings/github?" + urlencode({"github": status}), 303)`
    for **every** outcome (success and error).
  - Docs (`README.md`, `backend/src/OPERATIONS.md`) state protected dashboard
    routes "redirect to `/settings/github`" when unauthenticated.
- **Session cookie** is `release_manager_session` — signed, opaque, HttpOnly,
  SameSite=Lax, Secure on https. Its name is the only thing a cookie-presence
  gate needs.
- **Deterministic fakes**: `tests/fakes.py` + `tests/e2e_app.py` expose
  `FakeOAuth` (authorize via `GET /test/github/authorize`), `FakeAccountGitHub`,
  `FakeRepositoryGitHub`, `JOURNAL`, `seed_pack`, `CANARY_TOKEN`, `REPO_A`/
  `REPO_B`. Playwright runs loopback servers at `127.0.0.1:18000` (API) and
  `127.0.0.1:13000` (web), `workers: 1`, `reuseExistingServer: false`.
- **Gates** (`init.sh`): `.venv/bin/python -m pytest -q` &&
  `npm --prefix frontend test` && `npm --prefix frontend run test:e2e` &&
  `npm --prefix frontend run build`.

## Design decisions (read before implementing)

- **Route topology.** The five app sections move under a `/dashboard` segment:
  `/dashboard` (overview), `/dashboard/releases`, `/dashboard/releases/{id}`,
  `/dashboard/operations`, `/dashboard/settings/github`,
  `/dashboard/settings/schedule`. `/` and `/login` are public and
  server-rendered and touch **no** session-scoped data. `app/auth/*` and
  `app/api/*` route handlers keep their paths.
- **Auth gate = cookie-presence middleware + defense-in-depth guard.**
  `frontend/middleware.ts` matches `/dashboard/:path*`; if the
  `release_manager_session` cookie is absent it issues a 307 redirect to
  `/login` before any dashboard component runs (no data fetch, no action). As
  defense in depth, every `/dashboard/**` server component loads through a
  `requireSession()` helper that also catches `UnauthorizedError` from `api()`
  and calls `redirect('/login')`, so a stale/invalid cookie that passes the
  presence check still cannot render another user's shell. Protected **API**
  proxy routes are unchanged and keep returning 401.
- **Marketing page CTA.** `app/page.tsx` is a server component. It reads only
  cookie **presence** via `next/headers` (never calls `api()`), so it renders
  identically with or without a backend. Unauthenticated: a primary CTA
  ("Open the console" → `/login`) plus a distinct "Login with GitHub" action
  (→ `/auth/github`). Authenticated: the primary CTA reads "Go to dashboard"
  and links to `/dashboard`. No release/operation/repository data is fetched or
  rendered in either state.
- **`/login`.** Dedicated editorial sign-in page (server component, no session
  data). One prominent "Continue with GitHub" / "Login with GitHub" control
  that is a link to `/auth/github` (the existing OAuth initiation route —
  unchanged). Optionally shows an inline `role="alert"` message when
  `?error=<status>` is present (`denied`, `invalid_state`, `exchange_failed`).
  Renders regardless of session state (C4 only requires the no-session case).
- **Sidebar.** New `components/Sidebar.tsx` (client component, replaces
  `AppNav`). Left rail containing: the Release Manager logo/wordmark as a
  `Link href="/"`; nav links to Overview (`/dashboard`), Releases
  (`/dashboard/releases`), Operations (`/dashboard/operations`), GitHub
  (`/dashboard/settings/github`), Schedule (`/dashboard/settings/schedule`),
  each with `aria-current="page"` when active (exact match for `/dashboard`,
  `startsWith` for the rest); and a sign-out control. On viewports ≤ ~600px the
  rail is hidden and replaced by a `<button aria-expanded aria-controls>` toggle
  that opens/closes it; `Esc` and a backdrop click close it; focus is managed
  and `prefers-reduced-motion` is honored. All interactive targets stay
  ≥ 24×24 CSS px (existing globals rule retained). Rendered once by
  `app/dashboard/layout.tsx`; no top `<header>` nav remains for dashboard pages.
- **Sign-out.** New `frontend/app/auth/logout/route.ts` (route handler,
  `POST` from a form button in the sidebar, with a `GET` fallback). It expires
  the `release_manager_session` cookie on the response and redirects to `/`.
  This is minimal glue, not a framework change or a new dependency; the backend
  session row is harmless once the cookie is gone and no backend change is
  required. (If a backend teardown is later wanted it is out of scope here.)
- **Backend redirect-target changes (the only backend edits).**
  `backend/src/routes.py` `github_callback`: on **success** redirect to
  `web_url.rstrip('/') + "/dashboard"`; on **error** redirect to
  `web_url.rstrip('/') + "/login?" + urlencode({"error": status})`. Status
  codes (302/303) and the OAuth state machine are unchanged. No other backend
  file changes.
- **Alias redirects.** `next.config.mjs` `redirects()` updated so bookmarks keep
  working: `/github → /dashboard/settings/github`,
  `/schedule → /dashboard/settings/schedule`, plus `/releases →
  /dashboard/releases`, `/releases/:id → /dashboard/releases/:id`,
  `/operations → /dashboard/operations`, `/settings/github →
  /dashboard/settings/github`, `/settings/schedule →
  /dashboard/settings/schedule` (all 307, non-permanent). `output: 'standalone'`
  retained.
- **Design system.** `.impeccable.md` at the repo root is documentation only.
  `app/globals.css` gains a `:root` token layer: an editorial type pairing
  (a display/serif face for headings, a grotesque/sans for body — both from
  `next/font` **local or Google fonts already bundled by Next**, no new npm
  dependency; system-font stack fallback), a neumorphic surface token set
  (base surface, raised/inset shadow pairs at low contrast), a single gold
  accent token (`--accent-gold`) used for primary buttons, the active nav item,
  and focus/selection highlights, a spacing scale, and a radius scale. Existing
  functional CSS (24px targets, skeletons, `prefers-reduced-motion`, the
  ≤650px block) is preserved and extended, not removed. Contrast: body text and
  headings on the neumorphic surface are chosen to meet WCAG 2.1 AA (≥ 4.5:1
  for body, ≥ 3:1 for large text and UI focus rings); gold is used against
  dark ink text or as a large fill, never as low-contrast small text.
- **Behavior preserved.** No change to release workflow, scan concurrency,
  token encryption, OAuth state machine, cron/scheduler, migrations,
  route-policy (401/403/429), or the existing mobile-responsive rules. Scan
  triggers remain "Scan now" and due enabled schedules only. Approval still
  requires actor + reason. `lib/api.ts`, `lib/http.ts`, `lib/labels.ts`,
  `lib/format.ts`, and all `app/api/*` proxy handlers are unchanged in
  behavior (only import paths for pages move).
- **Never** deploy, invent credentials, or write secret values into any file.

## Files to create

### Repo root — documentation

- `.impeccable.md` — design context, documentation not code:
  - **Audience**: release managers and engineering teams who need confidence and
    auditability in a governed release.
  - **Tone**: bold editorial, precise, calm, evidence-forward; restrained
    neumorphism (soft extruded surfaces, low-contrast shadows, no skeuomorphic
    excess).
  - **Type pairing**: the chosen display face + text face, their roles, weights,
    and the fluid type scale; fallback stacks; that both ship via Next's font
    pipeline with no new runtime dependency.
  - **Neumorphic token set**: surface color, raised shadow pair, inset shadow
    pair, border/edge highlight, radius scale, elevation usage rules.
  - **Gold accent token**: the hex value, where it may appear (primary buttons,
    active nav, focus/selection), and where it must not (small body text,
    large low-contrast fills).
  - **Spacing scale**: the step values and their intended use.
  - **Accessibility rules**: WCAG 2.1 AA contrast minimums, visible focus
    styling, ≥ 24×24 px targets, reduced-motion behavior, semantic landmarks
    (`<nav aria-label>`, `<main>`), keyboard operability of the sidebar toggle.

### Frontend — source

- `frontend/app/page.tsx` — **rewritten** as the public marketing landing page
  (see design decisions). Server component; reads cookie presence only.
- `frontend/app/login/page.tsx` — editorial sign-in page; "Continue with
  GitHub" link → `/auth/github`; optional `?error=` alert.
- `frontend/app/auth/logout/route.ts` — expire `release_manager_session`,
  redirect to `/`.
- `frontend/middleware.ts` — gate `/dashboard/:path*` on `release_manager_session`
  cookie presence → 307 `/login`; matcher excludes `/api`, `/auth`, `/_next`,
  static assets, `/`, `/login`.
- `frontend/lib/session.ts` — `hasSession()` (cookie presence, for the
  marketing CTA) and `requireSession()` / `guard(fn)` (await an `api()` call,
  catch `UnauthorizedError` → `redirect('/login')`, rethrow the rest) for
  `/dashboard/**` server components.
- `frontend/components/Sidebar.tsx` — responsive left sidebar + collapse toggle
  + sign-out form (see design decisions).
- `frontend/app/dashboard/layout.tsx` — dashboard shell: `<Sidebar/>` +
  `<main>`; no top `<header>` nav.
- `frontend/app/dashboard/page.tsx` — overview (moved from `app/page.tsx`;
  loads through `guard()`; markup restyled).
- `frontend/app/dashboard/releases/page.tsx` — moved from `app/releases/page.tsx`.
- `frontend/app/dashboard/releases/loading.tsx`,
  `frontend/app/dashboard/releases/error.tsx` — moved from `app/releases/`.
- `frontend/app/dashboard/releases/[id]/page.tsx` — moved from
  `app/releases/[id]/page.tsx`; internal `/releases/${id}` links become
  `/dashboard/releases/${id}`.
- `frontend/app/dashboard/operations/page.tsx`,
  `frontend/app/dashboard/operations/loading.tsx`,
  `frontend/app/dashboard/operations/error.tsx` — moved from `app/operations/`;
  the `/releases/${o.pack_id}` link becomes `/dashboard/releases/${o.pack_id}`.
- `frontend/app/dashboard/settings/github/page.tsx` — moved from
  `app/settings/github/page.tsx`; the `authorize_url` action still targets the
  backend's OAuth start; `?github=` alert handling retained.
- `frontend/app/dashboard/settings/schedule/page.tsx` — moved from
  `app/settings/schedule/page.tsx`.
- `frontend/app/dashboard/loading.tsx`, `frontend/app/dashboard/error.tsx` —
  segment-level skeleton / retry boundary for the dashboard (reuse
  `components/Skeleton.tsx` / `components/RetryableError.tsx`).

### Frontend — tests

- `frontend/components/Sidebar.test.tsx` (vitest + Testing Library) — renders
  the five section links + a sign-out control + the logo link to `/`; marks the
  active route with `aria-current="page"` for a given `usePathname` mock; the
  toggle button exposes `aria-expanded` and toggles an `aria-controls` region;
  no `<nav>` labelled as top navigation.
- `frontend/e2e/marketing.spec.ts` — **C1/C2**: fresh context (no cookie) loads
  `/` → 200, no redirect, product/story copy, one primary CTA, a visible "Login
  with GitHub" control, and **no** release/operation/repository text; clicking
  "Login with GitHub" reaches the OAuth flow (`/auth/github` or `/login`).
  Then authenticate via the fake and reload `/` → still 200, no redirect,
  primary CTA reads "Go to dashboard" and navigates to `/dashboard`.
- `frontend/e2e/auth-gate.spec.ts` — **C3**: with no cookie, visiting
  `/dashboard`, `/dashboard/releases`, `/dashboard/operations`,
  `/dashboard/settings/github`, `/dashboard/settings/schedule` each ends on
  `/login` with no dashboard data/controls rendered en route; a protected API
  route (`/api/releases` via the proxy, unauthenticated) returns 401.
- `frontend/e2e/dashboard-shell.spec.ts` — **C4/C5/C6**: open `/login` (no
  session) → 200, editorial layout, GitHub button; click it, complete OAuth
  with the fake → final URL is `/dashboard` and an authenticated view renders.
  At ≥ 1200px a left sidebar shows Overview/Releases/Operations/GitHub/Schedule
  + sign-out and there is no top nav bar; each link routes to the matching
  `/dashboard/...` path and self-marks active; the logo navigates to `/`. At
  ≤ 600px the sidebar collapses to a toggle that opens and closes it. A gold
  accent is present on a primary action and/or the active nav item (assert a
  computed color / class token).

### Backend — tests

- `tests/test_redirect_targets.py` — success callback (`state`+`code`)
  redirects to `<web_url>/dashboard`; `denied` / missing-state / replayed-state
  / `exchange_failed` redirect to `<web_url>/login?error=<status>`; status
  codes unchanged; the OAuth journal is unchanged.

## Files to update

### Frontend

- `frontend/app/layout.tsx` — remove the top `<header>` + `<AppNav/>`; keep
  `<html lang="en"><body>` + `<main>`-less root (dashboard layout owns `<main>`;
  marketing/login own their own containers); wire the `next/font` faces onto
  `<body>`; import `globals.css`. Metadata unchanged.
- `frontend/app/globals.css` — add the `:root` neumorphic + gold + spacing +
  radius token layer and the editorial type rules; restyle surfaces
  (`.card`, `section`, `.hero`), buttons (`button`, `.button`, `.danger`),
  form controls, badges, tables, and the new `.sidebar` / `.sidebar-toggle` /
  `.sidebar-backdrop` classes and the marketing/login layouts; **keep** the
  ≥ 24×24px target block, the `.skeleton*` classes, the
  `@media(prefers-reduced-motion)` block, and the `@media(max-width:650px)`
  responsive rules (extend the breakpoint handling for the sidebar toggle).
  Focus-visible styling uses the gold accent at AA-compliant contrast.
- `frontend/next.config.mjs` — update `redirects()` to point every legacy
  top-level app path at its `/dashboard/...` equivalent (see design decisions);
  keep `output: 'standalone'`.
- `frontend/components/AppNav.tsx` — **delete** (replaced by `Sidebar`); remove
  its import from `layout.tsx`.
- `frontend/components/ScanNowButton.tsx`, `components/GitHubRepositoryForm.tsx`,
  `components/DecisionForm.tsx`, `components/ScheduleForm.tsx`,
  `components/StatusBadge.tsx`, `components/AuditTimeline.tsx`,
  `components/Skeleton.tsx`, `components/RetryableError.tsx` — markup/class
  restyle only for the neumorphic look and gold primary actions; **no behavior,
  prop, role, label, or accessible-name changes** (e2e selectors such as
  `getByRole('button', {name:'Scan now'})`, `getByLabel('Repository')`,
  `getByLabel('Actor')`, `getByRole('status')` must keep matching).
- `frontend/e2e/dashboard.spec.ts` — retarget every navigation and URL
  assertion to `/dashboard/...`; update the `connectAndSelect` helper to
  `/dashboard/settings/github`; the `operationCount` request URL is unchanged;
  keep the read-only-navigation, manual-scan-creates-a-draft,
  schedule-persist, approval-validates-and-publishes, and mobile-routes
  scenarios (paths only change). The two "OAuth callback rejects …" tests now
  expect `/login?error=invalid_state` and the alert text on `/login`.
- `frontend/e2e/oauth.spec.ts` — after `/auth/github` the expected URL is
  `/dashboard`; repository selection now happens on
  `/dashboard/settings/github` (navigate there explicitly); the journal and
  secret-absence assertions are unchanged.
- `frontend/e2e/repository-targeting.spec.ts`,
  `frontend/e2e/cron.spec.ts` — retarget any UI paths to `/dashboard/...`;
  `page.request.*` API calls and `CRON_SECRET` usage unchanged.
- `frontend/e2e/support/*` — no change expected; confirm `run-logged.mjs`
  wrappers and log paths still apply.
- `frontend/playwright.config.ts` — no change expected (base URL, ports,
  `workers: 1`, `reuseExistingServer: false`, secret canaries unchanged);
  re-verify after the specs are updated.
- `frontend/lib/api.ts`, `frontend/lib/http.ts`, `frontend/lib/labels.ts`,
  `frontend/lib/format.ts` and their `*.test.ts` — unchanged.
- `frontend/.env.example`, `frontend/vercel.json` — unchanged (re-confirm the
  server-only `RELEASE_MANAGER_API_URL` comment and the `0 9 * * *` cron).

### Backend

- `backend/src/routes.py` — in `github_callback`, split the redirect
  destination: success → `<web_url>/dashboard`; error → `<web_url>/login?error=
  <status>`. No other change; `github_start` and the OAuth flow untouched.
- `backend/src/OPERATIONS.md` — change "redirect unauthenticated browsers to
  `/settings/github`" to `/login`; update the local/prod "open …" URLs to the
  `/dashboard/settings/github` path. Keep the "ignored by the OAuth path"
  sentence and every C7 phrase.
- `backend/.env.example`, `backend/api/index.py`, `backend/vercel.json`,
  `backend/src/config.py`, migrations, scheduler, store — **unchanged**.

### Documentation

- `README.md` — update the operator walkthrough and route list: dashboard
  routes are now `/dashboard`, `/dashboard/releases`, `/dashboard/operations`,
  `/dashboard/settings/github`, `/dashboard/settings/schedule`,
  `/dashboard/releases/{id}`; `/` is the public marketing page and `/login` the
  sign-in page; OAuth lands on `/dashboard`; **change the sentence
  "Protected dashboard routes redirect to `/settings/github`" to "redirect to
  `/login`"**. Preserve every phrase `tests/test_docs_policy.py` asserts:
  `GET /health`, `GET /auth/github`, `/api/cron/scheduler`, "one authenticated
  GitHub account is exactly one user", "shared organization, team, or
  application role", `401`/`403`/`429`, "encrypted at rest",
  `TOKEN_ENCRYPTION_KEY`, `SESSION_SECRET`, `server-only`, `NEXT_PUBLIC_`,
  `MAX_CONCURRENT_SCANS`, `1..10`, "exempt", `CRON_SECRET`, every env-var name,
  "two Vercel projects", "route to the Python function through Next rewrites",
  `python -m src.migrate`, the four gate commands, the `GITHUB_TOKEN` /
  `GITHUB_OWNER` / `GITHUB_REPO` triple, and "ignored by the OAuth path".

### Tests (existing) to update

- `tests/test_oauth_flow.py` — `test_oauth_completes_and_lists_repositories`
  now expects `location == "http://127.0.0.1:13000/dashboard"`;
  `test_invalid_state_paths_keep_their_existing_status_codes` now expects
  `"/login?error=invalid_state"` / `error=denied` in `location` (status codes
  unchanged). `test_access_token_never_leaves_the_backend` is unaffected.
- `tests/test_docs_policy.py` — line ~28: change the asserted phrase from
  "redirect to `/settings/github`" to "redirect to `/login`".
- `tests/test_review_ui.py`, `tests/test_routes.py`, and the remaining backend
  suites — re-run; expected unaffected (they exercise `/api/*` and the
  server-rendered `/review` templates, neither of which moves). Fix only if a
  literal `/settings/github` UI-path assertion surfaces.

## Deployment readiness

This increment ships **no** new environment variable, **no** migration, and
**no** provider/topology change. It is still two Vercel project roots.

- **Build**
  - Frontend (Console): `npm --prefix frontend run build` (`next build`,
    `output: 'standalone'`). New `/dashboard/*` routes and `middleware.ts` are
    built by the same command; middleware runs on the Vercel Edge runtime with
    no extra config.
  - Backend (API): no build step; Vercel installs `backend/requirements.txt`
    (unchanged — no new dependency). Local/CI: `./init.sh`.
- **Start**
  - Frontend standalone: `npm --prefix frontend start`; on Vercel: the Next.js
    runtime plus the existing `/api/cron/scheduler` cron proxy.
  - Backend standalone: `PYTHONPATH=backend .venv/bin/uvicorn src.app:app
    --host 127.0.0.1 --port 8000`; on Vercel: `backend/api/index.py` →
    `create_app(enable_scheduler=False)`, scheduled work via
    `POST /scheduler/tick`.
- **Health / readiness**
  - Backend `GET /health` → `{"status":"ok"}` only after configuration
    validation, DB connection, and migrations succeed; otherwise `503` with no
    secret values. **Contract unchanged.**
  - Frontend readiness = the Next.js server responding; `/` and `/login` render
    without a backend round-trip (cookie-presence only), so the marketing
    surface stays up even if the API is degraded.
  - Auth behavior: unauthenticated `/dashboard/*` → 307 `/login` (middleware);
    protected API proxy routes → 401; cross-user → 403; scan limit → 429
    (all unchanged). OAuth success → `/dashboard`; OAuth error → `/login?error=`.
- **Required environment variables (names only — no values in any file)**
  - Backend: `DATABASE_URL` or `POSTGRES_URL`; `RELEASE_MANAGER_WEB_URL` (now
    also the base for the `/dashboard` and `/login` redirect targets — must be
    the public Console origin); `GITHUB_OAUTH_CLIENT_ID`;
    `GITHUB_OAUTH_CLIENT_SECRET`; `GITHUB_OAUTH_CALLBACK_URL`; `SESSION_SECRET`;
    `CRON_SECRET`; `MAX_CONCURRENT_SCANS` (optional, default 1, range 1..10);
    `TOKEN_ENCRYPTION_KEY` (optional). Standalone-only:
    `SCHEDULER_INTERVAL_SECONDS`, `RELEASE_MANAGER_DB`.
  - Frontend: `RELEASE_MANAGER_API_URL` (server-only); `CRON_SECRET` (identical
    to backend). No `NEXT_PUBLIC_` variables.
  - Topology-compatibility only, not production auth: `GITHUB_TOKEN`,
    `GITHUB_OWNER`, `GITHUB_REPO`.
- **Persistence / runtime assumptions**
  - No schema or data change. Sessions remain server-side and cookie-bound; the
    `release_manager_session` cookie stays HttpOnly, SameSite=Lax, Secure on
    https. Sign-out clears the cookie on the browser; the server session row is
    inert without it.
  - `middleware.ts` reads only the cookie name — no DB access, no secret, edge-
    safe.
  - Production: managed Postgres; migrations additive/idempotent/advisory-locked
    (unchanged). Dev/CI: SQLite fallback (unchanged), file still holds encrypted
    tokens and must stay access-restricted.
  - Serverless scheduler unchanged: Vercel Cron `GET /api/cron/scheduler`
    (validates `CRON_SECRET` + `User-Agent: vercel-cron/1.0`) → trusted
    `POST /scheduler/tick`; Vercel Hobby runs `0 9 * * *`; "Scan now" remains
    the primary trigger; the Vercel deployment sets `MAX_CONCURRENT_SCANS=1`.
- **Provider configuration / operator documentation the spec requires**
  - `.impeccable.md` (repo root): audience, tone, type pairing, neumorphic
    token set, gold accent token, spacing scale, accessibility rules.
  - `README.md`: updated route list (`/`, `/login`, `/dashboard/**`), the
    `/login` unauthenticated-redirect target, OAuth landing on `/dashboard`,
    and every existing C7 topic (route policy, identity boundary, token
    protection, concurrency + scheduler exemption, all env-var names, two
    Vercel roots + server-only backend URL, migration + verification commands,
    legacy `GITHUB_*` status).
  - `backend/src/OPERATIONS.md`: `/login` redirect target and the
    `/dashboard/settings/github` operator URL.
  - GitHub OAuth App: Homepage `https://<console-domain>`, Authorization
    callback `https://<console-domain>/auth/github/callback` — **unchanged**
    (the callback path did not move); documented, not configured here.
- **Two Vercel projects, restated.** `backend` root (FastAPI, `api/index.py`,
  self-contained rewrite) and `frontend` root (Next.js + cron proxy) deploy as
  separate projects. One Next.js deployment does not and cannot route to the
  Python function through Next rewrites; the Console reaches the API only via
  the server-only `RELEASE_MANAGER_API_URL`. This redesign does not add any
  cross-project route.
- **No deployment is performed. No cloud resource is created. No credential is
  invented or written.**

## Implementation order

1. **Baseline.** Run all four gates on the intake revision; record pass/fail so
   regressions are attributable.
2. **`.impeccable.md`** at the repo root — lock the tokens, type pairing, gold
   value, spacing scale, and accessibility rules first so CSS follows the doc.
3. **Design tokens + globals.** Add the `:root` neumorphic/gold/spacing layer
   and editorial type rules to `app/globals.css`; wire `next/font` faces in
   `app/layout.tsx`; remove the top `<header>`/`<AppNav>`. Keep the 24px,
   skeleton, reduced-motion, and ≤650px blocks.
4. **Route move.** Create `app/dashboard/layout.tsx` and relocate the five
   sections (+ `[id]`, loading/error boundaries) under `/dashboard`, fixing
   internal links; delete the old top-level route folders and `AppNav.tsx`.
5. **`lib/session.ts` + `middleware.ts`.** Cookie-presence gate on
   `/dashboard/:path*` → `/login`; `guard()` wrapping every dashboard page's
   `api()` load.
6. **Marketing `/` + `/login` + sign-out route.** Rewrite `app/page.tsx`; add
   `app/login/page.tsx` and `app/auth/logout/route.ts`.
7. **`components/Sidebar.tsx`** — links, active state, logo→`/`, responsive
   collapse toggle, sign-out form; restyle the shared form/badge/button
   components for the neumorphic + gold look without touching roles or names.
8. **Backend redirects.** `routes.py` `github_callback` success→`/dashboard`,
   error→`/login?error=`. Land `tests/test_redirect_targets.py`; update
   `tests/test_oauth_flow.py`.
9. **Docs.** `README.md`, `backend/src/OPERATIONS.md`; update
   `tests/test_docs_policy.py` line ~28.
10. **Vitest.** `components/Sidebar.test.tsx`; run `npm --prefix frontend test`.
11. **Playwright.** Add `marketing.spec.ts`, `auth-gate.spec.ts`,
    `dashboard-shell.spec.ts`; retarget `dashboard.spec.ts`, `oauth.spec.ts`,
    `repository-targeting.spec.ts`, `cron.spec.ts` to `/dashboard/...` and the
    new landing/redirect targets.
12. **Gates in order.** `.venv/bin/python -m pytest -q`,
    `npm --prefix frontend test`, `npm --prefix frontend run test:e2e`,
    `npm --prefix frontend run build` — all exit 0, no skips, no deployment.

## Acceptance criteria being designed to (from `criteria.json`, unedited)

- **C1** — `frontend/e2e/marketing.spec.ts`: no-session `/` → 200, no redirect,
  product story + one primary CTA + a visible "Login with GitHub" control, no
  account data; the login control reaches `/auth/github` or `/login`.
- **C2** — `frontend/e2e/marketing.spec.ts`: authenticated `/` → 200, no
  redirect, primary CTA reads "Go to dashboard" and navigates to `/dashboard`.
- **C3** — `frontend/e2e/auth-gate.spec.ts`: no-session `/dashboard`,
  `/dashboard/releases`, `/dashboard/operations`, `/dashboard/settings/github`,
  `/dashboard/settings/schedule` each redirect to `/login` with nothing
  rendered en route; a protected API route still returns 401.
- **C4** — `frontend/e2e/dashboard-shell.spec.ts`: `/login` (no session) → 200
  editorial layout with a GitHub button; completing OAuth with the fake lands on
  `/dashboard` as an authenticated view.
- **C5** — `frontend/e2e/dashboard-shell.spec.ts` +
  `frontend/components/Sidebar.test.tsx`: left sidebar (no top nav) with
  Overview/Releases/Operations/GitHub/Schedule + sign-out; links route to the
  matching `/dashboard/...` and self-mark active; logo → `/`; ≤600px collapses
  to a working toggle.
- **C6** — `frontend/e2e/dashboard-shell.spec.ts` + manual review: a gold
  accent on a primary action and/or the active nav item; `.impeccable.md` at
  the repo root documents audience, type pairing, neumorphic tokens, the gold
  accent token, and accessibility rules; heading/body pairs meet WCAG 2.1 AA.
- **C7** — `frontend/e2e/dashboard.spec.ts` (retargeted): connect a repo on
  `/dashboard/settings/github`, "Scan now" on `/dashboard`, a draft appears
  under `/dashboard/releases`, open `/dashboard/releases/{id}`, approval without
  actor/reason is rejected, approval with actor + reason attempts publication,
  navigation/refresh alone start no scan.
- **C8** — the four gates run in order at step 12 and exit 0 using loopback
  services and the deterministic fakes; no deployment command runs and no cloud
  resource or deployment artifact is created.

## Explicitly not changed

- `criteria.json` (acceptance phase only edits `passes`).
- The two Vercel project roots, `backend/vercel.json`, `frontend/vercel.json`,
  the cron schedule, and the server-only `RELEASE_MANAGER_API_URL` contract.
- Any backend API contract, status code, migration, scheduler, encryption, or
  OAuth state-machine behavior. The only backend edit is the `github_callback`
  redirect destination.
- `lib/api.ts`, `lib/http.ts`, `lib/labels.ts`, `lib/format.ts`, and the
  `app/api/*` proxy route handlers.
- The OAuth callback **path** (`/auth/github/callback`) and the GitHub OAuth App
  configuration.
- The existing accessibility guarantees: ≥ 24×24px targets, accessible
  skeletons, `prefers-reduced-motion`, and the ≤650px responsive rules.
