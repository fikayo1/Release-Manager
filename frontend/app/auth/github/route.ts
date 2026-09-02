import {NextResponse} from 'next/server';

const base=process.env.RELEASE_MANAGER_API_URL || 'http://127.0.0.1:8000';

/** Keep OAuth initiation same-origin while FastAPI remains the credential boundary. */
export async function GET(){
  const upstream=await fetch(base+'/auth/github',{redirect:'manual',cache:'no-store'});
  const location=upstream.headers.get('location');
  if(!location) return NextResponse.json({detail:'GitHub OAuth is unavailable'},{status:upstream.status});
  const response=NextResponse.redirect(location,upstream.status);
  const cookie=upstream.headers.get('set-cookie');
  if(cookie) response.headers.set('set-cookie',cookie);
  return response;
}
