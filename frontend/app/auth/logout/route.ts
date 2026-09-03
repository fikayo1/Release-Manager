import { NextResponse, type NextRequest } from 'next/server';

// Minimal sign-out glue: expire the browser session cookie and return to the
// public landing page. The server-side session row is inert once the cookie is
// gone; no backend call is required.
const SESSION_COOKIE = 'release_manager_session';

function clear(request: NextRequest) {
  const response = NextResponse.redirect(new URL('/', request.url), 303);
  response.cookies.set(SESSION_COOKIE, '', {
    path: '/',
    maxAge: 0,
    httpOnly: true,
    sameSite: 'lax',
  });
  return response;
}

export async function POST(request: NextRequest) {
  return clear(request);
}

// GET fallback so a plain link also signs out.
export async function GET(request: NextRequest) {
  return clear(request);
}
