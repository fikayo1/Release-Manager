"""Unified durable runner for manual and scheduled scans."""
from datetime import datetime, timedelta, timezone
from threading import Event, Thread
from uuid import uuid4
from .models import primitive
from .phases import scan, draft


def utcnow(): return datetime.now(timezone.utc)

def iso(value): return value.astimezone(timezone.utc).isoformat()

class OperationRunner:
    def __init__(self, store, github, owner=None, lease_seconds=300, clock=utcnow):
        self.store,self.github,self.owner,self.lease_seconds,self.clock=store,github,owner or str(uuid4()),lease_seconds,clock

    def run(self, source="manual", scheduled_for=None):
        operation_id=str(uuid4()); moment=self.clock(); now=iso(moment)
        repository=f"{self.github.owner}/{self.github.repo}"
        self.store.create_operation(operation_id,source,repository,now,scheduled_for)
        if not self.store.acquire_lease(self.owner,operation_id,now,iso(moment+timedelta(seconds=self.lease_seconds))):
            self.store.finish_operation(operation_id,"suppressed",now)
            return self.store.operation(operation_id)
        stop_renewal = Event()
        def renew():
            # A scan may legitimately take longer than its initial lease. Keep
            # ownership durable until the operation has reached a terminal state.
            while not stop_renewal.wait(max(1, self.lease_seconds / 3)):
                instant = self.clock()
                self.store.renew_lease(
                    self.owner, operation_id, iso(instant),
                    iso(instant + timedelta(seconds=self.lease_seconds)),
                )
        renewal = Thread(target=renew, daemon=True)
        renewal.start()
        try:
            snapshot,verdict=scan(self.store,self.github,now)
            pack=draft(self.store,snapshot,verdict,now)
            result="draft_created" if pack else "non_release"
            self.store.finish_operation(operation_id,result,iso(self.clock()),snapshot.id,pack.id if pack else None)
        except Exception:
            self.store.finish_operation(operation_id,"failed",iso(self.clock()),error="GitHub scan failed; review credentials, connectivity, and repository access")
        finally:
            stop_renewal.set()
            renewal.join(timeout=1)
            self.store.release_lease(self.owner,operation_id)
        return self.store.operation(operation_id)
