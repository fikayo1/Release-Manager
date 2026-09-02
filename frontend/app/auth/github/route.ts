import {NextResponse} from 'next/server';

function apiBase(): string {
  const value = process.env.RELEASE_MANAGER_API_URL;
  if (!value) throw new Error('RELEASE_MANAGER_API_URL is required');
  return value.replace(/\/$/, '');
}

/** Keep OAuth initiation same-origin while FastAPI remains the credential boundary. */
export async function GET(){
  const upstream=await fetch(apiBase()+'/auth/github',{redirect:'manual',cache:'no-store'});
  const location=upstream.headers.get('location');
  if(!location) return NextResponse.json({detail:'GitHub OAuth is unavailable'},{status:upstream.status});
  const response=NextResponse.redirect(location,upstream.status);
  const cookie=upstream.headers.get('set-cookie');
  if(cookie) response.headers.set('set-cookie',cookie);
  return response;
}
