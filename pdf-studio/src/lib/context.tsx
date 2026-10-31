import React,{createContext,useContext,useEffect,useState,useCallback} from 'react';
import type {StudioFile,Job,Page,Settings,HistoryItem,LibraryItem,ToolOptions,Capability,Folder} from './types';
import {api,pollJob,download} from './api';
import {library,getMeta,setMeta,defaultSettings,readLocal,writeLocal} from './store';
import {useToast} from '../components/UI';
export type Output=StudioFile&{blob?:Blob};
interface StudioContextType {
 page:Page;toolId:string;navigate:(page:Page,tool?:string)=>void;files:StudioFile[];addFiles:(f:StudioFile[])=>void;jobs:Job[];setJobs:React.Dispatch<React.SetStateAction<Job[]>>;history:HistoryItem[];clearHistory:()=>void;remember:(item:HistoryItem)=>void;toolSeed:StudioFile[];openInTool:(id:string,files:StudioFile[])=>void;saved:LibraryItem[];refreshLibrary:()=>Promise<void>;folders:Folder[];setFolders:React.Dispatch<React.SetStateAction<Folder[]>>;settings:Settings;updateSettings:(s:Partial<Settings>)=>void;capabilities:Capability|null;refreshCapabilities:()=>Promise<void>;saveOutput:(f:Output,folder?:string)=>Promise<void>;outputBlob:(f:Output)=>Promise<Blob>;downloadOutput:(f:Output)=>Promise<void>;run:(operation:string,files:StudioFile[],options?:ToolOptions|((f:StudioFile)=>ToolOptions),label?:string,extras?:StudioFile[])=>Promise<Job[]>;searchOpen:boolean;setSearchOpen:React.Dispatch<React.SetStateAction<boolean>>;editorHtml:string;setEditorHtml:React.Dispatch<React.SetStateAction<string>>;templateName:string;setTemplateName:React.Dispatch<React.SetStateAction<string>>;busy:boolean;libraryQuery:string;setLibraryQuery:React.Dispatch<React.SetStateAction<string>>;
}
const Context=createContext<StudioContextType>(null!);export const useStudio=()=>useContext(Context);
export function StudioProvider({children}:{children:React.ReactNode}){
 const toast=useToast();const [page,setPage]=useState<Page>('dashboard'),[toolId,setToolId]=useState('merge'),[files,setFiles]=useState<StudioFile[]>([]),[jobs,setJobs]=useState<Job[]>([]),[history,setHistory]=useState<HistoryItem[]>(()=>readLocal('history',[])),[saved,setSaved]=useState<LibraryItem[]>([]),[folders,setFolders]=useState<Folder[]>([]),[settings,setSettings]=useState<Settings>(defaultSettings),[capabilities,setCapabilities]=useState<Capability|null>(null),[searchOpen,setSearchOpen]=useState(false),[editorHtml,setEditorHtml]=useState(''),[templateName,setTemplateName]=useState('Untitled document'),[busy,setBusy]=useState(false),[toolSeed,setToolSeed]=useState<StudioFile[]>([]),[libraryQuery,setLibraryQuery]=useState('');
 const navigate=useCallback((p:Page,t?:string)=>{setPage(p==='tool'&&t==='watermark'?'watermark':p);if(t)setToolId(t);if(p!=='tool')setToolSeed([]);window.scrollTo({top:0});},[]);
 const refreshLibrary=useCallback(async()=>{setSaved(await library.all());},[]);
 const refreshCapabilities=useCallback(async()=>{try{setCapabilities(await api.capabilities());}catch(e){toast((e as Error).message,'error');}},[]);
 useEffect(()=>{getMeta('settings',defaultSettings).then(setSettings);getMeta('folders',[]).then(setFolders);refreshLibrary();refreshCapabilities();api.files().then(setFiles).catch(()=>{});},[]);
 useEffect(()=>{document.documentElement.dataset.theme='studio';document.documentElement.dataset.motion=settings.reduceMotion?'reduced':'normal';},[settings.reduceMotion]);
 const updateSettings=(s:Partial<Settings>)=>setSettings(old=>{const next={...old,...s};setMeta('settings',next);return next;});
 useEffect(()=>{setMeta('folders',folders);},[folders]);
 const addFiles=(f:StudioFile[])=>setFiles(old=>[...f,...old.filter(x=>!f.some(n=>n.id===x.id))]);
 const remember=(item:HistoryItem)=>{if(!settings.history)return;setHistory(h=>{const next=[item,...h].slice(0,300);writeLocal('history',next);return next;});};
 const record=(j:Job,label:string)=>{const item:HistoryItem={id:j.id,tool:label||j.operation,filename:j.results[0]?.name||'Document',date:Date.now(),status:j.status,outputs:j.results.length,bytes:j.results.reduce((n,f)=>n+f.size,0),notes:j.notes};remember(item);};
 const openInTool=(id:string,seed:StudioFile[])=>{setToolSeed(seed);navigate('tool',id);};
 const run=async(operation:string,inputs:StudioFile[],options:ToolOptions|((f:StudioFile)=>ToolOptions)={},label='',extras:StudioFile[]=[])=>{
  setBusy(true);const created:Job[]=[];
  try{const batches=inputs.length?inputs.map(input=>[input]):[[]];for(const batch of batches){const j=await api.createJob(operation,[...batch.map(f=>f.id),...extras.map(f=>f.id)],typeof options==='function'?options(batch[0]):options);created.push(j);}setJobs(old=>[...created,...old]);
   const completed=await Promise.all(created.map(j=>pollJob(j.id,u=>setJobs(old=>old.map(x=>x.id===u.id?u:x)))));
   for(const j of completed){record(j,label);if(j.status==='complete'){addFiles(j.results);toast(`${label||'Processing'} complete · ${j.results.length} output${j.results.length===1?'':'s'}`,'success');}else if(j.status==='error')toast(j.error||'Processing failed.','error');}
   return completed;
  }finally{setBusy(false);}
 };
 const outputBlob=async(f:Output)=>f.blob||api.content(f.id);
 const downloadOutput=async(f:Output)=>{try{download(await outputBlob(f),f.name);const item:HistoryItem={id:crypto.randomUUID(),tool:'Download',filename:f.name,date:Date.now(),status:'download',outputs:1,bytes:f.size};setHistory(h=>{const next=[item,...h].slice(0,300);if(settings.history)writeLocal('history',next);return next;});}catch(e){toast((e as Error).message,'error');}};
 const saveOutput=async(f:Output,folder='')=>{try{const blob=await outputBlob(f);const item:LibraryItem={id:crypto.randomUUID(),name:f.name,size:blob.size,type:blob.type||f.ext||'application/octet-stream',created:Date.now(),modified:Date.now(),opened:Date.now(),sourceCreated:f.created,sourceModified:f.modified,folder,favorite:false,blob};await library.save(item);await refreshLibrary();toast('Saved to your local library. Nothing was uploaded.','success');}catch(e){toast((e as Error).message,'error');}};
 useEffect(()=>{const replace=(e:Event)=>setFiles((e as CustomEvent).detail);window.addEventListener('studio-files-replace',replace);return()=>window.removeEventListener('studio-files-replace',replace);},[]);
 const clearHistory=()=>{setHistory([]);writeLocal('history',[]);};
 return <Context.Provider value={{page,toolId,navigate,files,addFiles,jobs,setJobs,history,clearHistory,remember,toolSeed,openInTool,saved,refreshLibrary,folders,setFolders,settings,updateSettings,capabilities,refreshCapabilities,saveOutput,outputBlob,downloadOutput,run,searchOpen,setSearchOpen,editorHtml,setEditorHtml,templateName,setTemplateName,busy,libraryQuery,setLibraryQuery}}>{children}</Context.Provider>;
}

