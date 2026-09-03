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

const base = process.env.RELEASE_MANAGER_API_URL || 'http://127.0.0.1:8000';

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
    const origin = (await headers()).get('origin');
    if (origin) forwarded.origin = origin;
  } catch {
    /* outside a request scope */
  }
  return forwarded;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const forwarded = await forwardedHeaders();
  return fetchJson<T>(
    base + path,
    {
      ...init,
      cache: 'no-store',
      headers: { 'content-type': 'application/json', ...forwarded, ...(init?.headers || {}) },
    },
    DEFAULT_TIMEOUT_MS,
  );
}
