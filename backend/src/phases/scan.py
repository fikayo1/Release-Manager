from uuid import uuid4
from ..classification import classify
from ..models import Scan

def scan(store,github,now):
    repo=github.repository(); baseline=github.latest_release(); cutoff=baseline.published_at if baseline else repo.created_at
    snapshot=Scan(str(uuid4()),f"{github.owner}/{github.repo}",now,cutoff,baseline is None,baseline.tag if baseline else None,github.commits_since(cutoff,repo.default_branch),github.merged_pulls_since(cutoff))
    verdict=classify(snapshot); store.save_scan(snapshot,verdict,now); return snapshot,verdict
