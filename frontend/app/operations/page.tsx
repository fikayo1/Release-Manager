import {api} from '@/lib/api';
import {utc} from '@/lib/format';
import {operationTitle, statusLabel} from '@/lib/labels';
import {StatusBadge} from '@/components/StatusBadge';
import {AuditTimeline} from '@/components/AuditTimeline';

export default async function Operations() {
  const items = await api<any[]>('/api/operations');
  return (
    <>
      <h1>Operations</h1>
      {!items.length ? (
        <div className="card">No scan operations yet.</div>
      ) : (
        <div className="grid">
          {items.map((o) => (
            <article className="card" key={o.id}>
              <h2>{operationTitle(o)}</h2>
              <p>
                <StatusBadge value={o.result || o.status} />{' '}
                <span>{statusLabel(o.result || o.status)}</span>
              </p>
              <p>{o.repository}</p>
              <p>Started {utc(o.started_at)}</p>
              {o.finished_at && <p>Finished {utc(o.finished_at)}</p>}
              {o.scheduled_for && <p>Scheduled for {utc(o.scheduled_for)}</p>}
              {o.scan_id && <p>Source scan {o.scan_id}</p>}
              {o.error && <p role="alert">{o.error}</p>}
              {o.pack_id && (
                <>
                  <a href={`/releases/${o.pack_id}`}>Related release</a>
                  <p>Release state: {statusLabel(o.pack_status)}</p>
                </>
              )}
              <AuditTimeline events={o.activity || []} />
            </article>
          ))}
        </div>
      )}
    </>
  );
}
