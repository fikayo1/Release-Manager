"""Small lifespan-owned UTC scheduler using durable slot claims."""
import asyncio
from datetime import datetime, timezone
from .cron import matches

class Scheduler:
    def __init__(self, store, runner, interval=30, clock=lambda: datetime.now(timezone.utc)):
        self.store,self.runner,self.interval,self.clock=store,runner,interval,clock; self.task=None
    async def start(self): self.task=asyncio.create_task(self.loop())
    async def stop(self):
        if self.task:
            self.task.cancel()
            try: await self.task
            except asyncio.CancelledError: pass
    async def tick(self):
        heartbeat=self.clock().astimezone(timezone.utc)
        current=heartbeat.replace(second=0,microsecond=0); slot=current.isoformat()
        # Heartbeat even while disabled so operators can distinguish an idle
        # scheduler from one that was never started.
        with self.store.connect() as db:
            db.execute("UPDATE scheduler_state SET heartbeat_at=? WHERE id=1",(heartbeat.isoformat(),))
        schedule=self.store.schedule()
        if not schedule["enabled"] or not matches(schedule["expression"],current):
            return {"slot": slot, "ran": False, "reason": "not_due"}
        # The operation's durable scheduled_for slot is the claim. Marking a
        # slot only after the operation exists means a crash before creation is
        # retried after restart, while a completed operation is never duplicated.
        claimed = next((item for item in self.store.operations()
                        if item["source"] == "scheduled" and item["scheduled_for"] == slot), None)
        if claimed:
            # Repeat HTTP ticks are operations too: persist a suppression receipt
            # against the canonical slot owner without creating a second slot row.
            self.store.record_suppressed_operation(
                "scheduled", claimed["repository"], heartbeat.isoformat(), slot, "already_claimed"
            )
            return {"slot": slot, "ran": False, "reason": "already_claimed",
                    "operation_id": claimed["id"], "result": "suppressed"}
        result=await asyncio.to_thread(self.runner.run,"scheduled",slot)
        if result.get("id") and result.get("result") != "suppressed":
            with self.store.connect() as db:
                db.execute("UPDATE scheduler_state SET last_slot=?,last_operation_id=?,last_run_at=?,last_result=?,last_error=? WHERE id=1",(slot,result["id"],heartbeat.isoformat(),result["result"],result.get("error")))
        return {"slot": slot, "ran": True, "result": result.get("result"),
                "operation_id": result.get("id"), "repository": result.get("repository")}
    async def loop(self):
        while True:
            try:
                await self.tick()
            except Exception:
                # A transient database/API failure must not permanently stop
                # future schedule evaluation.
                with self.store.connect() as db:
                    db.execute("UPDATE scheduler_state SET last_error=? WHERE id=1",("scheduler tick failed",))
            await asyncio.sleep(self.interval)
