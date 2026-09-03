// Human-readable wording for the raw tokens the backend stores on scans,
// operations, packs, and audit rows. The Operations and overview views must
// never surface a bare token such as "non_release" or "Non Release manual".

const TITLES: Record<string, string> = {
  non_release: 'No release needed',
  draft_created: 'Release draft created',
  reconnect_required: 'GitHub reconnect required',
  suppressed: 'Duplicate run suppressed',
  failed: 'Scan failed',
  running: 'Scan running',
  completed: 'Scan complete',
  published: 'Published',
  uncertain: 'Publication uncertain',
  rejected: 'Rejected',
  approved: 'Approved',
  pending: 'Awaiting decision',
  publishing: 'Publishing',
  retry_safe: 'Safe to retry',
  conflict: 'Publication conflict',
};

const SOURCES: Record<string, string> = {
  manual: 'Manual scan',
  scheduled: 'Scheduled scan',
  legacy: 'Legacy scan',
};

export function humanize(value?: string | null): string {
  if (!value) return 'Unknown';
  return value
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function statusLabel(value?: string | null): string {
  if (!value) return 'Unknown';
  return TITLES[value] ?? humanize(value);
}

export function sourceLabel(value?: string | null): string {
  if (!value) return 'Scan';
  return SOURCES[value] ?? `${humanize(value)} scan`;
}

// A single line describing an operation: "<source> — <result/status>".
export function operationTitle(op: {
  source?: string | null;
  result?: string | null;
  status?: string | null;
}): string {
  return `${sourceLabel(op.source)} — ${statusLabel(op.result || op.status)}`;
}
