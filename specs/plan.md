# Release Manager operator dashboard implementation plan

## Delivery approach

Extend the existing FastAPI application as the canonical workflow and persistence service, and add a separate responsive Next.js app-router UI in `frontend/`. The browser will read and mutate state only through the dashboard's same-origin server route handlers; those handlers call FastAPI with a server-only base URL. GitHub credentials remain exclusively in the FastAPI process, and no page render, route prefetch, mount, refresh, or polling path will trigger a scan. The sole browser scan entry point will be the explicit **Scan now** control.

FastAPI will retain the existing scan, classification, draft, decision, publication, reconciliation, and audit functions. A new workflow runner will wrap the existing scan/draft phases for both manual and scheduled requests, add durable operation tracking, and acquire the same SQLite-backed lease regardless of trigger source. Approval will continue to record a human decision and immediately call the existing governed publication phase; rejection remains terminal. Existing explicit publication/reconciliation APIs will remain available for recovery and compatibility, subject to the existing state guards.

One schedule row will be persisted in SQLite. Its expression has exactly five fields, all evaluation and display are UTC, and it can be enabled or disabled. A FastAPI lifespan scheduler will calculate due slots, persist scheduler heartbeat/run metadata, and resume from durable state after restart. A transactional singleton lease will prevent process-local and multi-process overlap. Every attempted run receives an operation record: a lease loser is completed as `suppressed`, while started, successful, non-release, failed, interrupted/uncertain, and recovered outcomes remain inspectable and auditable. Lease ownership has an expiry and heartbeat so a dead API process cannot lock scans forever; startup recovery will close abandoned operations truthfully and continue future due work without representing an unknown run as successful.

Schema evolution will be additive and versioned. The migration will create schedule, operation, scheduler-state, and lease structures without dropping or rewriting existing scans, verdicts, packs, decisions, attempts, reconciliations, or audit rows. Existing scans will be represented as legacy operations where needed so historical data remains visible, while retaining their original identifiers and pack relationships.

## Files to create

### Backend workflow, scheduler, and migration

- `src/migrations.py` — ordered, transactional SQLite migrations and schema version tracking; additive migration/backfill from the current schema with preservation checks.
- `src/cron.py` — dependency-free validation and UTC next-run calculation for standard five-field cron expressions, including ranges, lists, wildcards, and steps with clear validation errors.
- `src/operations.py` — the single manual/scheduled workflow runner, durable lease acquisition/renewal/release, operation state transitions, scan/verdict/pack linkage, suppression, safe error recording, and audit emission.
- `src/scheduler.py` — lifespan-owned scheduler service, UTC clock abstraction, persisted heartbeat and due-slot handling, restart recovery, and deterministic wake/clock hooks for tests.

### Backend tests and deterministic fixtures

- `tests/fakes.py` — reusable deterministic fake GitHub repository, evidence, release, failure, and blocking controls used without network access.
- `tests/test_migrations.py` — pre-migration database upgrade and preservation/backfill coverage.
- `tests/test_cron.py` — exact five-field validation and deterministic UTC matching/next-run cases.
- `tests/test_operations.py` — shared workflow, manual/scheduled source, release and non-release outcomes, failure safety, lease suppression, and restart/expired-lease behavior.
- `tests/test_scheduler.py` — deterministic time advancement, enabled/disabled schedules, persisted schedule state, due execution, no duplicate slot execution, health metadata, and restart recovery.
- `tests/e2e_app.py` — test-only FastAPI assembly using a temporary durable database, fake GitHub implementation, controllable clock, held scans, publication failures, reset/seed helpers, and scheduler controls. This module is started only by Playwright and is not mounted by the production app.

### Next.js application and configuration

- `frontend/package.json` — pinned Next.js/React runtime and unit/Playwright tooling with `test`, `test:e2e`, and `build` scripts.
- `frontend/package-lock.json` — reproducible npm dependency resolution.
- `frontend/next.config.mjs` — production-safe app configuration without exposing backend secrets.
- `frontend/tsconfig.json` — strict TypeScript/app-router configuration.
- `frontend/next-env.d.ts` — Next.js TypeScript declarations.
- `frontend/vitest.config.ts` — jsdom/component unit-test configuration.
- `frontend/vitest.setup.ts` — DOM matcher and test cleanup setup.
- `frontend/playwright.config.ts` — non-skipping browser project plus deterministic FastAPI and Next web-server startup, timeouts, traces, and local runtime configuration.
- `frontend/app/layout.tsx` — application shell, responsive navigation, title/metadata, and global status semantics.
- `frontend/app/globals.css` — responsive layout, forms, tables/cards, timelines, status treatments, loading/error states, and accessible focus styles.
- `frontend/app/page.tsx` — overview with repository/schedule health, recent releases and operations, and the explicit manual scan control.
- `frontend/app/releases/page.tsx` — release-pack index with status, version, source operation/scan, and publication summary.
- `frontend/app/releases/[id]/page.tsx` — full pack view with evidence, rationale, proposed version, notes, announcement, decision/publication state, recovery information, and chronological audit timeline.
- `frontend/app/operations/page.tsx` — operation history showing trigger source, repository, evidence/decision summary, suppression, result/error, uncertain/recovery status, related pack, and audit events.
- `frontend/app/settings/schedule/page.tsx` — UTC schedule editor and display for expression, enabled state, validation, health, next/latest run, latest result, and last error.
- `frontend/app/loading.tsx` — navigation loading feedback that performs no mutations.
- `frontend/app/error.tsx` — recoverable dashboard error boundary without leaking backend details.
- `frontend/app/not-found.tsx` — consistent unknown-release/route state.
- `frontend/components/AppNav.tsx` — accessible responsive navigation for all required routes.
- `frontend/components/ScanNowButton.tsx` — explicit, guarded manual scan mutation with busy/result feedback and no automatic invocation.
- `frontend/components/ScheduleForm.tsx` — controlled enabled/expression editing with server validation feedback.
- `frontend/components/DecisionForm.tsx` — actor/reason approval and rejection controls, confirmation/busy handling, and terminal-state hiding.
- `frontend/components/StatusBadge.tsx` — text-plus-color status rendering.
- `frontend/components/AuditTimeline.tsx` — ordered accessible audit event presentation.
- `frontend/components/EvidenceList.tsx` — safe commit and pull-request evidence links and metadata.
- `frontend/lib/api.ts` — server-only typed FastAPI client, explicit cache policy, safe error mapping, and backend URL access; marked server-only so environment values cannot enter client bundles.
- `frontend/lib/types.ts` — API view types for schedules, operations, packs, evidence, publication, recovery, and audit records.
- `frontend/lib/format.ts` — UTC date/result display helpers with deterministic fallbacks.
- `frontend/app/api/scans/route.ts` — same-origin POST proxy used only by the Scan now component.
- `frontend/app/api/schedule/route.ts` — same-origin schedule update proxy.
- `frontend/app/api/releases/[id]/approve/route.ts` — same-origin approval proxy preserving backend status/error truth.
- `frontend/app/api/releases/[id]/reject/route.ts` — same-origin rejection proxy preserving backend status/error truth.
- `frontend/app/api/releases/[id]/reconcile/route.ts` — same-origin explicit recovery proxy for uncertain publication states.

### Frontend tests

- `frontend/components/ScanNowButton.test.tsx` — no mount-time request, one request per explicit action, busy state, suppression, and failure rendering.
- `frontend/components/ScheduleForm.test.tsx` — five-field validation feedback, UTC labeling, enabled/disabled submission, and persisted metadata display.
- `frontend/components/DecisionForm.test.tsx` — required trimmed actor/reason, approval/rejection endpoints, terminal-state behavior, and backend errors.
- `frontend/components/AuditTimeline.test.tsx` — ordered actor/reason/result and failure/recovery rendering.
- `frontend/lib/format.test.ts` — UTC and absent-value formatting.
- `frontend/e2e/dashboard.spec.ts` — required route/direct-navigation/history checks, responsive smoke checks, and proof that navigation/reload does not create operations.
- `frontend/e2e/schedule.spec.ts` — invalid editing, UTC persistence across API restart, deterministic scheduled draft creation, disable behavior, and overlap suppression.
- `frontend/e2e/workflow.spec.ts` — manual scan, release/non-release evidence, approval with immediate publication, terminal rejection, audit display, publication/GitHub failure, uncertain state, and recovery.

## Existing files to update

- `src/models.py` — add typed operation, trigger/result, schedule, scheduler health, and lease-facing domain/view contracts without changing existing persisted pack/scan meanings.
- `src/store.py` — invoke migrations and add transactional schedule, scheduler, operation, lease, joined detail/list, and audit queries; retain existing compare-and-set decision/publication/reconciliation behavior and all historical records.
- `src/config.py` — add non-secret scheduler timing/instance configuration and safe server defaults while keeping GitHub token redacted and environment-only.
- `src/app.py` — initialize migrations, recover durable scheduler state, start/stop the scheduler in lifespan, and support injected clock/runner dependencies for deterministic tests. Production startup still validates the configured repository.
- `src/routes.py` — remove legacy HTML rendering, retain compatible governed JSON routes, add read APIs for dashboard releases/operations/schedule, add explicit manual operation and schedule update APIs, return complete source/evidence/audit/publication/recovery views, and map validation/conflict/external failures to truthful HTTP responses.
- `src/phases/scan.py` — accept operation/lease-safe orchestration needs without embedding trigger-specific behavior; preserve immutable evidence collection and classification.
- `src/phases/draft.py` — keep pack creation conditional on release worthiness while allowing the runner to record a durable non-release result.
- `src/phases/publish.py` — retain immediate governed publication and uncertain-outcome safety while exposing enough structured outcome information for operation/recovery views.
- `src/phases/rollback.py` — connect reconciliation outcomes to operation recovery presentation/audit without weakening existing matching/absent/conflict checks.
- `tests/test_config.py` — cover scheduler configuration defaults and confirm secret redaction.
- `tests/test_core.py` — adapt canonical workflow tests to operation linkage while retaining classification/version/draft assertions.
- `tests/test_governance.py` — retain mandatory trimmed actor/reason and terminal decision tests under migrated persistence.
- `tests/test_recovery_audit.py` — verify uncertain publication and reconciliation are reflected in both preserved audit and operation recovery state.
- `tests/test_routes.py` — cover new dashboard APIs, schedule validation, operation payloads, explicit scan-only mutation, compatibility routes, decision outcomes, and safe error statuses.
- `tests/test_health.py` — cover application and scheduler health/lifespan behavior.
- `README.md` — replace scaffold text with clean Python/npm setup, development and production startup, backend/frontend URLs, all environment variables, migrations, UTC schedule semantics, durable restart behavior, and the complete verification commands.
- `src/OPERATIONS.md` — document schedule ownership/health, lease and suppression behavior, restart/interruption recovery, backup/migration procedure, manual versus scheduled operations, publication reconciliation, secrets, and deterministic browser-test procedure.
- `.gitignore` — ignore Next.js output, frontend coverage/test artifacts, Playwright reports, and local frontend environment files while retaining lockfiles.
- `init.sh` — keep one-command Python setup and install the locked frontend dependencies once `frontend/package-lock.json` exists; print the exact required verification sequence.

The existing `requirements.txt` and locked project requirements will not be changed. Cron parsing and scheduling use the Python standard library and existing FastAPI lifecycle primitives. `criteria.json` will not be edited except by a later acceptance phase that is authorized to flip `passes` values.

## Legacy files to remove after replacement

- `src/templating.py`
- `src/templates/base.html`
- `src/templates/review_list.html`
- `src/templates/pack_detail.html`
- `src/static/review.css`
- `tests/test_review_ui.py`

Removal occurs only after equivalent API and Next.js coverage is passing. The old `/review` pages are not retained as a second state-changing interface; optional redirects may point operators to the configured Next.js dashboard, but FastAPI remains the source of truth.

## Implementation order

1. **Baseline and characterize.** Run the current backend suite and record current schema, endpoint, scan/draft, decision, publication, recovery, and audit contracts. Create a representative current-version database fixture before changing persistence.
2. **Introduce safe migrations.** Add schema versioning and the additive schedule/operation/lease structures. Backfill old scans into legacy operation views without changing existing rows. Prove migration idempotence, foreign-key relationships, record counts, JSON payloads, decisions, attempts, reconciliations, and audit order before proceeding.
3. **Add cron and schedule storage.** Implement strict five-field parsing and UTC next occurrence calculation, then schedule CRUD and scheduler health metadata. Reject malformed expressions atomically so the last valid persisted schedule remains unchanged.
4. **Build the common operation runner.** Create operation intent first, transactionally claim the singleton lease, record suppression on conflict, run the existing scan/classify/draft path, link evidence/verdict/pack, and complete with a distinct draft-created, non-release, failed, or uncertain result. Renew and release the lease safely, sanitize errors, and append audit records for every attempted trigger.
5. **Run scheduling from application lifespan.** Add a cancellable scheduler loop using injected UTC clock/wake primitives. Persist due slot and heartbeat before/around dispatch, enforce one execution per slot across restarts/processes, recover stale leases and interrupted records, and make disabled schedules inert. Confirm shutdown does not erase durable state.
6. **Expose dashboard APIs.** Add schedule, release, operation, manual scan, decision, and recovery representations while preserving existing API paths. Ensure GETs are read-only, POST manual scan is the only scan mutation, approval publishes immediately, rejection is terminal, and failures/uncertainty remain truthful.
7. **Create the Next.js shell and server data layer.** Add reproducible tooling, strict types, server-only API access, responsive navigation, route-level loading/error/not-found handling, and the five required app routes. Do not use `NEXT_PUBLIC_` for credentials or embed FastAPI/GitHub secrets in HTML, JavaScript, browser storage, or browser-visible headers.
8. **Add explicit controls and detail views.** Implement Scan now, schedule editing, decision, and recovery components. Render operation evidence/results and full pack source/version/content/publication/audit information. Invalidate/refetch only after explicit mutations; never trigger a scan from effects, server rendering, prefetch, polling, or retries.
9. **Add unit and backend integration coverage.** Test migration preservation, cron boundaries, lease races, scheduler restart/catch-up semantics, shared workflows, failures, governance, and API read/write separation with temporary SQLite files and deterministic fake GitHub data.
10. **Add non-optional Playwright coverage.** Start the deterministic FastAPI fixture and Next.js app from Playwright configuration, reset state per test, control time and held scans without wall-clock sleeps, and exercise actual browser routes and forms. Treat missing browser executable, skipped tests, timeout, web-server failure, or zero executed tests as a failing command.
11. **Remove the legacy HTML UI and update documentation.** Delete server templates/static assets only after Next routes cover their governed behavior. Document clean setup, production topology, UTC scheduling, restart/migration/recovery operations, environment variables, and browser testing.
12. **Run release gates in order.** Execute `.venv/bin/python -m pytest -q`, `npm --prefix frontend test`, `npm --prefix frontend run test:e2e`, and `npm --prefix frontend run build`. Do not report completion unless all four execute and pass without skips used to satisfy UI criteria.

## Acceptance criteria

### Dashboard routes and mutation safety

- `/`, `/releases`, `/releases/[id]`, `/operations`, and `/settings/schedule` render through the Next.js app router on direct load and client navigation, with usable desktop and mobile layouts and clear empty/loading/error states.
- Any network-reachable dashboard user can use all controls; no role gate is introduced. Approval and rejection nonetheless require independently server-validated, trimmed, nonblank actor and reason.
- Visiting, prefetching, navigating, refreshing, polling, building, or server-rendering any page creates zero scans and zero scan operations. One deliberate Scan now submission creates exactly one manual attempt; disabled/double-clicked controls do not duplicate it.
- Browser-visible requests, response bodies, HTML, JavaScript bundles/source maps, local/session storage, logs, and environment payloads contain no GitHub token or backend secret.

### Schedule and restart behavior

- The database contains exactly one configurable schedule. A save accepts a valid five-field cron expression and enabled flag, labels it UTC, and survives Store/FastAPI restart unchanged; invalid or non-five-field input returns a visible error and does not replace the previous value.
- The schedule view reports expression, enabled state, scheduler health/heartbeat, calculated next run, latest attempted run, latest result, and last error using persisted data. Disabled schedules have no next run and produce no due operations as deterministic time advances.
- A due UTC slot is claimed at most once across scheduler loops/API instances and produces one scheduled operation. Restart resumes future/due scheduling from persisted slot state without duplicate successful execution.
- An API death cannot leave an eternal lock: lease expiry/startup recovery makes the interrupted operation visibly failed or uncertain, records recovery/audit information, and permits a later run. It is never silently marked successful.

### Unified operations and durable lease

- Manual and scheduled triggers call the same runner and existing GitHub scan/classification/draft logic. Both record trigger source, repository, timestamps, scan/evidence, verdict/rationale, result, related pack (if any), safe error, recovery state, and related audit events.
- Release-worthy deterministic commit/PR evidence creates one complete pending draft with proposed version, source scan, evidence-backed notes/body, rationale, announcement, and no automatic decision/publication. Non-release-worthy evidence records a completed non-release operation and no pack.
- The singleton SQLite lease is acquired transactionally and shared by manual and scheduled paths. While one scan is held, every competing trigger records its own auditable `suppressed` operation and performs no GitHub scan or draft creation.
- GitHub read failures produce a failed operation with a safe operator message and audit event. Sensitive exception/transport data is not persisted or returned.

### Packs, governance, publication, and recovery

- Release list/detail responses and pages show every pack with canonical status, proposed version, source operation and scan, commits and pull requests, decision rationale, complete notes/body, announcement, approval/rejection information, publication attempt/outcome, recovery status, and chronological audit timeline.
- No scheduler or page activity approves or publishes a pending pack. Approval with a valid actor/reason records the decision once and immediately invokes the existing governed publication flow exactly once. Success records the receipt and published state.
- Missing/blank actor or reason causes no transition or GitHub write. Rejection with valid fields records actor/reason/audit, becomes terminal after restart, never publishes, and exposes no subsequent approval/publication control.
- Publication exceptions are non-success responses and leave the canonical failed/uncertain attempt visible. Reconciliation records matching/absent/conflict recovery without deleting the original failure, and duplicate decisions/publications remain blocked by durable state guards.

### Migration and compatibility

- Upgrading a database produced by the current repository is transactional and idempotent. Every existing scan, verdict, pack, decision, attempt, reconciliation, and audit row retains its data, identifier, relationship, and order; no reset or destructive migration is required.
- Historical scans/packs are visible through the new operations/releases APIs after backfill. Existing health, pack, audit, approve/reject, explicit publish, and reconcile integrations retain compatible governed behavior except where the specification already requires actor/reason and immediate publication on approval.
- Migration failure rolls back without leaving a partially upgraded schema, and documentation includes backup and upgrade/restart steps.

### Automated gates and documentation

- Backend tests run offline against temporary SQLite databases and deterministic fakes, covering cron parsing, migration preservation, scheduling/restart, lease races/suppression, shared workflows, governance, publication uncertainty, and recovery.
- Frontend unit tests cover mutation safety, schedule validation/display, decision validation, UTC formatting, audit/failure rendering, and accessible controls.
- `npm --prefix frontend run test:e2e` executes real Playwright browser tests for all required routes, no-navigation scan behavior, schedule edit/persistence/restart, scheduled draft creation, manual scans, approval, rejection, audit, suppression, failures, and recovery. Required tests cannot pass by skip, timeout, absent browser, mocked-out page routing, or zero-test execution.
- `npm --prefix frontend run build` produces a successful production Next.js build with all five routes and no secret leakage.
- README and operations documentation are sufficient from a clean checkout and cover Python/npm setup, `GITHUB_TOKEN`, `GITHUB_OWNER`, `GITHUB_REPO`, `RELEASE_MANAGER_DB`, frontend-to-backend server URL, scheduler timing/UTC semantics, durable lease and suppression, restart/recovery, non-destructive migration, production operation, and the exact backend/unit/E2E/build commands.
