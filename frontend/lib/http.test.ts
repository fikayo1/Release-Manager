import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  ApiError,
  ForbiddenError,
  RateLimitedError,
  TimeoutError,
  UnauthorizedError,
  fetchJson,
} from './http';

const json = (status: number, body: unknown): Response =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

afterEach(() => vi.restoreAllMocks());

describe('fetchJson', () => {
  it('returns parsed JSON on success', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json(200, { ok: true })));
    await expect(fetchJson('http://api.test/x')).resolves.toEqual({ ok: true });
  });

  it('maps status codes to typed errors carrying the server detail', async () => {
    for (const [status, Type] of [
      [401, UnauthorizedError],
      [403, ForbiddenError],
      [429, RateLimitedError],
      [500, ApiError],
    ] as const) {
      vi.stubGlobal('fetch', vi.fn(async () => json(status, { detail: `d-${status}` })));
      const error = await fetchJson('http://api.test/x').catch((e) => e);
      expect(error).toBeInstanceOf(Type);
      expect(error.status).toBe(status);
      expect(error.detail).toBe(`d-${status}`);
    }
  });

  it('rejects with a TimeoutError instead of hanging when the backend stalls', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        (_url: string, init: RequestInit) =>
          new Promise((_resolve, reject) => {
            init.signal?.addEventListener('abort', () =>
              reject(new DOMException('aborted', 'AbortError')),
            );
          }),
      ),
    );
    await expect(fetchJson('http://api.test/slow', {}, 10)).rejects.toBeInstanceOf(TimeoutError);
  });
});
