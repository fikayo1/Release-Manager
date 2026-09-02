# Release Manager operations

Run `./init.sh`, register a GitHub OAuth App whose callback is
`http://127.0.0.1:8000/auth/github/callback`, and start both services:

```bash
export GITHUB_OAUTH_CLIENT_ID=... GITHUB_OAUTH_CLIENT_SECRET=...
export GITHUB_OAUTH_CALLBACK_URL=http://127.0.0.1:8000/auth/github/callback
export SESSION_SECRET='a-long-random-secret'
export RELEASE_MANAGER_WEB_URL=http://127.0.0.1:3000
export RELEASE_MANAGER_DB=/var/lib/release-manager/state.db # optional
.venv/bin/uvicorn src.app:app --port 8000
RELEASE_MANAGER_API_URL=http://127.0.0.1:8000 npm --prefix frontend run dev
```

Open **http://127.0.0.1:3000/settings/github**, choose **Continue with GitHub**,
and select an authorized repository. The OAuth callback and tokens stay in the
backend; protect and encrypt database backups. The `repo` scope permits listing
and publishing to authorized private repositories. A revoked token requires
reconnection. Selection is durable, and each scan records its repository so a
later selection change cannot retarget an existing release.

The selected repository is captured on each `Scan` when the scan starts and is
persisted in the operator SQLite database, so it survives a backend restart on
the same `RELEASE_MANAGER_DB` file and a later selection change never retargets
existing work: reconcile, rollback/reject, approval, and publication for a pack
always resolve credentials against that pack's scan-captured repository, while
only the next manual scan and the next due scheduled scan follow the new
selection.

For non-interactive legacy automation only, the complete `GITHUB_OWNER`,
`GITHUB_REPO`, and `GITHUB_TOKEN` triple may replace all OAuth/session settings.
Partial legacy configuration is rejected.

Dashboard routes are `/`, `/releases`, `/operations`, `/settings/github`, and
`/settings/schedule`; release details are `/releases/{id}`. The compatibility
server-rendered queue is the backend `/review` route and health is `/health`.
There is no application role gate, so restrict network access.

Approval and rejection require an actor and reason. Approval immediately
publishes. An uncertain publish must be reconciled before retrying. Navigation
and refresh are read-only; only **Scan now** or an enabled due UTC schedule
starts a scan. The API workflow is `POST /api/scans`, inspect
`GET /api/releases/{id}`, then `POST /api/packs/{id}/approve` or `/reject`.
Use `POST /api/packs/{id}/reconcile` for uncertain publication and inspect
`GET /api/audit` for retained receipts.

Verify with:

```bash
.venv/bin/python -m pytest -q
npm --prefix frontend test
npm --prefix frontend run test:e2e
npm --prefix frontend run build
```

Browser binaries are provisioned by an operator, not by package scripts.
