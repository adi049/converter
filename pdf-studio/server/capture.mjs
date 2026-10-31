import { chromium } from 'playwright-core';
import { lookup } from 'node:dns/promises';
import { isIP, BlockList } from 'node:net';
import { existsSync } from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import https from 'node:https';

export function chromiumPath() {
  return process.env.CHROMIUM_PATH || ['/usr/bin/chromium','/usr/bin/chromium-browser','/usr/bin/google-chrome'].find(existsSync);
}
const blocked4=new BlockList(),blocked6=new BlockList();
for(const [net,mask] of [['0.0.0.0',8],['10.0.0.0',8],['100.64.0.0',10],['127.0.0.0',8],['169.254.0.0',16],['172.16.0.0',12],['192.0.0.0',24],['192.0.2.0',24],['192.88.99.0',24],['192.168.0.0',16],['198.18.0.0',15],['198.51.100.0',24],['203.0.113.0',24],['224.0.0.0',4],['240.0.0.0',4]])blocked4.addSubnet(net,mask,'ipv4');
for(const [net,mask] of [['::',128],['::1',128],['::ffff:0:0',96],['64:ff9b::',96],['100::',64],['2001::',32],['2001:db8::',32],['2002::',16],['fc00::',7],['fe80::',10],['ff00::',8]])blocked6.addSubnet(net,mask,'ipv6');
function privateIP(ip){const family=isIP(ip);return !family||(family===6?blocked6:blocked4).check(ip,family===6?'ipv6':'ipv4');}
export async function checkPublicURL(value) {
  let u;try{u=new URL(value);}catch{throw new Error('Enter a complete https:// or http:// URL.');}
  if(!['http:','https:'].includes(u.protocol)||u.username||u.password)throw new Error('Only public HTTP(S) URLs without embedded credentials are allowed.');
  if(u.port&&u.port!==(u.protocol==='https:'?'443':'80'))throw new Error('Private or nonstandard network ports are blocked; use public HTTP(S) on port 80 or 443.');
  const host=u.hostname.replace(/^\[|\]$/g,'');
  if(host==='localhost'||host.endsWith('.localhost')||host.endsWith('.local')||host.endsWith('.internal'))throw new Error('Private and local network URLs are blocked.');
  const addresses=isIP(host)?[{address:host}]:await lookup(host,{all:true,verbatim:true});
  if(!addresses.length||addresses.some(a=>privateIP(a.address)))throw new Error('Private, loopback and link-local network destinations are blocked.');
  u.studioAddress=addresses[0].address;u.studioFamily=addresses[0].family;return u;
}
export async function fetchPinned(request,u,signal){
 return new Promise((resolve,reject)=>{
  const deadline=setTimeout(()=>req.destroy(new Error('Remote resource exceeded 20 seconds.')),20000);
  let settled=false;const finish=(error,value)=>{if(settled)return;settled=true;clearTimeout(deadline);error?reject(error):resolve(value);};
  const headers={...request.headers(),'accept-encoding':'identity'};delete headers.host;delete headers.connection;
  const req=(u.protocol==='https:'?https:http).request(u,{method:request.method(),headers,lookup:(_host,options,cb)=>options.all?cb(null,[{address:u.studioAddress,family:u.studioFamily}]):cb(null,u.studioAddress,u.studioFamily),signal},res=>{
   const chunks=[];let size=0;res.on('close',()=>clearTimeout(deadline));res.on('data',chunk=>{size+=chunk.length;if(size>20*1024*1024){req.destroy(new Error('Remote resource exceeds 20 MB.'));return;}chunks.push(chunk);});res.on('end',()=>finish(null,{status:res.statusCode||200,headers:res.headers,body:Buffer.concat(chunks)}));res.on('error',e=>finish(e));
  });req.setTimeout(20000,()=>req.destroy(new Error('Remote resource timed out.')));req.on('error',e=>finish(e));const body=request.postDataBuffer();if(body)req.write(body);req.end();
 });
}
const escapeHTML=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export async function capturePDF({url,html,options:o,out,signal}) {
  if(signal?.aborted)throw new Error('Processing cancelled.');
  if(url)url=await checkPublicURL(String(url));
  const executablePath=chromiumPath();if(!executablePath)throw new Error('Chromium is not installed. Set CHROMIUM_PATH or install Chromium.');
  if(o.allowRemoteAssets && !o.consent)throw new Error('Confirm external network access before loading remote assets.');
  let deadline,cancel,context;
  const browser=await chromium.launch({executablePath,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--disable-background-networking','--disable-sync','--no-first-run'],timeout:30000});
  try {
    context=await browser.newContext({javaScriptEnabled:false,serviceWorkers:'block',acceptDownloads:false,viewport:{width:1240,height:1754}});
    const page=await context.newPage();
    const abort=new AbortController();let totalBytes=0,requests=0;
    cancel=()=>{abort.abort();browser.close().catch(()=>{});};signal?.addEventListener('abort',cancel,{once:true});
    deadline=setTimeout(()=>{abort.abort(new Error('Capture exceeded its two-minute safety limit.'));browser.close().catch(()=>{});},120000);
    await context.route('**/*',async route=>{
      const req=route.request();const u=new URL(req.url());
      if(++requests>100)return route.abort('blockedbyclient');
      if(['data:','blob:','about:'].includes(u.protocol))return route.continue();
      if(!o.allowRemoteAssets)return route.abort('blockedbyclient');
      try {
        const validated=await checkPublicURL(req.url());
        // Fetch using the exact validated address; TLS SNI/Host retain the original hostname.
        // This closes the validate-then-resolve DNS rebinding gap. Redirects re-enter this route.
        const response=await fetchPinned(req,validated,abort.signal);
        totalBytes+=response.body.length;if(totalBytes>80*1024*1024)return route.abort('blockedbyclient');
        const headers={...response.headers};delete headers['transfer-encoding'];delete headers['content-security-policy'];delete headers['x-frame-options'];
        return route.fulfill({...response,headers});
      }catch{return route.abort('blockedbyclient');}
    });
    const sizes={a4:'A4',a3:'A3',letter:'Letter',legal:'Legal',a5:'A5'};
    const margin=Number(o.margin??36);if(margin<0||margin>144)throw new Error('Margins must be between 0 and 144 points.');
    const dims=o.pageSize==='custom'?{width:`${Number(o.width)||210}mm`,height:`${Number(o.height)||297}mm`}:{format:sizes[o.pageSize]||'A4'};
    if(url){await page.goto(url.href,{waitUntil:'networkidle',timeout:45000});}
    else {
      await page.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>*{box-sizing:border-box}body{font-family:Arial,'Noto Sans','Noto Sans Devanagari',sans-serif;color:#242331;font-size:12pt;line-height:1.6;margin:0}img{max-width:100%;height:auto}table{border-collapse:collapse;width:100%}td,th{border:1px solid #cbd0d9;padding:8px}th{background:#f1eef8}h1,h2,h3{line-height:1.25}blockquote{border-left:3px solid #7856d8;margin-left:0;padding-left:20px;color:#666}pre{white-space:pre-wrap;background:#f4f4f6;padding:16px}a{color:#6842c2}${String(o.textCss||'').replace(/<\//g,'<\\/')}</style></head><body>${html||''}</body></html>`,{waitUntil:'networkidle',timeout:30000});
    }
    await page.emulateMedia({media:'print'});
    const header=escapeHTML(o.header||'');const footer=escapeHTML(o.footer||'');const show=!!(header||footer||o.pageNumbers);
    await page.pdf({path:out,...dims,landscape:o.orientation==='landscape',printBackground:true,preferCSSPageSize:false,displayHeaderFooter:show,
      headerTemplate:`<div style="font-size:9px;width:100%;padding:0 ${margin+12}px;color:#666;font-family:Arial">${header}</div>`,
      footerTemplate:`<div style="font-size:9px;width:100%;padding:0 ${margin+12}px;color:#666;font-family:Arial;display:flex;justify-content:space-between"><span>${footer}</span><span>${o.pageNumbers?'<span class="pageNumber"></span> / <span class="totalPages"></span>':''}</span></div>`,
      margin:{top:`${Math.max(margin,show?42:0)}px`,bottom:`${Math.max(margin,show?42:0)}px`,left:`${margin}px`,right:`${margin}px`},timeout:60000});
    clearTimeout(deadline);signal?.removeEventListener('abort',cancel);
    if(signal?.aborted)throw new Error('Processing cancelled.');
    await context.close();
  }finally{if(deadline)clearTimeout(deadline);if(cancel)signal?.removeEventListener('abort',cancel);await context?.close().catch(()=>{});await browser.close().catch(()=>{});}
  return path.basename(out);
}
