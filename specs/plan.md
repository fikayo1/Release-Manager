# GitHub OAuth and repository-targeting completion — implementation plan

> This plan supersedes the earlier "operator dashboard" plan for the current
> increment. The prior plan remains in git history (commit `5244a2de` and
> around `923227c7`). No routes, screens, workflow states, or operator
> behavior are redesigned here — this increment only *finishes and proves*
> the existing GitHub OAuth / repository-selection / scan-targeting flow with
> deterministic doubles and a token canary.

## Objective

Close `criteria.json` C1–C7 without changing product surface:

- Existing entry points stay exactly as-is: `/auth/github`, `/auth/github/callback`,
  `/settings/github`, `/settings/schedule`, `Scan now`, the schedule controls, and
  the pack approve/reject/publish/reconcile actions (`src/routes.py`,
  `frontend/app/settings/github/page.tsx`, `frontend/components/*`).
- Automated acceptance runs entirely offline against deterministic OAuth + GitHub
  doubles and a single distinctive fake access-token canary. No live GitHub
  credentials, no network.
- Persistence and targeting scenarios run against a real on-disk operator
  database (the process's configured `RELEASE_MANAGER_DB`), including the records
  the scenarios themselves create — not an isolated synthetic-only database.
- After OAuth the access token stays backend-only: the canary must be absent from
  browser-visible URLs, rendered content, browser-observed response bodies, Web
  Storage, browser console output, and captured backend/frontend process logs.
- Selecting repository B after A-targeted work exists retargets only the next
  manual scan and the next due scheduled scan; it never retargets existing A work
  (reconcile, rollback/reject, approval, publication).
- All four gates stay green: `pytest -q`, `npm --prefix frontend test`,
  `npm --prefix frontend run test:e2e`, `npm --prefix frontend run build`.

## Current state (what already exists and is kept)

- `src/github_oauth.py` — `OAuthService`: signed opaque session cookie, hashed
  state, `token_request` injection hook. **Unchanged** (secure-cookie behaviour
  preserved).
- `src/github_client.py` — `GitHubAccountClient` (`user()`, `repositories()`),
  `GitHubClient` (scan reads + `create_release` + `release_for_tag`), token
  redaction in `__repr__` and `_safe`.
- `src/routes.py` — `/auth/github`, `/auth/github/callback`, `GET /api/github`,
  `PUT /api/github/repository`, `POST /api/scans`, pack actions.
- `src/store.py` — `save_github_connection`, `github_connection()` (credential
  columns excluded), `github_credentials()`, `select_repository()`,
  `mark_github_revoked()`; `migrations.py` migration 3 creates
  `github_connection` / `oauth_states`.
- `src/operations.py` `OperationRunner` — resolves the repository from
  `store.github_connection()["selected_repository"]` at run start via
  `client_provider`; captures it on the scan. `src/scheduler.py` drives the same
  runner with `source="scheduled"`.
- `src/phases/scan.py` records `f"{github.owner}/{github.repo}"` on the `Scan`;
  `src/routes.py::client_for_pack` re-resolves credentials against the
  scan-captured repository for pack actions (so A work stays A).
- `tests/e2e_app.py` — deterministic OAuth + GitHub doubles + `/test/*` endpoints,
  started only by Playwright.
- `frontend/e2e/dashboard.spec.ts` — already exercises much of the OAuth +
  targeting path; kept, with overlap trimmed once dedicated specs exist.

## Gaps this increment closes

1. The fixture token `"browser-test-token"` is not a distinctive canary and is not
   asserted-absent from logs / storage / bodies.
2. The GitHub double has no observable, resettable **request journal** covering
   authorization, token exchange, repository listing, and per-repository scan
   reads / writes / tag lookups keyed by repository full name.
3. The double's `RepositoryGitHub` is not repository-aware for reconcile
   (`release_for_tag`) and does not record which repo each call targeted.
4. No backend test proves: OAuth completion through doubles, canary absent from
   API responses, selection survival across a fresh process on the same DB file,
   and A-work actions never calling the B double.
5. No Playwright spec dedicated to C2 (canary containment incl. captured server
   logs) or to C4/C5/C6 as isolated, journal-asserted scenarios, or to a **real
   backend process restart** (C3).
6. Playwright does not currently capture backend/frontend stdout+stderr to a file
   a test can assert against.

## Files to create

### Shared deterministic doubles

- `tests/fakes.py` — single source of truth for the doubles, imported by both
  `tests/e2e_app.py` and the new backend tests:
  - `CANARY_TOKEN` — one distinctive, obviously-fake access token string
    (e.g. `ghp_FaKeCaNaRy0000NeverLogMe0000DEADBEEFcafe`), plus `OTHER_REPO`
    helpers.
  - `Journal` — append-only list of `{kind, repository, detail}` entries with
    `record()`, `entries()`, `reset()`, and `for_repo(name)` filters.
  - `FakeOAuth(OAuthService)` — deterministic `token_request` returning
    `{"access_token": CANARY_TOKEN}` only for the accepted code; overrides
    `begin()` to point at the fixture's local `/test/github/authorize`; records
    `authorize` and `token_exchange` journal entries. No cookie/session changes.
  - `FakeAccountGitHub(GitHubAccountClient)` — injected transport serving two real
    `/user/repos` pages (`fixture/repository-a` private, `fixture/repository-b`
    public) and `/user`; asserts `Authorization: Bearer <CANARY_TOKEN>`; records
    `user` and `repos_page` journal entries; raises `AssertionError` on any
    non-`api.github.com` / unexpected URL (proves no live GitHub).
  - `FakeRepositoryGitHub` — repository-aware scan reads, `create_release`,
    `release_for_tag`; every method records a journal entry tagged with
    `f"{owner}/{repo}"`; asserts the token is `CANARY_TOKEN`. Deterministic
    release-worthy evidence for repo A and repo B, distinguishable per repo.
  - `seed_pack(store, pack_id, repository, status, *, tag=...)` — insert an
    A-targeted `Scan` + pack + operation directly in the states where reconcile
    (`publishing`/`uncertain`), rollback/reject (`pending`), approval
    (`pending`), and publish (`pending`) are each applicable, mirroring
    `tests/test_review_ui.add_pack` conventions.

### Backend tests (offline, deterministic, real temp operator DB file)

- `tests/test_oauth_flow.py` — designs to **C1** and the backend half of **C2**:
  - Drive `GET /auth/github` → `/test/github/authorize` → `GET /auth/github/callback`
    through `FakeOAuth` + `FakeAccountGitHub` with a real `Settings(database=<tmp
    file>)` app; assert redirect lands on `…/settings/github?github=connected`.
  - `GET /api/github` lists repositories A and B; `PUT /api/github/repository`
    accepts A and rejects an unauthorized slug (422).
  - Journal shows `authorize`, `token_exchange`, `user`, `repos_page`×2 and **no**
    entry outside the doubles.
  - Canary assertion: `CANARY_TOKEN` absent from every response body/header of
    `/auth/github/callback`, `/api/github`, `/api/github/repository`,
    `/api/operations`, `/api/releases`; absent from `store.github_connection()`;
    present only in `store.github_credentials()`. `repr()` of both client classes
    and any raised `GitHubError` never contains it.
  - Existing invalid/expired/denied/replayed-state paths still redirect with the
    existing `github=` status codes (regression guard, no behaviour change).

- `tests/test_repository_targeting.py` — designs to **C3**, **C4**, **C5**, **C6**:
  - **C3**: connect + select A against a temp DB file; open a *new* `Store` on the
    exact same path (simulating a fresh process) and assert
    `github_connection()["selected_repository"] == "fixture/repository-a"` with no
    re-selection; also assert `GET /api/github` from a freshly built app on that
    file shows A selected. (The real-process restart is additionally covered in
    Playwright.)
  - **C4**: with A selected, run `OperationRunner(...).run("manual")`; retain the
    A operation/pack. Switch selection to B, `journal.reset()`, run again; assert
    the new operation's `repository` is B, journal for that scan contains only
    B-targeted read calls, and the retained A operation/pack still reports A via
    `store.operation(...)` / `store.pack_detail(...)`.
  - **C5**: keep B selected, `update_schedule("* * * * *", True, ...)`, run one
    `Scheduler.tick()` with an injected UTC clock on a due slot; assert exactly
    one `source="scheduled"` operation for that slot, targeting B, journal
    B-only, and it reaches `draft_created`.
  - **C6**: `seed_pack` four A-targeted records; select B; call `approve`+`publish`,
    `reject`, `publish`, and `reconcile` through `src/routes.py` handlers /
    `src/phases`; assert every journal entry produced names repo A, never B, and
    each record stays A-targeted and reaches its expected terminal/recovery state.
    Assertions read the journal and persisted/API views, not internal mocks.

### Playwright specs (real browser, real processes, deterministic doubles)

- `frontend/e2e/support/run-logged.mjs` — wrapper: `run-logged.mjs <logfile> -- <cmd…>`
  spawns the command, tees combined stdout+stderr to `<logfile>` and through to
  the parent, exits with the child's code. Used for both Playwright `webServer`
  entries so a test can read the captured logs.

- `frontend/e2e/support/backend.ts` — helper to `spawn`/`kill` an extra
  `uvicorn tests.e2e_app:app` process on a dedicated port pointed at a caller-
  supplied operator DB path, with `waitForHealth()` and `stop()`; used by the
  restart scenario. Honours an env flag so the *restarted* process does not reset
  its database.

- `frontend/e2e/oauth.spec.ts` — designs to **C1** + **C2**:
  - From `/settings/github`, click `Continue with GitHub`, return through the
    existing callback, assert `Connected as` and that the repository `<select>`
    offers `fixture/repository-a` and `fixture/repository-b`; select A and save.
  - Assert `GET /test/github/journal` shows the expected authorize / token /
    `/user` / `/user/repos` interactions and zero entries outside the doubles.
  - Throughout callback → settings load → save: collect every `page.on('request')`
    URL, every response body (`response.text()` where readable), `page.on('console')`
    output, full rendered `document.documentElement.outerHTML`, and all
    `localStorage` + `sessionStorage` keys/values; after the run read both
    captured server log files. Assert `CANARY_TOKEN` appears in **none** of them
    and not in `page.url()` / the address bar.
  - Assert the session cookie is still `HttpOnly` (not visible to
    `document.cookie`) — existing behaviour unchanged.

- `frontend/e2e/repository-targeting.spec.ts` — designs to **C4**, **C5**, **C6**
  (and the process-restart half of **C3**):
  - Connect, select A, `Scan now`, keep the A release. `POST /test/github/journal/reset`.
  - Select B via the existing form, `Scan now`; assert `/test/github/journal`
    contains B-targeted scan reads and **no** A-targeted request for that scan;
    open the retained A release and assert its displayed/API repository is still A.
  - **C5**: enable a deterministically-due schedule through `/settings/schedule`,
    reset the journal, advance the fixture clock / trigger the due slot via a
    `/test/*` control that drives the *real* `Scheduler` path; assert one
    scheduled operation for B reaching `draft_created` and journal B-only.
  - **C6**: call `/test/seed` to create A-targeted packs in reconcile / reject /
    approve / publish states; with B selected, perform each action through its
    existing UI/API entry point; assert `/test/publications` + journal show repo A
    only and the records stay A-targeted.
  - **C3 restart**: using `support/backend.ts`, start an extra backend on its own
    port + operator DB file, complete OAuth + select A against it, `kill` it,
    start a fresh process on the same DB path, reload its `/api/github` (proxied)
    and assert A is still selected without re-selecting or re-authorising.

### Playwright frontend unit coverage (if a component changes)

- `frontend/components/GitHubRepositoryForm.test.tsx` — only if the component is
  touched: no mount-time request, one PUT per explicit save, busy state, backend
  error surfaced, selection preselected from `selected` prop. (Preferred: leave
  the component untouched and add no test.)

## Files to update

- `tests/e2e_app.py` — import the doubles from `tests/fakes.py`; use `CANARY_TOKEN`;
  add endpoints: `GET /test/github/journal`, `POST /test/github/journal/reset`,
  `POST /test/seed` (A-targeted pack records per state), and a `/test/*` control
  that advances the scheduler clock / forces the next due slot through the real
  `Scheduler`. Reset the operator DB only when an explicit env flag is set (so a
  restarted process keeps its data); keep the DB path from `E2E_DB`.
- `frontend/playwright.config.ts` — route both `webServer` commands through
  `support/run-logged.mjs` with per-server log file paths under `e2e/.logs/`;
  export those paths (env or a shared constant) for specs; keep
  `reuseExistingServer: false` and the non-skipping single project.
- `frontend/e2e/dashboard.spec.ts` — trim the OAuth/targeting assertions now
  owned by the new specs to keep runtime down, but keep at least a smoke path;
  no coverage is lost overall.
- `.gitignore` — ignore `frontend/e2e/.logs/` and any temp operator DB files the
  restart helper creates.
- `README.md` — document the deterministic-doubles + canary acceptance approach
  and the operator-DB restart expectation. **Keep** the existing
  `GITHUB_TOKEN` / `GITHUB_OWNER` / `GITHUB_REPO` legacy-automation section
  verbatim; keep the four verification commands.
- `src/OPERATIONS.md` — one paragraph: repository selection is captured at scan
  start, survives restart on the same DB file, and never retargets existing work;
  note the legacy `GITHUB_TOKEN`/`GITHUB_OWNER`/`GITHUB_REPO` triple.

Only touch `src/*` if a gate proves a real defect (e.g. a genuine canary leak or
a targeting bug). Expected default: **no production code change** — this is
test/fixture/doc completion. Any src change must preserve all current behaviour
and be justified against a failing criterion.

## Explicitly not changed

- `criteria.json` (acceptance phase only).
- `requirements.txt` and the locked project requirements.
- `src/github_oauth.py` session/cookie logic.
- Any route path, screen, workflow state, or operator-visible behaviour.

## Implementation order

1. **Baseline.** Run all four gates on the intake revision and record current
   pass/fail and the exact journal of GitHub calls the existing e2e path makes.
2. **Extract `tests/fakes.py`.** Move the `tests/e2e_app.py` doubles into it,
   add `CANARY_TOKEN`, the `Journal`, repository-aware `FakeRepositoryGitHub`
   (incl. `release_for_tag`), and `seed_pack`. Re-point `tests/e2e_app.py` at it;
   keep the e2e Playwright suite green.
3. **Add fixture observability.** `GET /test/github/journal`,
   `POST /test/github/journal/reset`, `POST /test/seed`, and the real-scheduler
   due-slot control in `tests/e2e_app.py`. Guard the DB reset behind an env flag.
4. **Backend `tests/test_oauth_flow.py`.** C1 + backend C2 (canary absent from all
   API responses and `github_connection()`, present only in credentials; repr /
   error redaction). Keep existing invalid-state regressions.
5. **Backend `tests/test_repository_targeting.py`.** C3 (new `Store` on same
   file), C4 (manual A→B, A work unchanged), C5 (`Scheduler.tick` on a due slot
   targets B), C6 (seeded A packs — every action journals repo A only).
6. **Playwright log capture.** `support/run-logged.mjs` + `playwright.config.ts`
   wiring; confirm existing specs still pass with piped/teed output.
7. **`frontend/e2e/oauth.spec.ts`.** C1 + C2 with full request/response/console/
   storage/HTML capture and captured server-log assertions; HttpOnly cookie check.
8. **`support/backend.ts` + `frontend/e2e/repository-targeting.spec.ts`.** C3
   real-process restart, C4/C5/C6 browser-level with journal + `/test/publications`
   + persisted/API assertions.
9. **Trim `dashboard.spec.ts`** overlap; verify total e2e coverage unchanged.
10. **Docs.** `README.md`, `src/OPERATIONS.md`, `.gitignore`.
11. **Gates in order.** `.venv/bin/python -m pytest -q`,
    `npm --prefix frontend test`, `npm --prefix frontend run test:e2e`
    (provisioned browser binaries; no skips/timeouts/zero-test),
    `npm --prefix frontend run build`. All four exit 0.

## Acceptance criteria being designed to (from `criteria.json`, unedited)

- **C1** — OAuth authorizes through deterministic doubles and permits repository
  selection with no live GitHub: `tests/test_oauth_flow.py`,
  `frontend/e2e/oauth.spec.ts`; journal shows authorize/token + repo-list, no
  live request.
- **C2** — access token not exposed to browser or logs: `frontend/e2e/oauth.spec.ts`
  (URL bar, request URLs, response bodies, rendered HTML, `localStorage` +
  `sessionStorage`, console, captured backend+frontend logs) + backend redaction
  checks in `tests/test_oauth_flow.py`. Distinctive `CANARY_TOKEN`.
- **C3** — selection survives a real backend restart on the same operator SQLite
  file: `frontend/e2e/repository-targeting.spec.ts` (kill + respawn `uvicorn` on
  the same DB path) + `tests/test_repository_targeting.py` (fresh `Store` / app).
- **C4** — A→B change retargets the next manual scan; existing A work stays A:
  `tests/test_repository_targeting.py` + `frontend/e2e/repository-targeting.spec.ts`,
  asserting via the journal and persisted/API-visible results.
- **C5** — next due scheduled scan targets B exactly as the manual scan: same two
  files, driving the real `Scheduler` path with a controlled clock / due-slot
  control.
- **C6** — changing selection to B never retargets reconcile, rollback, approval,
  or publish for existing A work: `tests/test_repository_targeting.py` +
  `frontend/e2e/repository-targeting.spec.ts`, asserting every GitHub interaction
  names repo A via the journal and `/test/publications`, and records stay
  A-targeted.
- **C7** — all existing backend, frontend unit, Playwright, and production
  Next.js build checks stay green: enforced by running all four gates in order at
  step 11, and by keeping `src/*` unchanged unless a criterion forces it.
