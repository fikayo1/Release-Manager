import 'server-only';
import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { UnauthorizedError } from './api';

// The signed, opaque, HttpOnly session cookie minted by FastAPI on the OAuth
// legs. Only its presence is inspected here — never its contents.
export const SESSION_COOKIE = 'release_manager_session';

/** Cookie-presence check for the public marketing CTA. No backend round-trip. */
export async function hasSession(): Promise<boolean> {
  const jar = await cookies();
  return Boolean(jar.get(SESSION_COOKIE)?.value);
}

/**
 * Defense-in-depth wrapper for every `/dashboard/**` server-component data
 * load. `middleware.ts` already redirects a cookie-less visitor to `/login`;
 * this additionally catches a stale/invalid cookie that survived the presence
 * check and turns the resulting 401 into the same redirect, so no other user's
 * shell can render. All other errors propagate to the segment error boundary.
 */
export async function guard<T>(load: () => Promise<T>): Promise<T> {
  try {
    return await load();
  } catch (error) {
    if (error instanceof UnauthorizedError) redirect('/login');
    throw error;
  }
}
