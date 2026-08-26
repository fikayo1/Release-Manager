# Release Manager review interface plan

## Approach

Add a progressively enhanced, server-rendered review UI to the existing FastAPI application. The current SQLite store, pack identifiers/statuses, decision functions, publication/reconciliation behavior, JSON API, and audit records remain canonical; HTML routes will call the same workflow functions rather than implement a parallel state machine. Jinja templates and a local stylesheet are sufficient—there will be no SPA, frontend framework, or asset build.

The existing `/api/...` routes remain available to CLI and cron clients. Their decision validation will be aligned with the new contract: both approval and rejection require a non-blank human reason. Approval will execute the existing approval transition and immediately invoke the existing publication phase. If GitHub publication fails, the response will be an error and the store's canonical non-success publication state/audit record will remain visible; neither JSON nor HTML will claim publication succeeded. Rejection will retain the pack and record its rejected status, actor, reason, and audit event.

No authentication is added. Network access is the current access boundary and the pages will state actions plainly without implying authorization that does not exist.

## Files to change or create

### Existing files to update

- `requirements.txt` — add the minimal Jinja template and HTML form parsing dependencies, with no JavaScript framework or build tooling.
- `src/app.py` — mount the local static directory, configure template-capable routing as needed, and retain the existing application factory, startup repository validation, `/health`, and dependency injection used by tests.
- `src/routes.py` — retain all existing JSON endpoints and add HTML list/detail/decision routes. Add shared decision request validation and orchestration so approval requires a reason and triggers publication, rejection requires a reason, API errors remain truthful, HTML form failures render useful messages, and successful form posts use redirect-after-post.
- `src/phases/review.py` — pass the required approval reason into the canonical store decision operation, keeping review transitions centralized.
- `src/store.py` — require a non-blank reason for both decision types and add read-only queries/view support for reverse-chronological pack listing, scan evidence, and pack-scoped chronological audit activity. Existing durable transition, attempt, and audit semantics remain intact.
- `src/OPERATIONS.md` — document the review URLs, no-auth/network-access posture, approval-publishes behavior, failure/recovery expectations, and the required `GITHUB_TOKEN`, `GITHUB_OWNER`, and `GITHUB_REPO` variables while preserving API/CLI guidance.
- `tests/test_governance.py` — update approval tests for mandatory reasons and verify both decision types persist their reasons.
- `tests/test_recovery_audit.py` — update fixtures/calls for reason-required approval while retaining interrupted-publication coverage.

### New UI files

- `src/templates/base.html` — accessible document shell, local stylesheet link, semantic status/error region, and shared page structure.
- `src/templates/review_list.html` — primary review page with the reverse-chronological pack collection, connected vertical status timeline sidebar, selected/current fallback behavior, and a card for every pack.
- `src/templates/pack_detail.html` — full pack review showing version, status, changelog, release notes, announcement, supporting commit/PR links, audit history, and state-appropriate approve/reject forms.
- `src/static/review.css` — responsive minimalist styling: white background, sans-serif type, generous spacing, 1px borders, no shadows, timeline dots/connectors, large metric values with small muted labels, and semantic amber/green/red/blue color use only.

No JavaScript file is planned because all navigation, validation, submission, and feedback can work with ordinary links and forms. JavaScript should be added only if a later implementation identifies a small enhancement that leaves the complete no-JavaScript flow intact.

### New or expanded tests

- `tests/test_review_ui.py` — server-rendered list/detail tests covering ordering, selection fallback, timeline/card content, semantic statuses, published metrics, evidence links, action visibility, non-JavaScript form submission, validation errors, success redirects, and truthful publication failure rendering.
- `tests/test_routes.py` — API regression tests proving existing pack/audit routes remain usable, approve/reject both reject blank reasons, approval immediately attempts publication, rejection does not publish, and publication errors do not return success.

Implementation may place small private view-model helpers in `src/routes.py`. A separate `src/view_models.py` should be created only if route preparation becomes large enough to obscure request handling; it is not otherwise planned.

## Build order

1. **Characterize existing contracts.** Run the current offline tests and inspect the pack, scan, status, publication, reconciliation, and audit representations. Preserve route paths and response shapes except for the specified mandatory approval reason and approval-triggered publication behavior.
2. **Add read models and decision validation.** Extend `Store` with deterministic reverse-chronological pack listing, scan lookup, and pack audit filtering. Enforce trimmed, non-blank reasons for approval and rejection at the store boundary so HTML, API, and direct workflow callers cannot bypass the rule. Update review phase signatures and focused governance/recovery tests.
3. **Unify API decision orchestration.** Update the existing approve endpoint to validate actor/reason, record approval, and immediately invoke publication; update rejection validation without introducing a write. Map validation/state errors to non-success API responses and external publication failures to non-success responses while relying on the existing durable attempt/status/audit handling. Keep the explicit publish and reconciliation endpoints for compatibility and recovery, subject to their canonical status guards.
4. **Build presentation view data.** For each pack, combine canonical pack data with its creation time, relevant audit events, and stored scan evidence. Sort packs by creation timestamp descending with a deterministic ID tie-break. Honor an explicit canonical current marker if one becomes available; because the current model has no such marker, select the newest pack by default. Derive published-only metrics from the stored scan and rendered changelog: commit count, pull-request count, and count of non-blank changelog item lines.
5. **Add templates and styling.** Implement the shared shell, review list, pack detail, and local CSS. Use semantic HTML, visible keyboard focus, labels associated with fields, status text in addition to color, real links, and responsive layout. Do not rely on client-side rendering or submission.
6. **Wire HTML routes.** Make the primary review route render all packs and accept a selected pack query/path state. Add a stable full-review URL per pack and POST approve/reject form routes. Missing packs return a real 404 page/response; invalid reasons and workflow/publication errors re-render the detail with a visible error and proper non-success status; successful decisions redirect to the canonical detail page.
7. **Add UI and API regression tests.** Exercise empty, pending/in-progress, published/healthy, rejected/failed, and mixed datasets. Use a fake GitHub publisher to verify exact write counts and failure behavior. Parse returned HTML and assert meaningful content/classes/links rather than relying on screenshots alone.
8. **Update operator documentation and verify.** Document startup and UI/API use, explicitly naming `GITHUB_TOKEN`, `GITHUB_OWNER`, and `GITHUB_REPO`. Run the complete offline test suite and manually inspect representative pages at desktop and narrow widths with JavaScript disabled.

## Acceptance criteria

### Review list and timeline

- The primary HTML review page returns 200 with zero packs and presents a useful empty state.
- With packs present, every durable pack appears exactly once in both the main card collection and timeline, ordered newest creation timestamp first.
- The timeline is vertical, uses connected dots, and provides readable status text; meaning is not conveyed by color alone.
- An explicitly current canonical pack is selected when such data exists; otherwise the newest pack is highlighted. Selection remains understandable without JavaScript.
- Every card shows version, canonical status pill, timestamped pack-specific audit activity, and a working link to the full review page.
- Published cards alone show correct commit, pull-request, and changelog-line metric tiles. Metric values are prominent and labels are small/muted.

### Full pack review

- A valid detail URL displays canonical version/status and the complete changelog, release notes, announcement text, and rationale where available, without silently modifying stored content.
- Supporting commits and pull requests come from the pack's stored scan and include safe, clickable GitHub URLs plus identifying text.
- Pending and active in-progress review states expose both approve and reject forms. Terminal published, rejected, failed/conflict, or uncertain states do not offer an invalid fresh decision; their status and audit outcome remain visible.
- Both forms contain labeled actor and reason inputs, and reason is required by HTML and independently enforced server-side after whitespace trimming.
- Unknown pack IDs return HTTP 404 rather than an empty or misleading success page.

### Decisions, publication, and errors

- Blank or whitespace-only approval and rejection reasons are rejected through HTML, JSON API, and direct store/workflow paths, with no status transition or GitHub write.
- A valid rejection records the actor and reason, changes the durable pack status to rejected, adds a timestamped audit event, remains visible after database reopen, and never calls GitHub publication.
- A valid approval records actor/reason and immediately makes exactly one publication attempt using the existing publication phase. On success, the durable status is published, the release receipt appears in audit activity, and HTML redirects to the updated detail.
- A GitHub/API publication exception produces a non-success HTTP response and visible error, while the durable pack status/attempt/audit reflect the canonical uncertain or failed outcome. No page or API payload reports publication success or published status unless the store recorded it.
- Invalid/repeated/concurrent decisions continue to be rejected by canonical compare-and-set guards. The existing explicit publish/reconcile APIs remain available for CLI/cron compatibility and recovery but cannot bypass legal status transitions.

### Styling, accessibility, and progressive enhancement

- Pages work end to end with JavaScript disabled: list/detail navigation, reason entry, approve/reject submission, errors, and success navigation.
- Layout uses a white background, sans-serif type, whitespace, 1px borders, and no shadows. Amber/orange is limited to pending/in-progress, green to published/healthy, red to rejected/failed, and blue to links.
- Forms have explicit labels, controls are keyboard reachable, focus is visible, headings/landmarks are ordered meaningfully, and status/error text is announced/readable without color.
- At narrow viewport widths the timeline and cards remain readable without horizontal page scrolling or overlapping controls.
- All assets are local and directly served by FastAPI; there is no frontend framework, SPA runtime, Node dependency, CDN requirement, or asset compilation step.

### Compatibility, security scope, and operations

- Existing health, scan, pack, publish/reconcile, and audit API routes continue to work for non-browser clients, with decision request changes limited to the specified required reason and immediate approval publication behavior.
- UI routes do not accept or expose repository credentials. No authentication/authorization behavior is implied or added; documentation clearly says anyone with network access may view and act for now.
- Operator documentation explicitly names and explains `GITHUB_TOKEN`, `GITHUB_OWNER`, and `GITHUB_REPO`, and describes publication failure/reconciliation without suggesting a failed action succeeded.
- The complete default `pytest` suite is offline and passes using temporary SQLite databases and fake GitHub clients, including representative pending, published, rejected, failed/uncertain, and empty UI states.
