import json

from src.models import Claim, Pack, Release
from src.phases.rollback import reconcile
from src.store import Store


def approved_store(tmp_path):
    store = Store(str(tmp_path / "state.db"))
    with store.connect() as db:
        db.execute("INSERT INTO scans VALUES('s','{}','now')")
    pack = Pack(
        "p", "s", "1.2.3", "v1.2.3", "Release v1.2.3", "notes", "announcement",
        "minor", (Claim("Features", "feature", "e"),),
    )
    store.save_pack(pack, "t0")
    store.decide("p", "approved", "alice", None, "t1")
    return store


class ExistingRelease:
    def release_for_tag(self, tag):
        return Release(tag, "Release v1.2.3", "notes", "t2", "https://example/release")


def test_interrupted_publish_is_recoverable_and_finalizes_attempt(tmp_path):
    store = approved_store(tmp_path)
    attempt = store.claim_publish("p", "t2")
    # Simulate termination after GitHub accepted the release and before finish().
    assert store.pack("p")["status"] == "publishing"
    assert reconcile(store, ExistingRelease(), "p", "t3") == "matching"
    assert store.pack("p")["status"] == "published"
    with store.connect() as db:
        row = db.execute("SELECT * FROM attempts WHERE id=?", (attempt,)).fetchone()
    assert row["result"] == "success"
    receipt = [event for event in store.audit() if event["kind"] == "publish_success"][-1]
    assert receipt["actor"] == "alice"
    assert receipt["approver"] == "alice"
    assert receipt["version"] == "1.2.3"
    assert receipt["tag"] == "v1.2.3"
    assert receipt["title"] == "Release v1.2.3"
    assert receipt["body"] == "notes"
    assert receipt["publication_result"] == "success"
    assert receipt["url"] == "https://example/release"
