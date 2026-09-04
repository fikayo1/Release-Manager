export const dynamic = 'force-dynamic';
import Link from 'next/link';
import { api } from '@/lib/api';
import { guard } from '@/lib/session';
import { utc } from '@/lib/format';
import { operationTitle } from '@/lib/labels';
import { ScanNowButton } from '@/components/ScanNowButton';
import { StatusBadge } from '@/components/StatusBadge';

export default async function Home() {
  const [operations, releases, schedule] = await guard(() =>
    Promise.all([
      api<any[]>('/api/operations'),
      api<any[]>('/api/releases'),
      api<any>('/api/schedule'),
    ]),
  );
  return (
    <>
      <div className="hero">
        <p className="eyebrow">Governed releases, from evidence to publication</p>
        <h1>Home</h1>
        <ScanNowButton />
      </div>
      <div className="grid">
        <section>
          <h2>Schedule</h2>
          <p>
            {schedule.enabled ? schedule.expression : 'Disabled'} · UTC
          </p>
          <Link href="/dashboard/settings/schedule">Configure schedule</Link>
        </section>
        <section>
          <h2>Recent operations</h2>
          {operations.slice(0, 5).map((o) => (
            <p key={o.id}>
              <StatusBadge value={o.result || o.status} /> {operationTitle(o)} · {utc(o.started_at)}
            </p>
          ))}
          {!operations.length && <p>No operations yet.</p>}
        </section>
        <section>
          <h2>Release packs</h2>
          <p>{releases.length ? `${releases.length} draft${releases.length === 1 ? '' : 's'} ready for review.` : 'No release packs yet. Run a scan to draft one.'}</p>
          <Link href="/dashboard/releases">Review releases</Link>
        </section>
      </div>
    </>
  );
}
