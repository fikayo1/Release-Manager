# Release Manager implementation plan

## Scope and architectural direction

Build the product into the existing FastAPI seed rather than replacing it. The service remains one process, one configured GitHub repository, one SQLite audit database, and one server-rendered operator interface. Runtime behavior is split into the five named governed phases `scan`, `draft`, `review`, `publish`, and `rollback` (where rollback is reconciliation/recovery, not deletion of a GitHub Release). Phase inputs and outputs will be typed and persisted at each boundary. The phase implementations will be registered with the Shipyard phase/gate API available to the build environment; the application will not introduce a generic workflow scheduler or a second autonomy engine. If that runtime API is not actually available in this checkout, the builder must surface that integration gap rather than silently inventing a substitute and claiming Shipyard governance.

The GitHub token is an environment-only secret. `GITHUB_OWNER`, `GITHUB_REPO`, and `GITHUB_TOKEN` are loaded at process startup, are never accepted in request bodies, and are never written to SQLite, responses, audit details, or logs. `RELEASE_MANAGER_DB` may select the SQLite path for deployment/tests. Application startup initializes the schema and performs a real repository-read check before serving traffic. Tests will construct the application with injected settings, clock, database path, and fake raw HTTP transport so they need neither network access nor credentials.

The workflow state is monotonic and enforced in the service layer and database: a scan is an immutable snapshot; only a release-worthy scan can produce one immutable pack; a pack starts pending; exactly one human decision changes it to approved or rejected; only approved packs can begin publishing; uncertain publication must be reconciled against GitHub before any retry; rejected packs and every attempt remain queryable. There is no autonomy-tier input or auto-approval setting.

## Intended files

Existing files to update:

- `src/app.py` — application factory, FastAPI lifespan wiring, dependency assembly, error handling, and retention of `/health`.
- `src/__init__.py` — package metadata/exports only as needed.
- `requirements.txt` — pin/add the minimal server-rendering and form dependencies (`jinja2`, `python-multipart`) while retaining FastAPI, requests, uvicorn, and pytest support.
- `README.md` — operator setup, required environment, database and startup behavior, API/UI workflow, recovery procedure, test commands, real-repository acceptance procedure, and how to inspect the genuine Shipyard build trace.
- `.gitignore` — continue excluding local secrets, virtual environments, caches, and runtime databases without excluding checked-in documentation/evidence manifests.
- `tests/test_health.py` — adapt the smoke test to the application factory so startup validation can be faked without weakening production startup behavior.
- `criteria.json` — do not edit descriptions, verification, order, or IDs; only flip individual `passes` flags after the corresponding checks genuinely pass, as required by the scaffold contract.

Product files to create:

- `src/config.py` — immutable environment settings and fail-fast validation for owner/repository/token/database configuration, with redacted representations.
- `src/models.py` — typed domain records and enums for repository metadata, release baseline, scanned commit/PR evidence, verdict, release pack and claim references, human decision, publish attempt/receipt, reconciliation result, and legal statuses.
- `src/store.py` — hand-written `sqlite3` schema/bootstrap, transactions, guarded state transitions, immutable snapshot/pack writes, append-only audit events, and read models. Tables will cover scans and their captured evidence, verdicts, packs and pack claim references, review decisions, publish attempts, receipts/reconciliation, and audit events. Foreign keys/check constraints and compare-and-set updates will prevent invalid or concurrent transitions.
- `src/github_client.py` — thin direct GitHub REST client over an injected raw request callable. It will expose visibly separate read methods (`repository`, `latest_release`, `commits_since`, `merged_pulls_since`, `release_for_tag`) and the sole write method (`create_release`), implement `Link` pagination and response parsing itself, send bearer/Accept/pinned API-version headers, and map authentication, visibility, rate-limit, GitHub-body, malformed-response, and transport failures to safe specific errors.
- `src/classification.py` — deterministic change normalization and release-worthiness rules with evidence IDs and reasons. PR evidence is the downstream source when the snapshot has merged PRs; commits are the fallback when it does not, while both raw lists remain in the scan. Case-insensitive breaking labels (`breaking`, `breaking-change`, `breaking change`), conventional `!` markers, and `BREAKING CHANGE` markers drive breaking changes; `feat`/feature/enhancement drives features; `fix`/bug drives fixes; docs-only or empty inputs are not release-worthy. Unknown-only change sets are not release-worthy rather than producing an unexplained release.
- `src/versioning.py` — strict semantic-version parsing from the latest published release tag and deterministic major/minor/patch calculation. Leading `v` is preserved for the proposed GitHub tag. For a first release, use `0.0.0` as the calculation base, yielding `1.0.0` for breaking, `0.1.0` for feature, or `0.0.1` for fix; malformed prior release tags fail clearly rather than guessing.
- `src/pack.py` — deterministic pack construction from the stored scan/verdict only: grouped feature/fix/other changelog, GitHub Markdown release title/body, short copyable announcement, version rationale, and an explicit reference from every generated claim/line to evidence in that scan.
- `src/phases/__init__.py` — phase registration/export surface.
- `src/phases/scan.py` — governed read-only scan phase: resolve the latest published non-draft/non-prerelease baseline, use its `published_at` cutoff or repository creation time for the explicit first-release case, collect and persist the exact commit and merged-PR snapshot, then persist the evidence-backed verdict. No call path to `create_release` is present.
- `src/phases/draft.py` — governed draft phase that stops cleanly for a non-worthy verdict and otherwise creates the typed immutable pack from its stored scan without re-fetching GitHub.
- `src/phases/review.py` — mandatory autonomy hold and approve/reject transitions, requiring a nonblank operator identifier and requiring a rejection reason; decisions are timestamped and retained.
- `src/phases/publish.py` — deterministic publish script that loads the already-approved pack, records an attempt before the external call, sends exactly its tag/title/body to `create_release`, and records the returned URL/receipt. It performs no drafting or judgment and never posts the announcement.
- `src/phases/rollback.py` — interrupted/failed publish reconciliation. It checks `release_for_tag` before presenting an action: an existing matching release can be marked resolved and recorded as success; an absent release can be marked retry-safe; a conflicting release blocks both actions for operator investigation. Retry is accepted only from a recorded retry-safe reconciliation and creates a new retained attempt.
- `src/workflow.py` — Release Manager-specific registration/composition of the five phase callables and their gates with the real Shipyard runtime interface. It contains no generic queue, retry scheduler, model agent, autonomy-tier bypass, or alternate phase engine.
- `src/routes.py` — JSON API and HTML routes for starting/viewing scans, viewing verdicts and packs, pending review, approve/reject, publish, reconcile, mark-resolved/retry, and querying audit history. Route handlers delegate all state and authorization checks to phase/services so an alternate route cannot bypass approval.
- `src/templates/base.html` — minimal shared accessible layout and status/error presentation.
- `src/templates/index.html` — configured repository summary, scan action, recent workflow records, and links to audit history.
- `src/templates/scan.html` — baseline/no-prior-release status, fixed cutoff/timestamp, full commit and PR evidence fields/links, and visible verdict rationale.
- `src/templates/review_list.html` — pending packs only, with clear status/version links.
- `src/templates/pack.html` — complete pack, supporting evidence and claim links, human identity/reason form, publish/recovery controls shown only for legal states, and retained decision/attempt history.
- `src/templates/audit.html` — chronological, queryable product audit trail separate from Shipyard build evidence.
- `src/static/style.css` — small local stylesheet; no frontend build or client-side workflow engine.
- `tests/conftest.py` — temporary SQLite/app fixtures, deterministic clock, raw fake GitHub transport/responses, and call recorder that can prove read/write separation.
- `tests/test_config.py` — missing settings, redaction, startup validation, and 401/403/404/rate-limit/transport error behavior.
- `tests/test_github_client.py` — required headers, repository parsing, latest-release 404 semantics, commit `Link` pagination and strict cutoff filtering, pull pagination/early stop and merged-date filtering, first-release metadata, response errors, release lookup, and create payload/receipt parsing.
- `tests/test_scan.py` — prior-release and no-prior-release snapshots with every required evidence field, storage immutability, deterministic PR preference/fallback, and an assertion that scan made zero GitHub write calls.
- `tests/test_classification.py` — release-worthy feature/fix/breaking cases and empty/docs-only/unknown non-worthy cases, all with specific evidence and stated reasons.
- `tests/test_pack.py` — semver precedence/first-release behavior, grouping/rendering, complete pack fields, and invariant that every version/changelog claim references an item in the stored scan.
- `tests/test_review_publish.py` — pending publish refusal, mandatory identity/rejection reason, approval and rejection persistence, retained rejected pack, exact approved payload, receipt/audit data, double-submit/concurrency guards, and absence of an auto-approval path.
- `tests/test_recovery.py` — failure before response, simulated success followed by lost response/process interruption, existing/absent/conflicting release reconciliation, mark-resolved, retry-safe gate, and proof that no retry occurs before a GitHub lookup.
- `tests/test_routes.py` — JSON and server-rendered journeys, pending list/detail evidence, form actions, invalid-state responses, audit queryability, and assurance that API inputs cannot set repository credentials or an autonomy tier.
- `tests/test_security_scope.py` — source/behavior guard tests that secrets are not serialized/logged/persisted, scan is read-only, announcement has no send action/integration, and every publish entry point requires an approved state.
- `tests/test_real_github_acceptance.py` — explicitly opt-in operator test, skipped unless dedicated acceptance environment variables are set, that creates a uniquely tagged release in the designated real test repository and verifies tag/title/body and stored receipt. It must never run in the default offline suite.
- `Dockerfile` — reproducible single-process deployment image with no token baked into layers and a persistent database mount point.
- `.dockerignore` — omit virtualenv, caches, databases, VCS internals, and local secret files from the image context.

No Slack, Discord, generic webhook, model-client, account system, multi-repository, ORM, or release-deletion file/module will be added.

## Build order

1. **Preserve and characterize the seed.** Run the existing tests; introduce the app-factory test fixture without changing `/health`; confirm `criteria.json` remains structurally untouched and that the real Shipyard request/plan/build trace is being produced by the harness rather than fabricated by this product.
2. **Define configuration and domain contracts.** Add `config.py` and `models.py`, including redaction and the complete state machine. Add configuration tests first. This gives every later phase typed, reviewable inputs/outputs.
3. **Create durable storage and audit invariants.** Add `store.py` with idempotent schema bootstrap, foreign keys, UTC timestamps, transactions, uniqueness, immutable evidence/pack records, and guarded transitions. Test restart persistence and illegal/concurrent transitions before adding external effects. Audit events are append-only and reference the relevant scan/pack/attempt.
4. **Build the GitHub seam.** Add `github_client.py` and raw-response fake tests. Validate the repository in FastAPI lifespan. Implement precise errors and pagination in the real client while the fake supplies only status/JSON/headers or a transport exception, ensuring parsing and cutoff logic are genuinely tested. The token may exist only in in-memory settings/client headers.
5. **Implement and verify scan.** Add the scan phase, its phase registration, and tests for both baselines. `releases/latest` 404 means `no_prior_release=true` and repository `created_at` is the first-run cutoff. Commits use `since` plus the default branch, follow `Link`, and are retained only when commit date is strictly after cutoff. Closed PR pages are ordered by `updated` descending, retain only actually merged PRs with `merged_at` strictly after cutoff, and stop after a page whose `updated_at` values are all at/before cutoff. Capture PR labels and merge SHA in addition to displayed number/title/author/date/URL. Store commits and PRs separately without altering GitHub data.
6. **Implement deterministic decision and draft.** Add classification, versioning, pack construction, and their tests. Persist a complete not-worthy verdict and stop before creating a pack. For worthy scans, derive only from the stored snapshot and create claim-to-evidence rows so traceability is machine-checkable, not merely visual.
7. **Add mandatory review hold.** Add review phase and tests for one-time approval/rejection, actor/time/reason audit details, rejection retention, and all illegal transitions. Register it as a mandatory human gate with no autonomy override.
8. **Add deterministic publish and audit receipt.** Add publish phase and tests. In one transaction, atomically claim an approved pack and append an `started` attempt before calling GitHub; then append success with immutable tag/title/body digest/body, URL, timestamp, and approving decision, or append a definitive/uncertain failure. Do not hold a SQLite transaction open during network I/O. All route/script entry points call the same approved-state guard.
9. **Add rollback/reconciliation before enabling retry.** Add the GitHub release-by-tag read and rollback phase. Reconciliation always performs and records a fresh GitHub lookup. A matching existing release is never republished; an absent release is the only state that can enable retry; mismatched tag/title/body is a conflict, not success. Test interruption after GitHub has created the release but before the receipt commit.
10. **Expose API and human UI.** Add routes, templates, and CSS after state rules are covered. Pages must display the proposed version, all pack text, per-claim evidence links, actor/reason history, attempt outcomes, and only state-valid actions. JSON audit endpoints provide the same inspectability. Use POST for mutations and redirect-after-post for forms; validate all inputs server-side. No repository/token configuration endpoint exists.
11. **Wire application lifecycle and Shipyard governance.** Compose settings, client, store, phases, gates, and routes in `app.py`; initialize storage then validate GitHub in lifespan. Register the exact `scan -> draft -> review -> publish -> rollback` phase graph through the harness runtime, with draft ending successfully on a not-worthy verdict and review always holding. Verify phase/gate events appear in the genuine Shipyard execution trace; do not copy Release Manager audit rows into that trace or vice versa.
12. **Deployment and operations.** Add container files and expand README with clean setup, environment variables, persistent volume, startup-failure examples, recovery runbook, API/UI paths, dedicated real-test-repository precautions, and commands for inspecting `.shipyard/trace.db`/`shipyard runs`/yard. The default test and startup documentation must not imply a token can be omitted in production; tests use explicit dependency injection.
13. **End-to-end verification and acceptance updates.** Run `./init.sh` from a clean state and the default offline pytest suite. Exercise two restart-spanning fake-GitHub journeys: docs-only scan stopping with an auditable verdict, and feature/fix scan through approval/publish plus interrupted-publish reconciliation. With operator-provided credentials, run the opt-in real GitHub acceptance once against a designated disposable repository and clean up only manually after evidence capture. Inspect source for forbidden integrations/bypasses and inspect the genuine Shipyard trace. Only then flip each satisfied `criteria.json` `passes` value; never alter criterion text.

## Acceptance criteria

### C1 — fail-loud repository connection

- Startup refuses missing owner/repo/token before an HTTP call and refuses to serve on failed GitHub validation.
- A valid repository check succeeds; 401 says `authentication failed`; 404 says the named repository is `not found or not readable`; rate-limited 403 includes the actual reset time; other 403 responses preserve GitHub's safe error message; transport failures become clear service errors without raw stack traces.
- Every request carries bearer authorization, GitHub JSON Accept, and a pinned API version, while tests/audit/log output never reveal the token.

### C2 — complete, read-only stored scan

- Latest published release time is the cutoff; prereleases/drafts are not baselines. A latest-release 404 is explicit no-prior-release and uses repository creation time to return an inspectable first-release history.
- All post-cutoff default-branch commits and merged PRs are fetched across pages and display identifier, verbatim title, author, commit/merge date, and GitHub URL; PR labels are retained for downstream rules.
- The scan and exact evidence lists/cutoff/capture time survive restart, drafting does not re-scan, and the fake's recorded calls prove no create/update/delete GitHub method ran.

### C3 — evidence-backed worthiness

- Breaking, feature, and fix signals produce a worthy verdict with cited evidence and a short deterministic explanation.
- Empty, docs-only, and unknown-only snapshots produce a complete non-worthy verdict with the available evidence/reason and no pack row.
- No verdict can be persisted with evidence IDs outside its scan.

### C4 — complete traceable pack

- A worthy scan creates a proposed semver/tag, grouped features/fixes/other changelog, GitHub-renderable Markdown notes, short plain Markdown announcement, version rationale, and supporting URLs.
- Every changelog line and bump reason has a persisted foreign-key reference to scanned evidence; tests check all lines (not only three samples).
- Pack generation consumes the immutable stored scan, prefers PRs as specified, and makes no network or announcement-posting call.

### C5 and C12 — mandatory human review with no bypass

- Pending and rejected packs cannot publish. A rejection stores nonblank rejecter/reason/time and leaves the pack and evidence visible.
- Approval requires a nonblank human-supplied identifier and is the only transition to publishable state. There is no auto-approval/tier/config/request field, and every UI/API/script publish path converges on the same approval guard.
- Repeated or competing decisions cannot overwrite the first terminal decision.

### C6 — real GitHub publication and receipt

- Publication sends the immutable approved tag, title, and notes body through the sole GitHub write method; announcement text is excluded.
- Successful publication records the GitHub URL/time, exact published values (and body digest/full approved body), attempt result, and approving decision/actor.
- The opt-in real-repository test verifies the created release via GitHub and is run only by an operator with a designated repository/token.

### C7 — interruption-safe recovery

- An attempt exists durably before the API call. Lost responses and process death leave an uncertain/recoverable record rather than being treated as absent.
- Recovery checks GitHub by tag before either resolution or retry. Existing matching releases become resolved success without another create call; absent releases become retry-safe; conflicts block publication.
- Retry requires a recorded absent reconciliation and creates one new attempt. Repeated reconciliation/mark-resolved requests are idempotent and no state can double-publish.

### C8 — separate queryable audit trail

- The deployed API/UI can query chronological scans, verdicts, packs, human decisions, attempts, reconciliation, and receipts, including actor/reason/result/version/URL/times as applicable.
- Rejections, failures, and uncertain attempts are retained. Audit entries are product records in Release Manager SQLite, not inferred from logs and not conflated with Shipyard's build trace.

### C9 — genuine Shipyard evidence

- The runtime phase graph is registered as scan, draft, review, publish, rollback with visible gates/holds.
- The repository/run documentation points to the actual `.shipyard/trace.db`, `shipyard runs`, or yard view containing request/plan/build/verify/review/accept, retries/gates, and the criteria scorecard. No test fixture or synthetic Release Manager record is presented as this evidence.

### C10 — offline core coverage

- Default `pytest -q` requires no network/token and covers worthy and non-worthy decisions, major/minor/patch derivation, approval and rejection, blocked unapproved publication, exact publish payload, and both recovery outcomes through the raw HTTP seam.
- Tests also cover pagination, first-release behavior, persistence across reopen, invalid transitions, and evidence referential integrity.

### C11 — reproducible setup/deployment

- From a fresh clone, `./init.sh` installs all declared dependencies and the offline suite is green with no seed database/manual migration.
- With only documented owner/repo/token (and optional DB path), uvicorn initializes SQLite, validates GitHub, and serves `/health`; the container follows the same contract and does not contain credentials.

### C13 and v1 scope guardrails

- Announcement output is text for copy/paste only. There is no Slack, Discord, webhook, or generic send route/client and publication never accesses such a service.
- One environment-configured repository and GitHub Releases are the only supported repository/target. No credentials are persisted or accepted over API, and rejected/failed evidence is never deleted.

## Final verification checklist

- `criteria.json` differs only in justified `passes` values.
- Default tests are deterministic, offline, and green after clean initialization.
- Startup validation and all GitHub error mappings are exercised using raw fake responses.
- Stored scans and packs remain identical after GitHub fake data changes, proving snapshot behavior.
- Audit queries show both success and rejection/failure histories after restart.
- Source review finds only one GitHub create-release call site, guarded by approval, and no announcement sender or auto-approval path.
- Interrupted publication is reconciled in both exists/absent cases without duplicate create calls.
- A real acceptance release is verified when credentials are supplied, and its receipt matches the pack.
- Release Manager audit evidence and genuine Shipyard build/runtime trace evidence are both independently inspectable.
