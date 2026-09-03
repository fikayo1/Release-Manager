import {NextRequest,NextResponse} from 'next/server';
const base=process.env.RELEASE_MANAGER_API_URL||'http://127.0.0.1:8000';
export async function PUT(request:NextRequest){
  const body=await request.text();
  // Forward the browser session and origin so FastAPI can bind the request to
  // a user and enforce same-origin on this mutating route.
  const headers:Record<string,string>={'content-type':'application/json'};
  const cookie=request.headers.get('cookie');
  if(cookie) headers.cookie=cookie;
  const origin=request.headers.get('origin');
  if(origin) headers.origin=origin;
  const response=await fetch(base+'/api/github/repository',{method:'PUT',headers,body,cache:'no-store'});
  return new NextResponse(await response.text(),{status:response.status,headers:{'content-type':'application/json'}});
}
