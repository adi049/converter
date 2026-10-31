import { openDB } from 'idb';
import type { LibraryItem, Settings, HistoryItem, Preset, Folder } from './types';
const db=()=>openDB('pdf-studio-private',1,{upgrade(d){const files=d.createObjectStore('files',{keyPath:'id'});files.createIndex('folder','folder');d.createObjectStore('meta');}});
export const library={
  async all():Promise<LibraryItem[]>{return (await db()).getAll('files');},
  async save(item:LibraryItem){await (await db()).put('files',item);},
  async update(id:string,patch:Partial<LibraryItem>){const d=await db();const item=await d.get('files',id);if(item)await d.put('files',{...item,...patch,modified:Date.now()});},
  async remove(id:string){await (await db()).delete('files',id);},
  async clear(){await (await db()).clear('files');},
};
export async function getMeta<T>(key:string,fallback:T):Promise<T>{return await (await db()).get('meta',key)??fallback;}
export async function setMeta(key:string,value:unknown){await (await db()).put('meta',value,key);}
export const defaultSettings:Settings={theme:'studio',history:true,defaultDpi:150,defaultQuality:85,ocrLanguage:'eng',reduceMotion:false};
export const defaultWatermark={enabled:true,type:'text' as const,text:'CONFIDENTIAL',font:'Helvetica',fontSize:48,color:'#7C3AED',opacity:.18,rotation:45,position:'diagonal',x:50,y:50,tile:false,gap:100,imageWidth:220,align:'center',valign:'middle',margin:24,layer:'over' as const,unit:'percent' as const};
export function readLocal<T>(key:string,fallback:T):T{try{return JSON.parse(localStorage.getItem('studio-'+key)||'null')??fallback;}catch{return fallback;}}
export function writeLocal(key:string,value:unknown){try{localStorage.setItem('studio-'+key,JSON.stringify(value));}catch{}}
export function parsePages(input:string,count:number):number[]{
  if(!input.trim()||input==='all')return Array.from({length:count},(_,i)=>i+1);
  const result:number[]=[];
  for(const part of input.split(',')){
    const s=part.trim();if(s==='odd'||s==='even'){for(let i=1;i<=count;i++)if(i%2===(s==='odd'?1:0))result.push(i);continue;}
    const m=s.match(/^(\d+)(?:\s*-\s*(\d+))?$/);if(!m)throw new Error(`Invalid page range “${s}”. Try 1-3, 5, 8.`);
    const a=Number(m[1]),b=Number(m[2]||a);if(a<1||b<a||b>count)throw new Error(`Pages ${s} are outside this document.`);for(let i=a;i<=b;i++)result.push(i);
  }
  if(new Set(result).size!==result.length)throw new Error('Select each page only once.');return result;
}
