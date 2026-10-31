import type { ToolOptions } from '../lib/types';
let sequence=0;const worker=()=>new Worker(new URL('./image.worker.ts',import.meta.url),{type:'module'});
export function localImage(file:File,options:ToolOptions,onProgress?:(n:number)=>void):Promise<{blob:Blob;name:string;size:number}>{
 return new Promise((resolve,reject)=>{const w=worker(),id=++sequence;w.onmessage=e=>{if(e.data.id!==id)return;if(e.data.progress!==undefined){onProgress?.(e.data.progress);return;}w.terminate();e.data.error?reject(new Error(e.data.error)):resolve(e.data.result);};w.onerror=e=>{w.terminate();reject(new Error(e.message||'Browser image worker failed.'));};w.postMessage({id,operation:'image',file,options});});
}
export function localImagesPDF(files:File[],options:ToolOptions,onProgress?:(n:number)=>void):Promise<{blob:Blob;name:string;size:number}>{
 return new Promise((resolve,reject)=>{const w=worker(),id=++sequence;w.onmessage=e=>{if(e.data.id!==id)return;if(e.data.progress!==undefined){onProgress?.(e.data.progress);return;}w.terminate();e.data.error?reject(new Error(e.data.error)):resolve(e.data.result);};w.onerror=e=>{w.terminate();reject(new Error(e.message));};w.postMessage({id,operation:'images-pdf',options:{...options,files}});});
}
