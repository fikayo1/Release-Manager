import {NextRequest, NextResponse} from 'next/server';

function apiBase(): string {
  const value = process.env.RELEASE_MANAGER_API_URL;
  if (!value) throw new Error('RELEASE_MANAGER_API_URL is required');
  return value.replace(/\/$/, '');
}

/** Complete OAuth through the public web origin while FastAPI owns the state. */
export async function GET(request: NextRequest) {
  const upstream = await fetch(`${apiBase()}/auth/github/callback${request.nextUrl.search}`, {
    headers: {cookie: request.headers.get('cookie') ?? ''},
    redirect: 'manual',
    cache: 'no-store',
  });
  const location = upstream.headers.get('location');
  if (!location) {
    return NextResponse.json({detail: 'GitHub OAuth callback failed'}, {status: upstream.status});
  }
  const response = NextResponse.redirect(location, upstream.status);
  const cookie = upstream.headers.get('set-cookie');
  if (cookie) response.headers.set('set-cookie', cookie);
  return response;
}
