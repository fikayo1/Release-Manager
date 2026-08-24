# release-manager

Scaffolded by Shipyard from the `release-manager` topology.

```bash
./init.sh                          # install
.venv/bin/python -m pytest -q      # test
.venv/bin/uvicorn src.app:app --reload   # run
```

`criteria.json` is the definition of done. Every entry starts `passes: false`.
Later phases may only flip that flag — never edit or remove a criterion.

This is a seed, not a release manager yet. `/health` is the only route. The
GitHub client, the scan/draft/review/publish/rollback phases, the review
interface's approve/reject routes, and the audit-trail schema are what the
build phases that follow this scaffold are for.
