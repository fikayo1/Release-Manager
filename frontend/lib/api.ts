import 'server-only';
import { cookies, headers } from 'next/headers';
import { DEFAULT_TIMEOUT_MS, fetchJson } from './http';

export {
  ApiError,
  ForbiddenError,
  RateLimitedError,
  TimeoutError,
  UnauthorizedError,
} from './http';

function apiBase(): string {
  const value = process.env.RELEASE_MANAGER_API_URL;
  if (!value) throw new Error('RELEASE_MANAGER_API_URL is required');
  return value.replace(/\/$/, '');
}

// The browser session cookie and a same-origin marker are forwarded to
// FastAPI so it can bind the request to a user and enforce same-origin on
// mutating routes. `RELEASE_MANAGER_API_URL` stays server-only.
async function forwardedHeaders(): Promise<Record<string, string>> {
  const forwarded: Record<string, string> = {'x-release-manager-proxy': 'console'};
  try {
    const jar = await cookies();
    // CookieStore.toString() is not consistently populated in server actions.
    const cookie = jar.getAll().map(({name, value}) => `${name}=${value}`).join('; ');
    if (cookie) forwarded.cookie = cookie;
  } catch {
    /* outside a request scope */
  }
  try {
    const incoming = await headers();
    // Route handlers preserve the raw Cookie header even when Next's async
    // CookieStore is empty during an internal server fetch.
    if (!forwarded.cookie) {
      const rawCookie = incoming.get('cookie');
      if (rawCookie) forwarded.cookie = rawCookie;
    }
    const origin = incoming.get('origin');
    // Server components and same-origin route handlers frequently have no
    // browser Origin. Supply the configured public console origin rather than
    // weakening backend CSRF enforcement.
    forwarded.origin = origin || process.env.RELEASE_MANAGER_WEB_URL || '';
    if (!forwarded.origin) delete forwarded.origin;
  } catch {
    /* outside a request scope */
  }
  return forwarded;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const forwarded = await forwardedHeaders();
  return fetchJson<T>(
    apiBase() + path,
    {
      ...init,
      cache: 'no-store',
      headers: { 'content-type': 'application/json', ...forwarded, ...(init?.headers || {}) },
    },
    DEFAULT_TIMEOUT_MS,
  );
}
