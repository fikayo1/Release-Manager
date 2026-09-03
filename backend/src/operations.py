"""Unified durable runner for manual and scheduled scans."""
from datetime import datetime, timedelta, timezone
from threading import Event, Thread
from uuid import uuid4
from .models import primitive
from .db import is_integrity_error
from .phases import scan, draft


def utcnow(): return datetime.now(timezone.utc)

def iso(value): return value.astimezone(timezone.utc).isoformat()

class OperationRunner:
    def __init__(self, store, github=None, owner=None, lease_seconds=300, clock=utcnow, client_provider=None):
        self.store,self.github,self.owner,self.lease_seconds,self.clock=store,github,owner or str(uuid4()),lease_seconds,clock
        self.client_provider=client_provider

    def run(self, source="manual", scheduled_for=None):
        operation_id=str(uuid4()); moment=self.clock(); now=iso(moment)
        if self.client_provider:
            connection=self.store.github_connection()
            repository=connection.get("selected_repository") if connection and connection.get("status")=="connected" else None
            if not repository:
                repository="unconfigured"
                self.store.create_operation(operation_id,source,repository,now,scheduled_for)
                self.store.finish_operation(operation_id,"reconnect_required",now,error="Connect GitHub and select a repository")
                return self.store.operation(operation_id)
            github=self.client_provider(repository)
        else:
            github=self.github
            repository=f"{github.owner}/{github.repo}"
        try:
            self.store.create_operation(operation_id,source,repository,now,scheduled_for)
        except Exception as exc:
            if not is_integrity_error(exc):
                raise
            # Keep one canonical row per slot, but durably attach a suppression
            # receipt to it so duplicate invocations are not merely synthetic
            # in-memory outcomes.
            claimed_id = self.store.record_suppressed_operation(
                source, repository, now, scheduled_for, "duplicate_slot"
            )
            return {"id": claimed_id, "source": source, "repository": repository,
                    "status": "completed", "result": "suppressed", "error": None,
                    "scan_id": None, "pack_id": None, "started_at": now,
                    "finished_at": now, "scheduled_for": scheduled_for}
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
            snapshot,verdict=scan(self.store,github,now)
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
