import 'server-only';
const base=process.env.RELEASE_MANAGER_API_URL || 'http://127.0.0.1:8000';
export async function api<T>(path:string, init?:RequestInit):Promise<T>{
 const response=await fetch(base+path,{...init,cache:'no-store',headers:{'content-type':'application/json',...(init?.headers||{})}});
 if(!response.ok) throw new Error(`Release Manager API error (${response.status})`);
 return response.json();
}
