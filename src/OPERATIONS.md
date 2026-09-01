# Release Manager operations

This in-package guide exists because this build phase is restricted to writing
`src/` and `tests/`. The repository-level README should link to or incorporate
it in a later unrestricted phase.

## Clean setup and startup

Run `./init.sh`, then export all three required values:

```bash
export GITHUB_OWNER=my-organization
export GITHUB_REPO=my-repository
export GITHUB_TOKEN='github-token-with-repository-read-and-release-write-access'
# Optional; use a persistent path in production:
export RELEASE_MANAGER_DB=/var/lib/release-manager/release-manager.db
.venv/bin/uvicorn src.app:app
```

Startup creates the SQLite schema and makes an authenticated read of
`GITHUB_OWNER/GITHUB_REPO` before serving. Missing configuration, an invalid
token, an unreadable repository, rate limiting, or transport failure prevents
startup. `GET /health` returns `{"status":"ok"}` only after startup succeeds.
Do not put the token in command-line arguments, API bodies, or the database.

Start the Next.js dashboard with `RELEASE_MANAGER_API_URL=http://127.0.0.1:8000 npm --prefix frontend run dev`, then open `http://127.0.0.1:3000/`. Its operator routes are `/releases`, `/operations`, and `/settings/schedule`, with evidence, audit history, and decisions at `/releases/{id}`. The compatibility server-rendered queue remains at backend route `/review`.

There is currently **no authentication or authorization**: anyone who can reach the service over the network can view packs and submit decisions. Restrict network access accordingly. Both approval and rejection require a named actor and a non-blank reason. Approval immediately attempts GitHub publication. A failed request is not success: the detail page displays the durable uncertain state, and an operator must reconcile before retrying. The FastAPI lifespan starts the UTC scheduler; `/settings/schedule` shows its heartbeat and durable latest outcome.

The compatible JSON workflow is:

1. `POST /api/scans` (read-only scan and deterministic draft when worthy).
2. `GET /api/packs/{id}` to inspect all text and evidence references.
3. `POST /api/packs/{id}/approve` or `/reject` with
   `{"actor":"human name","reason":"..."}`. Approval immediately publishes;
   rejection never does.
4. The explicit `POST /api/packs/{id}/publish` remains for compatible recovery
   clients, but canonical state guards prevent duplicate publication.
5. If publication is uncertain, `POST /api/packs/{id}/reconcile`. An absent
   release makes one retry safe; a matching release records success without a
   duplicate; a conflict requires human investigation.
6. `GET /api/audit` returns chronological retained product evidence.

The announcement is copy/paste text only and is never sent by the service.

## Verification

The default suite is offline and needs no credentials:

```bash
.venv/bin/python -m pytest -q
```

For real acceptance use a dedicated disposable repository and a token supplied
by the operator. Start the service with that repository, scan and inspect the
pack, approve it, publish once, and independently fetch
`GET /repos/{owner}/{repo}/releases/tags/{tag}`. Verify `tag_name`, `name`, and
`body` equal the pack, and verify `/api/audit` has `publish_success`, approver,
version, time, and URL. Release cleanup is deliberately manual; the product has
no delete operation.

## Shipyard evidence

Product audit rows are not Shipyard build evidence. In an environment where
the harness provides Shipyard, inspect the genuine run with `shipyard runs` or
the yard view, and query the harness-created `.shipyard/trace.db` for the
request, plan, build, verify, review, accept phases, gates/retries, and criteria
scorecard. This checkout has no importable Shipyard runtime API; `src/workflow.py`
therefore declares the five application callbacks for harness registration and
does not fabricate a trace or implement a substitute scheduler.
