export const dynamic = 'force-dynamic';
import { api } from '@/lib/api';
import { guard } from '@/lib/session';
import { utc } from '@/lib/format';
import { ScheduleForm } from '@/components/ScheduleForm';

export default async function Schedule() {
  const s = await guard(() => api<any>('/api/schedule'));
  return (
    <>
      <h1>UTC scan schedule</h1>
      <section>
        <ScheduleForm schedule={s} />
      </section>
      <div className="grid">
        <section>
          <h2>Next run</h2>
          <p>{utc(s.next_run)}</p>
        </section>
        <section>
          <h2>Scheduler health</h2>
          <p>Heartbeat: {utc(s.health.heartbeat_at)}</p>
          <p>Latest run: {utc(s.health.last_run_at)}</p>
          <p>Latest result: {s.health.last_result || 'Not yet'}</p>
          <p>Last error: {s.health.last_error || 'None'}</p>
        </section>
      </div>
    </>
  );
}
