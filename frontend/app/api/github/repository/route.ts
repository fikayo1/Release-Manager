import {NextRequest,NextResponse} from 'next/server';
const base=process.env.RELEASE_MANAGER_API_URL||'http://127.0.0.1:8000';
export async function PUT(request:NextRequest){const body=await request.text();const response=await fetch(base+'/api/github/repository',{method:'PUT',headers:{'content-type':'application/json'},body,cache:'no-store'});return new NextResponse(await response.text(),{status:response.status,headers:{'content-type':'application/json'}})}
