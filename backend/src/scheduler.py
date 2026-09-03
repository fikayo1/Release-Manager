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
        outcomes = []
        for schedule in self.store.scheduled_users():
            if not matches(schedule["expression"], current):
                continue
            user_id = schedule["user_id"]
            claimed = next((item for item in self.store.scoped_operations(user_id)
                            if item["source"] == "scheduled" and item["scheduled_for"] == slot), None)
            if claimed:
                self.store.record_suppressed_operation("scheduled", claimed["repository"], heartbeat.isoformat(), slot,
                                                       "already_claimed", user_id=user_id)
                outcomes.append({"user_id": user_id, "id": claimed["id"], "result": "suppressed"})
                continue
            result = await asyncio.to_thread(self.runner.run, "scheduled", slot, user_id)
            outcomes.append({"user_id": user_id, **result})
        if outcomes:
            with self.store.connect() as db:
                last = outcomes[-1]
                db.execute("UPDATE scheduler_state SET last_slot=?,last_operation_id=?,last_run_at=?,last_result=?,last_error=? WHERE id=1",
                           (slot, last.get("id"), heartbeat.isoformat(), last.get("result"), last.get("error")))
        return {"slot": slot, "ran": any(item.get("result") != "suppressed" for item in outcomes), "outcomes": outcomes,
                "reason": None if outcomes else "not_due"}
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
