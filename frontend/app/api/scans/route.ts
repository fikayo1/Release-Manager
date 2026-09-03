import { api, ApiError } from '@/lib/api';

export async function POST() {
  try {
    return Response.json(await api('/api/scans', { method: 'POST' }), { status: 201 });
  } catch (error) {
    // Pass through the backend's auth / ownership / concurrency signals with
    // their operator-facing detail; collapse everything else to a 502.
    if (error instanceof ApiError && [401, 403, 429].includes(error.status)) {
      return Response.json({ detail: error.detail || error.message }, { status: error.status });
    }
    return Response.json({ detail: 'Scan could not be completed' }, { status: 502 });
  }
}
