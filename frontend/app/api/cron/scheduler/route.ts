import {NextRequest, NextResponse} from 'next/server';
import {timingSafeEqual} from 'node:crypto';

const VERCEL_CRON_USER_AGENT = 'vercel-cron/1.0';

function equal(left: string, right: string): boolean {
  const a = Buffer.from(left);
  const b = Buffer.from(right);
  return a.length === b.length && timingSafeEqual(a, b);
}

/**
 * Handle the GET request issued by Vercel Cron.
 *
 * Vercel supplies the configured CRON_SECRET as a bearer token and identifies
 * scheduled invocations with User-Agent: vercel-cron/1.0. The legacy marker is
 * retained for local/backwards-compatible callers, but is not required from
 * Vercel itself.
 */
async function handleCron(request: NextRequest) {
  const secret = process.env.CRON_SECRET ?? '';
  const authorization = request.headers.get('authorization') ?? '';
  const vercelInvocation = equal(
    request.headers.get('user-agent')?.trim().toLowerCase() ?? '',
    VERCEL_CRON_USER_AGENT,
  );
  const legacyInvocation = Boolean(request.headers.get('x-vercel-cron'));

  if (!secret || (!vercelInvocation && !legacyInvocation) || !equal(authorization, `Bearer ${secret}`)) {
    return NextResponse.json({detail: 'unauthorized'}, {status: 401});
  }

  const base = process.env.RELEASE_MANAGER_API_URL;
  if (!base) return NextResponse.json({detail: 'scheduler unavailable'}, {status: 503});

  // The internal FastAPI endpoint is intentionally POST-only. Translate the
  // authenticated Vercel GET into its two-factor internal request.
  const upstream = await fetch(`${base.replace(/\/$/, '')}/scheduler/tick`, {
    method: 'POST',
    redirect: 'manual',
    cache: 'no-store',
    headers: {authorization, 'x-vercel-cron': '1'},
  });
  return new NextResponse(await upstream.text(), {
    status: upstream.status,
    headers: {'content-type': upstream.headers.get('content-type') ?? 'application/json'},
  });
}

export const GET = handleCron;
// Kept for manual smoke tests and existing integrations; Vercel Cron uses GET.
export const POST = handleCron;
