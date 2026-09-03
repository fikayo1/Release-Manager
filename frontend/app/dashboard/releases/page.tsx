export const dynamic = 'force-dynamic';
import Link from 'next/link';
import { api } from '@/lib/api';
import { guard } from '@/lib/session';
import { StatusBadge } from '@/components/StatusBadge';

export default async function Releases() {
  const releases = await guard(() => api<any[]>('/api/releases'));
  return (
    <>
      <h1>Release packs</h1>
      {!releases.length ? (
        <div className="card">No release packs yet. Run a scan to collect evidence.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Version</th>
              <th>Status</th>
              <th>Rationale</th>
            </tr>
          </thead>
          <tbody>
            {releases.map((r) => (
              <tr key={r.id}>
                <td>
                  <Link href={`/dashboard/releases/${r.id}`}>{r.version}</Link>
                </td>
                <td>
                  <StatusBadge value={r.status} />
                </td>
                <td>{r.rationale}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
