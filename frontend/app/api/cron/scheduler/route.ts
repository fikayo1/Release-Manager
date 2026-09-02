import {NextRequest, NextResponse} from 'next/server';
import {timingSafeEqual} from 'node:crypto';

function equal(left: string, right: string): boolean {
  const a = Buffer.from(left); const b = Buffer.from(right);
  return a.length === b.length && timingSafeEqual(a, b);
}

export async function POST(request: NextRequest) {
  const secret = process.env.CRON_SECRET ?? '';
  const authorization = request.headers.get('authorization') ?? '';
  const marker = request.headers.get('x-vercel-cron');
  if (!secret || !marker || !equal(authorization, `Bearer ${secret}`)) {
    return NextResponse.json({detail: 'unauthorized'}, {status: 401});
  }
  const base = process.env.RELEASE_MANAGER_API_URL;
  if (!base) return NextResponse.json({detail: 'scheduler unavailable'}, {status: 503});
  const upstream = await fetch(`${base.replace(/\/$/, '')}/scheduler/tick`, {
    method: 'POST', redirect: 'manual', cache: 'no-store',
    headers: {authorization, 'x-vercel-cron': '1'},
  });
  return new NextResponse(await upstream.text(), {
    status: upstream.status,
    headers: {'content-type': upstream.headers.get('content-type') ?? 'application/json'},
  });
}
