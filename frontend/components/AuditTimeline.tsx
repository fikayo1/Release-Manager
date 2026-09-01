import {utc} from '@/lib/format';
export function AuditTimeline({events}:{events:any[]}){return <ol className="timeline">{events.map(e=><li key={e.id}><strong>{e.kind.replaceAll('_',' ')}</strong> <time>{utc(e.created_at)}</time>{e.actor&&<span> by {e.actor}</span>}<pre>{JSON.stringify(e.detail,null,2)}</pre></li>)}</ol>}
