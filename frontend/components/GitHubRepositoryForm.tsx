'use client';
import {useState} from 'react';
export type Repository={full_name:string;private:boolean;html_url:string};
export function GitHubRepositoryForm({repositories,selected}:{repositories:Repository[],selected:string|null}){
 const [value,setValue]=useState(selected||''),[message,setMessage]=useState(''),[busy,setBusy]=useState(false);
 async function save(e:React.FormEvent){e.preventDefault();setBusy(true);setMessage('');try{const r=await fetch('/api/github/repository',{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify({full_name:value})});const data=await r.json();if(!r.ok)throw new Error(data.detail||'Could not save repository');setMessage(`Saved ${data.selected_repository}`)}catch(e){setMessage(e instanceof Error?e.message:'Could not save repository')}finally{setBusy(false)}}
 return <form onSubmit={save}><label htmlFor="repository">Repository</label><select id="repository" value={value} onChange={e=>setValue(e.target.value)} required><option value="">Select a repository</option>{repositories.map(r=><option key={r.full_name} value={r.full_name}>{r.full_name}{r.private?' (private)':''}</option>)}</select><button disabled={busy||!value}>{busy?'Saving…':'Save repository'}</button><p role="status">{message}</p></form>
}
