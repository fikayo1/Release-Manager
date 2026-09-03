import { NextResponse, type NextRequest } from 'next/server';

// Edge-safe auth gate: no DB access, no secret — it reads only the presence of
// the opaque session cookie. A cookie-less visitor to any `/dashboard` route is
// redirected to `/login` before a single dashboard component runs (no data
// fetch, no action). Stale/invalid cookies are handled by `guard()` server-side.
const SESSION_COOKIE = 'release_manager_session';

export function middleware(request: NextRequest) {
  if (request.cookies.get(SESSION_COOKIE)?.value) {
    return NextResponse.next();
  }
  const url = request.nextUrl.clone();
  url.pathname = '/login';
  url.search = '';
  return NextResponse.redirect(url, 307);
}

export const config = {
  matcher: ['/dashboard/:path*'],
};
