import {library,getMeta,setMeta} from './store';
import type {LibraryItem,Folder} from './types';
export async function exportLibrary(){
 const {default:JSZip}=await import('jszip');const zip=new JSZip();const files=await library.all();const folders=await getMeta<Folder[]>('folders',[]);
 const manifest={format:'pdf-studio-library',version:2,exported:new Date().toISOString(),folders,files:files.map(({blob,...f})=>({...f,archivePath:'documents/'+f.id}))};
 zip.file('manifest.json',JSON.stringify(manifest,null,2));for(const f of files)zip.file('documents/'+f.id,f.blob);
 zip.file('README.txt','PDF Studio library backup. Restore using Document library → Restore backup. Contains unencrypted document contents. Keep private.');
 return zip.generateAsync({type:'blob',compression:'DEFLATE',compressionOptions:{level:6}});
}
export async function inspectBackup(blob:Blob){
 if(blob.size>512*1024*1024)throw new Error('Backup exceeds the 512 MB restore safety limit.');
 const {default:JSZip}=await import('jszip');const zip=await JSZip.loadAsync(blob);const entry=zip.file('manifest.json');if(!entry)throw new Error('Not a PDF Studio library backup: manifest.json is missing.');
 const text=await entry.async('string');if(text.length>8*1024*1024)throw new Error('Backup manifest is too large.');const m=JSON.parse(text);
 if(m.format!=='pdf-studio-library'||m.version!==2||!Array.isArray(m.files)||m.files.length>2000||!Array.isArray(m.folders))throw new Error('Unsupported or invalid backup format.');
 let total=0;for(const f of m.files){const e=zip.file('documents/'+f.id);if(!e||typeof f.id!=='string'||!/^[a-zA-Z0-9-]{1,80}$/.test(f.id)||typeof f.name!=='string'||f.name.length>250)throw new Error('Backup contains an invalid document entry.');const size=(e as any)._data?.uncompressedSize||0;total+=size;if(total>512*1024*1024)throw new Error('Expanded backup exceeds the 512 MB safety limit.');}
 return {manifest:m,zip,total};
}
export async function restoreBackup(blob:Blob){
 const {manifest:m,zip}=await inspectBackup(blob);const existing=await library.all();const items:LibraryItem[]=[];
 for(const f of m.files){const data=await zip.file('documents/'+f.id)!.async('blob');const {archivePath,...rest}=f;items.push({...rest,id:crypto.randomUUID(),name:f.name.replace(/[\\/\x00-\x1f]/g,'_').slice(0,200),blob:new Blob([data],{type:typeof f.type==='string'?f.type:'application/octet-stream'}),folder:typeof f.folder==='string'?f.folder:'',favorite:!!f.favorite,created:Number(f.created)||Date.now(),modified:Number(f.modified)||Date.now(),opened:Number(f.opened)||Date.now()});}
 const folders=await getMeta<Folder[]>('folders',[]);const additions:Folder[]=m.folders.filter((f:Folder)=>typeof f.id==='string'&&typeof f.name==='string'&&!folders.some(x=>x.id===f.id)).map((f:Folder)=>({id:f.id,name:f.name.slice(0,100)}));
 // Stage all reads before writing; existing documents are never overwritten.
 for(const item of items)await library.save(item);await setMeta('folders',[...folders,...additions]);return {documents:items.length,existing:existing.length};
}
