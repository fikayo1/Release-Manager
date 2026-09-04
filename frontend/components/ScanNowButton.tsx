'use client';
import Link from 'next/link';
import { useState } from 'react';

type ScanResult = { result?: string; pack_id?: string; detail?: string };

export function ScanNowButton() {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [packId, setPackId] = useState<string | null>(null);
  async function run() {
    setBusy(true); setMessage(''); setPackId(null);
    try {
      const response = await fetch('/api/scans', { method: 'POST' });
      const data: ScanResult = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Scan failed');
      setMessage(data.result === 'suppressed' ? 'Suppressed: another scan is running' : `Completed: ${data.result}`);
      if (data.pack_id) setPackId(data.pack_id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Scan failed');
    } finally { setBusy(false); }
  }
  return <div>
    <button disabled={busy} onClick={run}>{busy ? 'Scanning…' : 'Scan now'}</button>
    <p role="status">{message}{packId && <> · <Link href={`/dashboard/releases/${packId}`}>Review draft {packId}</Link></>}</p>
  </div>;
}
