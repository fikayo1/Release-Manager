export const dynamic = 'force-dynamic';
import { notFound } from 'next/navigation';
import { api, UnauthorizedError } from '@/lib/api';
import { guard } from '@/lib/session';
import { StatusBadge } from '@/components/StatusBadge';
import { DecisionForm } from '@/components/DecisionForm';
import { AuditTimeline } from '@/components/AuditTimeline';

export default async function Release({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const p: any = await guard(async () => {
    try {
      return await api(`/api/releases/${id}`);
    } catch (error) {
      if (error instanceof UnauthorizedError) throw error;
      return null;
    }
  });
  if (!p) return notFound();
  return (
    <>
      <h1>{p.title}</h1>
      <p>
        <StatusBadge value={p.status} /> Version {p.version} · source scan {p.scan_id}
      </p>
      <section>
        <h2>Rationale</h2>
        <p>{p.rationale}</p>
        <h2>Release notes</h2>
        <pre>{p.body}</pre>
        <h2>Announcement</h2>
        <p>{p.announcement}</p>
      </section>
      <section>
        <h2>Evidence</h2>
        {[...(p.evidence.commits || []), ...(p.evidence.pulls || [])].map((e: any) => (
          <p key={e.id}>
            <a href={e.url}>{e.title}</a> — {e.author}
          </p>
        ))}
      </section>
      {p.status === 'pending' && <DecisionForm id={id} />}
      <section>
        <h2>Publication</h2>
        <pre>{JSON.stringify(p.publication, null, 2)}</pre>
      </section>
      <section>
        <h2>Audit timeline</h2>
        <AuditTimeline events={p.activity} />
      </section>
    </>
  );
}
