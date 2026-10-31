import type { StudioFile, Job, Capability, ToolOptions } from './types';
let token:string|null=sessionStorage.getItem('studio-token');
let pending:Promise<void>|null=null;
const timeoutSignal=(ms=30000)=>AbortSignal.timeout(ms);
async function init(){
  if(token)return;
  if(!pending)pending=fetch('/api/session',{method:'POST',signal:timeoutSignal()}).then(async r=>{if(!r.ok)throw new Error('Could not start the local processing API.');const data=await r.json();token=data.token;sessionStorage.setItem('studio-token',token!);}).finally(()=>{pending=null;});
  await pending;
}
async function request<T=any>(url:string,options:RequestInit={}):Promise<T>{
  await init();const headers=new Headers(options.headers);headers.set('Authorization',`Bearer ${token}`);
  if(options.body&&!(options.body instanceof FormData))headers.set('Content-Type','application/json');
  let r=await fetch(url,{...options,headers,signal:options.signal?AbortSignal.any([options.signal,timeoutSignal(60000)]):timeoutSignal(60000)});
  if(r.status===401){token=null;sessionStorage.removeItem('studio-token');await init();headers.set('Authorization',`Bearer ${token}`);r=await fetch(url,{...options,headers,signal:options.signal?AbortSignal.any([options.signal,timeoutSignal(60000)]):timeoutSignal(60000)});}
  if(!r.ok){let message;try{message=(await r.json()).error;}catch{message=r.statusText;}if(r.status===401){token=null;sessionStorage.removeItem('studio-token');}throw new Error(message||'Request failed.');}
  return r.headers.get('content-type')?.includes('application/json')?r.json():r.blob() as T;
}
export const api={
  capabilities:()=>request<Capability>('/api/capabilities'),
  files:()=>request<{files:StudioFile[]}>('/api/files').then(r=>r.files),
  upload:(files:File[],onProgress?:(n:number)=>void,signal?:AbortSignal)=>new Promise<StudioFile[]>(async(resolve,reject)=>{
    await init();const data=new FormData();files.forEach(f=>data.append('files',f));const xhr=new XMLHttpRequest();xhr.open('POST','/api/files');xhr.setRequestHeader('Authorization',`Bearer ${token}`);
    xhr.upload.onprogress=e=>{if(e.lengthComputable)onProgress?.(Math.round(e.loaded/e.total*100));};
    xhr.onload=()=>{try{const r=JSON.parse(xhr.responseText);if(xhr.status>=400)reject(new Error(r.error||'Upload failed.'));else resolve(r.files);}catch{reject(new Error('Invalid upload response.'));}};
    xhr.timeout=120000;xhr.ontimeout=()=>reject(new Error('Upload timed out. Try fewer files.'));xhr.onabort=()=>reject(new DOMException('Upload cancelled','AbortError'));xhr.onerror=()=>reject(new Error('Cannot reach the local processing API.'));signal?.addEventListener('abort',()=>xhr.abort(),{once:true});xhr.send(data);
  }),
  content:async(id:string)=>request<Blob>(`/api/files/${id}/content`),
  rename:(id:string,name:string)=>request<StudioFile>(`/api/files/${id}`,{method:'PATCH',body:JSON.stringify({name})}),
  remove:(id:string)=>request(`/api/files/${id}`,{method:'DELETE'}),
  clear:()=>request('/api/temp/clear',{method:'POST'}),
  createJob:(operation:string,fileIds:string[],options:ToolOptions={})=>request<Job>('/api/jobs',{method:'POST',body:JSON.stringify({operation,fileIds,options})}),
  searchText:(id:string,query:string)=>request<{pages:number[]}>(`/api/files/${id}/search`,{method:'POST',body:JSON.stringify({query})}),
  job:(id:string)=>request<Job>(`/api/jobs/${id}`),
  cancel:(id:string)=>request<Job>(`/api/jobs/${id}`,{method:'DELETE'}),
  zip:(fileIds:string[],paths?:Record<string,string>)=>request<Blob>('/api/zip',{method:'POST',body:JSON.stringify({fileIds,paths})}),
};
export async function pollJob(id:string,onUpdate:(j:Job)=>void,signal?:AbortSignal){
  while(!signal?.aborted){const j=await api.job(id);onUpdate(j);if(['complete','error','cancelled'].includes(j.status))return j;await new Promise(r=>setTimeout(r,650));}
  throw new DOMException('Cancelled','AbortError');
}
export function download(blob:Blob,name:string){const u=URL.createObjectURL(blob);const a=document.createElement('a');a.href=u;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),60000);}
export function formatBytes(bytes:number){if(!bytes)return '0 B';const i=Math.floor(Math.log(bytes)/Math.log(1024));return `${(bytes/1024**i).toFixed(i?1:0)} ${['B','KB','MB','GB'][i]}`;}
export function formatDate(n:number){return new Intl.DateTimeFormat(undefined,{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}).format(n);}
