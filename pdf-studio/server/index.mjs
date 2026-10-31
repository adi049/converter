import express from 'express';
import multer from 'multer';
import { ZipArchive } from 'archiver';
import { PDFDocument } from 'pdf-lib';
import { randomUUID, randomBytes } from 'node:crypto';
import { spawn, execFile } from 'node:child_process';
import { promisify } from 'node:util';
import fs from 'node:fs/promises';
import { createReadStream, existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { capturePDF, chromiumPath, checkPublicURL } from './capture.mjs';
import { marked } from 'marked';
import dotenv from 'dotenv';
import {validateUpload,validateOptions,checkExtension,safeName} from './validation.mjs';
dotenv.config({path:path.join(path.dirname(fileURLToPath(import.meta.url)),'..','.env'),quiet:true});

const exec=promisify(execFile);
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const TEMP=path.resolve(process.env.TEMP_DIR||path.join(ROOT,'.studio-temp'));
const PORT=Number(process.env.API_PORT||3001),HOST=process.env.HOST||'127.0.0.1';
const MAX_FILE=Number(process.env.MAX_FILE_MB||100)*1024*1024;
const MAX_SESSION=Number(process.env.MAX_SESSION_MB||1024)*1024*1024;
const TTL=Number(process.env.TEMP_TTL_MINUTES||120)*60000;
const MAX_JOBS=Math.max(1,Math.min(4,Number(process.env.MAX_CONCURRENT_JOBS)||2));
const MAX_SESSIONS=20,MAX_TOTAL=2*1024*1024*1024;let reservedBytes=0;
for(const value of [MAX_FILE,MAX_SESSION,TTL])if(!Number.isFinite(value)||value<=0)throw new Error('Storage and TTL environment limits must be positive.');
const PYTHON=process.env.PYTHON_PATH||'python';
await fs.mkdir(TEMP,{recursive:true,mode:0o700});await fs.chmod(TEMP,0o700);process.umask(0o077);
// Only this application's temporary namespace is ever removed.
for(const entry of await fs.readdir(TEMP,{withFileTypes:true})){
  if(entry.isDirectory()&&/^[a-f0-9-]{36}$/.test(entry.name))await fs.rm(path.join(TEMP,entry.name),{recursive:true,force:true});
}
const sessions=new Map(),queue=[];let active=0;const officeJobs=new Set(),captureJobs=new Set();
const app=express();app.disable('x-powered-by');
app.use((_req,res,next)=>{res.set({'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','Permissions-Policy':'camera=(), microphone=(), geolocation=()','Cross-Origin-Resource-Policy':'same-origin'});next();});
app.use(express.json({limit:'12mb'}));
app.use('/api',(req,res,next)=>{
  if(['127.0.0.1','localhost','::1'].includes(HOST)&&!['localhost','127.0.0.1','[::1]'].includes(req.hostname))return res.status(403).json({error:'Use the local application hostname to access this private API.'});
  res.set('Cache-Control','no-store');res.set('X-Content-Type-Options','nosniff');
  if(req.get('sec-fetch-site')==='cross-site')return res.status(403).json({error:'Cross-site API requests are not allowed.'});
  const origin=req.get('origin');
  if(origin){try{if(new URL(origin).host!==req.get('host')&&!(process.env.TRUSTED_PREVIEW_ORIGIN&&origin===process.env.TRUSTED_PREVIEW_ORIGIN))return res.status(403).json({error:'Origin mismatch.'});}catch{return res.status(403).json({error:'Invalid origin.'});}}
  next();
});
function session(req,res,next){
  const token=String(req.get('authorization')||'').replace(/^Bearer /,'');
  const s=sessions.get(token);
  if(!s||s.expires<Date.now())return res.status(401).json({error:'Local session expired. Reload the application and add your files again.'});
  s.expires=Date.now()+TTL;req.studio=s;req.token=token;next();
}
app.get('/api/health',(_req,res)=>res.json({ok:true,local:true}));
app.post('/api/session',(_req,res)=>{
  for(const [t,s] of sessions)if(s.expires<Date.now())sessions.delete(t);
  if(sessions.size>=MAX_SESSIONS)return res.status(429).json({error:'Too many local sessions. Close unused tabs or wait for temporary sessions to expire.'});
  const token=randomBytes(32).toString('hex'),id=randomUUID();
  const s={id,files:new Map(),jobs:new Map(),bytes:0,expires:Date.now()+TTL,dir:path.join(TEMP,id)};
  sessions.set(token,s);
  fs.mkdir(s.dir,{recursive:true,mode:0o700}).then(()=>res.json({token,expires:s.expires,tempTTLMinutes:TTL/60000})).catch(()=>res.status(500).json({error:'Cannot create a temporary workspace.'}));
});
app.delete('/api/session',session,async(req,res)=>{
  const s=req.studio;for(const j of s.jobs.values()){if(j.status==='queued'){j.status='cancelled';j.finished=Date.now();reservedBytes=Math.max(0,reservedBytes-(j.reserved||0));j.reserved=0;}j.cancel?.();j.kill?.();}
  if([...s.jobs.values()].some(j=>j.status==='running'))return res.status(409).json({error:'A local process is stopping. Try closing the workspace again in a moment.'});
  await fs.rm(s.dir,{recursive:true,force:true});sessions.delete(req.token);res.json({ok:true});
});
app.get('/api/capabilities',async(_req,res)=>{
  const engines={};
  for(const [name,cmd,args] of [['libreoffice','libreoffice',['--version']],['tesseract','tesseract',['--version']],['qpdf','qpdf',['--version']],['ghostscript','gs',['--version']]]){
    try{const {stdout}=await exec(cmd,args,{timeout:8000});engines[name]={available:true,version:stdout.trim().split('\n')[0]};}catch{engines[name]={available:false};}
  }
  engines.chromium={available:!!chromiumPath(),version:'Local Chromium'};
  try{const {stdout}=await exec(PYTHON,['-c','import pymupdf,pyhanko,docx,pptx,openpyxl;print(pymupdf.__version__)'],{timeout:8000});engines.pymupdf={available:true,version:stdout.trim()};}catch{engines.pymupdf={available:false};}
  let languages=[];try{const {stdout}=await exec('tesseract',['--list-langs'],{timeout:8000});languages=stdout.split('\n').slice(1).map(x=>x.trim()).filter(x=>x&&x!=='osd');}catch{}
  res.json({engines,languages,limits:{fileMB:MAX_FILE/1024/1024,sessionMB:MAX_SESSION/1024/1024,concurrentJobs:MAX_JOBS,tempTTLMinutes:TTL/60000},version:'2.0.0'});
});
async function register(s,original,name,size,extra={}){
  if(extra.kind==='output'&&s.bytes+size>MAX_SESSION)throw new Error('Output exceeds the temporary workspace limit. Clear temporary files or process fewer pages.');
  const id=randomUUID();const clean={...extra};delete clean.path;delete clean.originalPath;delete clean.session;const f={id,name:safeName(name),originalPath:original,size,created:Date.now(),modified:Date.now(),session:s.id,...clean};
  s.files.set(id,f);s.bytes+=size;return publicFile(f);
}
function publicFile(f){const {originalPath,session,...rest}=f;return rest;}
const upload=multer({storage:multer.diskStorage({destination:(req,_file,cb)=>cb(null,req.studio.dir),filename:(_req,_file,cb)=>cb(null,randomUUID()+'.upload')}),limits:{fileSize:MAX_FILE,files:50,fieldSize:16000},fileFilter:(_req,file,cb)=>{try{checkExtension(file.originalname);cb(null,true);}catch(e){cb(e);}}});
app.post('/api/files',session,(req,res,next)=>{
  if(req.studio.bytes>=MAX_SESSION||Number(req.get('content-length')||0)>MAX_SESSION-req.studio.bytes)return res.status(413).json({error:'Temporary workspace is full. Download your work and clear temporary files.'});
  upload.array('files',50)(req,res,async err=>{
    const incoming=Array.isArray(req.files)?req.files:[];
    if(err){await Promise.all(incoming.map(f=>fs.rm(f.path,{force:true})));return res.status(400).json({error:safeError(err)});}
    const result=[];let addedBytes=0;
    try{
      for(const file of incoming){
        if(req.studio.bytes+file.size>MAX_SESSION)throw new Error('Upload exceeds the temporary workspace limit. Process fewer files.');
        const meta=await validateUpload(file,MAX_FILE);let pages=null,encrypted=false;
        if(meta.ext==='.pdf'){
          try{const doc=await PDFDocument.load(await fs.readFile(file.path),{ignoreEncryption:true,updateMetadata:false});pages=doc.getPageCount();encrypted=doc.isEncrypted;}
          catch{const head=(await fs.readFile(file.path)).subarray(0,2048).toString('latin1');encrypted=/\/Encrypt\s/.test(head);if(!encrypted&&pages===null){/* PDF-lib rejects some valid damaged PDFs; MuPDF validates at processing time. */}}
        }
        await fs.chmod(file.path,0o600);result.push(await register(req.studio,file.path,file.originalname,file.size,{...meta,pages,encrypted,kind:'upload'}));addedBytes+=file.size;if([...sessions.values()].reduce((n,x)=>n+x.bytes,0)>MAX_TOTAL)throw new Error('Server temporary storage limit reached. Try again later.');
      }
      if(!result.length)return res.status(400).json({error:'No files were supplied.'});res.json({files:result});
    }catch(e){await Promise.all(incoming.map(f=>fs.rm(f.path,{force:true})));for(const f of result){req.studio.files.delete(f.id);req.studio.bytes=Math.max(0,req.studio.bytes-f.size);}res.status(400).json({error:safeError(e)});}
  });
});
app.get('/api/files',session,(req,res)=>res.json({files:[...req.studio.files.values()].map(publicFile)}));
app.get('/api/files/:id/content',session,(req,res)=>{
  const f=req.studio.files.get(req.params.id);if(!f)return res.status(404).json({error:'File no longer exists. It may have expired.'});
  const ext=path.extname(f.name).toLowerCase();
  const mimes={'.pdf':'application/pdf','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp','.txt':'text/plain; charset=utf-8','.md':'text/plain; charset=utf-8','.html':'text/plain; charset=utf-8','.json':'application/json; charset=utf-8','.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','.xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','.pptx':'application/vnd.openxmlformats-officedocument.presentationml.presentation'};
  res.set('Content-Type',mimes[ext]||'application/octet-stream');
  res.set('Content-Disposition',`${req.query.download?'attachment':'inline'}; filename*=UTF-8''${encodeURIComponent(f.name)}`);
  res.set('Content-Security-Policy',"default-src 'none'; sandbox");
  createReadStream(f.originalPath).on('error',()=>res.sendStatus(404)).pipe(res);
});
app.patch('/api/files/:id',session,(req,res)=>{const f=req.studio.files.get(req.params.id);if(!f)return res.sendStatus(404);if(typeof req.body.name==='string'&&req.body.name.trim()){const next=safeName(req.body.name);checkExtension(next);if(path.extname(next).toLowerCase()!==path.extname(f.name).toLowerCase())return res.status(400).json({error:'Renaming cannot change the file type.'});f.name=next;f.modified=Date.now();}res.json(publicFile(f));});
app.delete('/api/files/:id',session,async(req,res)=>{
  const s=req.studio,f=s.files.get(req.params.id);if(!f)return res.sendStatus(404);
  if([...s.jobs.values()].some(j=>['queued','running'].includes(j.status)&&(j.fileIds.includes(f.id)||j.results.some(r=>r.id===f.id))))return res.status(409).json({error:'This file belongs to an active job.'});
  await fs.rm(f.originalPath,{force:true});s.files.delete(f.id);s.bytes=Math.max(0,s.bytes-f.size);res.json({ok:true});
});
app.post('/api/temp/clear',session,async(req,res)=>{
  const s=req.studio;if([...s.jobs.values()].some(j=>['queued','running'].includes(j.status)))return res.status(409).json({error:'Wait for active jobs or cancel them before clearing temporary files.'});
  await fs.rm(s.dir,{recursive:true,force:true});await fs.mkdir(s.dir,{recursive:true,mode:0o700});s.files.clear();s.jobs.clear();s.bytes=0;res.json({ok:true});
});
const operations=new Set(['create-text','create-blank','create-markdown-text','markdown-docx','page-plan','create-html-rendered','create-url','images-pdf','office-pdf','pdf-jpg','pdf-png','pdf-images','pdf-text','pdf-html','pdf-markdown','pdf-docx','pdf-xlsx','pdf-pptx','watermark','merge','split','extract-pages','delete-pages','reverse','duplicate-pages','rotate-pages','reorder-pages','insert-blank','replace-pages','crop-pages','resize-pages','extract-images','annotate','redact','find-replace','page-numbers','bates','headers-footers','compress','protect','encrypt','unlock','decrypt','sign','verify-signatures','pdfa','ocr-text','ocr-docx','ocr-pdf','ocr-tables','compare','metadata','edit-metadata','bookmarks','generate-toc','csv-xlsx','flatten']);
app.post('/api/jobs',session,(req,res)=>{
  const {operation,fileIds=[],options={}}=req.body;
  if(!operations.has(operation))return res.status(400).json({error:'Unknown operation.'});
  try{validateOptions(options);}catch(e){return res.status(400).json({error:safeError(e)});}
  if(queue.length>=100)return res.status(429).json({error:'Processing queue is full. Wait for active jobs or cancel queued work.'});
  if(reservedBytes+req.studio.bytes>MAX_TOTAL)return res.status(429).json({error:'Server temporary storage is busy. Try again after active jobs finish.'});
  if(!Array.isArray(fileIds)||!options||typeof options!=='object')return res.status(400).json({error:'Invalid job inputs.'});
  if(fileIds.length>100)return res.status(400).json({error:'A job supports up to 100 input files.'});
  const files=fileIds.map(id=>req.studio.files.get(id));if(files.some(f=>!f))return res.status(404).json({error:'An input file has expired. Add it again.'});
  if(req.studio.jobs.size>=500)return res.status(429).json({error:'This session has reached its job limit. Clear temporary files to start fresh.'});
  const id=randomUUID(),dir=path.join(req.studio.dir,id);
  const job={id,operation,fileIds,status:'queued',message:'Waiting for a local worker',percent:null,created:Date.now(),results:[],notes:[],dir};
  req.studio.jobs.set(id,job);job.reserved=req.studio.bytes;reservedBytes+=job.reserved;queue.push({job,s:req.studio,options,files});res.status(202).json(publicJob(job));drain();
});
function publicJob(j){const {dir,s,options,...rest}=j;return rest;}
app.get('/api/jobs/:id',session,(req,res)=>{const j=req.studio.jobs.get(req.params.id);if(!j)return res.sendStatus(404);res.json(publicJob(j));});
app.delete('/api/jobs/:id',session,(req,res)=>{
  const j=req.studio.jobs.get(req.params.id);if(!j)return res.sendStatus(404);
  if(j.status==='queued'){j.status='cancelled';j.message='Cancelled';j.finished=Date.now();reservedBytes=Math.max(0,reservedBytes-(j.reserved||0));j.reserved=0;}else if(j.status==='running'){j.cancel?.();j.status='cancelled';j.message='Cancelled by you';}
  res.json(publicJob(j));
});
app.post('/api/zip',session,(req,res)=>{
  if(!Array.isArray(req.body.fileIds)||req.body.fileIds.length>500)return res.status(400).json({error:'Select up to 500 output files.'});const files=req.body.fileIds.map(id=>req.studio.files.get(id));if(!files.length||files.some(f=>!f))return res.status(400).json({error:'Select existing output files to download.'});
  res.attachment('PDF Studio export.zip');const zip=new ZipArchive({zlib:{level:6}});zip.on('error',()=>res.destroy());zip.pipe(res);const used=new Set();
  for(const [i,f] of files.entries()){const folder=String(req.body.paths?.[f.id]||'').split('/').map(x=>x.replace(/[^\w .-]/g,'_').replace(/^\.+$/,'_').slice(0,80)).filter(Boolean).slice(0,8).join('/');let name=(folder?folder+'/':'')+f.name,n=1;while(used.has(name)){name=`${path.basename(f.name,path.extname(f.name))}-${n++}${path.extname(f.name)}`;if(folder)name=folder+'/'+name;}used.add(name);zip.file(f.originalPath,{name});}zip.finalize();
});
async function drain(){
  if(active>=MAX_JOBS)return;
  const index=queue.findIndex(x=>x.job.status==='queued'&&(!(x.job.operation==='office-pdf')||officeJobs.size===0)&&(!(['create-html-rendered','create-url','create-markdown-text'].includes(x.job.operation))||captureJobs.size===0));
  if(index<0)return;const item=queue.splice(index,1)[0];active++;run(item).finally(()=>{active--;drain();});drain();
}
function safeError(e){let message=String(e?.message||e||'Processing failed.');message=message.replace(/\/(?:home|tmp|Users|var|private)\/[^\s"'<>]+/g,'[local file]').replace(/[A-Z]:\\[^\s"'<>]+/g,'[local file]');return message.slice(0,700);}
async function run({job,s,options,files}){
  const j=job;if(j.operation==='office-pdf')officeJobs.add(j.id);if(['create-html-rendered','create-url','create-markdown-text'].includes(j.operation))captureJobs.add(j.id);
  j.status='running';j.message='Preparing local processing';j.started=Date.now();const controller=new AbortController();j.cancel=()=>controller.abort();
  try{
    await fs.mkdir(j.dir,{recursive:true,mode:0o700});
    const out=path.join(j.dir,'output');await fs.mkdir(out);
    const manifest=path.join(j.dir,'result.json'),progress=path.join(j.dir,'progress.json');
    let results=[],notes=[];
    if(['create-url','create-html-rendered','create-markdown-text'].includes(j.operation)){
      j.message=j.operation==='create-url'?'Retrieving the explicitly requested URL':'Rendering document with local Chromium';
      let html=options.html||'';
      if(j.operation==='create-markdown-text'){const md=options.text||(files[0]?await fs.readFile(files[0].originalPath,'utf8'):'');if(!md.trim())throw new Error('Add a Markdown file or enter Markdown text.');html=marked.parse(md,{async:false});options={...options,allowRemoteAssets:false,consent:false};}
      if(options.url){if(!options.consent)throw new Error('Confirm permission to retrieve this URL.');await checkPublicURL(options.url);}
      const target=path.join(out,(String(options.filename||'Document').replace(/[\\/\x00-\x1f]/g,'_').slice(0,100)||'Document')+'.pdf');
      await capturePDF({url:options.url,html,options,out:target,signal:controller.signal});
      const stat=await fs.stat(target);results=[await register(s,target,path.basename(target),stat.size,{kind:'output',ext:'.pdf'})];
      notes.push(j.operation==='create-url'?'Captured the requested public URL using local Chromium. Only that explicit capture contacted the website. Review dynamic content and page breaks.':'Printed locally with Chromium. No document was sent to a conversion service.');
    }else{
      const request={operation:j.operation,options,files:files.map(f=>({...publicFile(f),path:f.originalPath})),out,manifest,progress};
      const reqPath=path.join(j.dir,'request.json');await fs.writeFile(reqPath,JSON.stringify(request),{mode:0o600});
      const timer=setInterval(async()=>{try{const p=JSON.parse(await fs.readFile(progress,'utf8'));if(j.status==='running'){j.message=p.message||j.message;j.percent=p.percent??null;}}catch{}},500);
      const code=await new Promise((resolve,reject)=>{
        const child=spawn(PYTHON,[path.join(ROOT,'engines','dispatcher.py'),reqPath],{cwd:ROOT,stdio:['ignore','pipe','pipe'],detached:process.platform!=='win32'});j.child=child;
        const kill=()=>{try{if(process.platform==='win32')spawn('taskkill',['/pid',String(child.pid),'/T','/F']);else process.kill(-child.pid,'SIGKILL');}catch{child.kill('SIGKILL');}};j.kill=kill;controller.signal.addEventListener('abort',kill,{once:true});let stderr='';
        child.stderr.on('data',b=>{stderr=(stderr+b).slice(-3000);});
        const timeout=setTimeout(()=>{j.timedOut=true;kill();},Number(process.env.JOB_TIMEOUT_MINUTES||10)*60000);
        child.on('error',e=>{clearTimeout(timeout);controller.signal.removeEventListener('abort',kill);reject(e);});child.on('close',code=>{clearTimeout(timeout);controller.signal.removeEventListener('abort',kill);resolve(code);});j.stderr=()=>stderr;
      });
      clearInterval(timer);await fs.rm(reqPath,{force:true});
      let result;try{result=JSON.parse(await fs.readFile(manifest,'utf8'));}catch{throw new Error(j.timedOut?'Processing exceeded the time limit. Try fewer pages or a smaller document.':(j.stderr?.()||'Processing engine stopped unexpectedly. Check Python dependencies.'));}
      if(!result.ok)throw new Error(result.error);
      const outputBytes=result.results.reduce((n,r)=>n+Number(r.size||0),0);if(s.bytes+outputBytes>MAX_SESSION)throw new Error('Outputs exceed the temporary workspace limit. Clear temporary files or process fewer pages.');
      const registered=[];try{for(const r of result.results){const filePath=path.resolve(r.path);if(!filePath.startsWith(out+path.sep))throw new Error('Invalid engine output path.');const item=await register(s,filePath,r.name,r.size,{kind:'output',ext:path.extname(r.name).toLowerCase(),...Object.fromEntries(Object.entries(r).filter(([k])=>!['path','name','size'].includes(k)))});results.push(item);registered.push(item);}}catch(e){for(const f of registered){s.files.delete(f.id);s.bytes=Math.max(0,s.bytes-f.size);await fs.rm(f.originalPath,{force:true});}throw e;}
      notes=result.notes||[];
    }
    if(j.status==='cancelled'){for(const f of results){await fs.rm(f.originalPath,{force:true});s.files.delete(f.id);s.bytes=Math.max(0,s.bytes-f.size);}await fs.rm(j.dir,{recursive:true,force:true});return;}j.status='complete';j.message='Ready to download';j.percent=100;j.results=results;j.notes=notes;
  }catch(e){if(j.status!=='cancelled'){j.status='error';j.message='Processing failed';j.error=controller.signal.aborted?'Processing cancelled.':safeError(e);}}
  finally{reservedBytes=Math.max(0,reservedBytes-(j.reserved||0));j.reserved=0;
    if(j.status==='error')await fs.rm(j.dir,{recursive:true,force:true}).catch(()=>{});j.finished=Date.now();delete j.kill;delete j.child;delete j.cancel;delete j.stderr;officeJobs.delete(j.id);captureJobs.delete(j.id);}
}
app.use('/api',(_req,res)=>res.status(404).json({error:'API endpoint not found.'}));
const dist=path.join(ROOT,'dist');
if(existsSync(dist)){app.use((_req,res,next)=>{res.set('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; worker-src 'self' blob:; connect-src 'self'; frame-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'self'");
  // Explicit opt-in for a trusted sandbox's cross-origin preview iframe.
  // Normal local/production launches retain the original framing protection.
  if(process.env.PREVIEW_EMBED==='true')res.set('Cross-Origin-Resource-Policy','cross-origin');
  else res.set('X-Frame-Options','SAMEORIGIN');
  next();});app.use(express.static(dist,{maxAge:'1h',index:false}));app.get('*',(_req,res)=>{res.set('Cache-Control','no-cache');res.sendFile(path.join(dist,'index.html'));});}
app.use((err,_req,res,_next)=>res.status(err.status===413?413:400).json({error:err.type==='entity.too.large'?'Request exceeds the size limit.':safeError(err)}));
const cleanup=setInterval(async()=>{
  for(const [token,s] of sessions){if(s.expires>Date.now())continue;const activeJobs=[...s.jobs.values()].filter(j=>['queued','running'].includes(j.status));for(const j of activeJobs){if(j.status==='queued'){j.status='cancelled';j.finished=Date.now();reservedBytes=Math.max(0,reservedBytes-(j.reserved||0));j.reserved=0;}j.cancel?.();j.kill?.();}if(activeJobs.some(j=>j.status==='running'))continue;await fs.rm(s.dir,{recursive:true,force:true});sessions.delete(token);}
},60000);cleanup.unref();
const server=app.listen(PORT,HOST,()=>console.log(`PDF Studio local API listening on ${HOST}:${PORT}. Temporary files expire after ${TTL/60000} minutes.`));
server.on('error',e=>{console.error(e.message);process.exit(1);});
let stopping=false;
async function shutdown(){if(stopping)return;stopping=true;clearInterval(cleanup);for(const s of sessions.values())for(const j of s.jobs.values()){if(j.status==='queued'){j.status='cancelled';j.finished=Date.now();reservedBytes=Math.max(0,reservedBytes-(j.reserved||0));j.reserved=0;}j.cancel?.();j.kill?.();}server.close();await new Promise(r=>setTimeout(r,700));await Promise.all([...sessions.values()].map(s=>fs.rm(s.dir,{recursive:true,force:true})));process.exit(0);}
process.on('SIGTERM',shutdown);process.on('SIGINT',shutdown);
// Complex-script text extraction uses MuPDF's Unicode mappings; PDF.js can split or mis-map conjuncts.
app.post('/api/files/:id/search',session,async(req,res)=>{
 const f=req.studio.files.get(req.params.id);if(!f||f.ext!=='.pdf')return res.status(404).json({error:'PDF no longer exists.'});
 const q=String(req.body.query||'').slice(0,500);if(!q.trim())return res.json({pages:[]});
 try{const {stdout}=await exec(PYTHON,['-c','import sys,pymupdf,json\nwith pymupdf.open(sys.argv[1]) as d:\n print(json.dumps({"pages":[i+1 for i,p in enumerate(d) if i<500 and p.search_for(sys.argv[2])]}))',f.originalPath,q],{timeout:30000,maxBuffer:1024*1024});res.json(JSON.parse(stdout));}catch{res.status(422).json({error:'Text search requires an unlocked, readable PDF. Unlock it first if protected.'});}
});
