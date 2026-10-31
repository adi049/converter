import fs from 'node:fs/promises';
import path from 'node:path';
import JSZip from 'jszip';
const exts=new Set(['.pdf','.doc','.docx','.ppt','.pptx','.xls','.xlsx','.csv','.tsv','.txt','.md','.markdown','.rtf','.html','.htm','.jpg','.jpeg','.png','.webp','.bmp','.tif','.tiff','.json','.p12','.pfx','.odt','.ods','.odp','.ttf','.otf']);
const office={'.docx':'word/','.pptx':'ppt/','.xlsx':'xl/','.odt':'opendocument.text','.ods':'opendocument.spreadsheet','.odp':'opendocument.presentation'};
export function safeName(value){return path.basename(String(value||'document')).replace(/[\\/\x00-\x1f]/g,'_').replace(/^\.+/,'').slice(0,180)||'document';}
export function checkExtension(name){const ext=path.extname(String(name)).toLowerCase();if(!exts.has(ext))throw new Error('Unsupported file type: '+ext);return ext;}
export async function validateUpload(file,maxBytes){
 const ext=checkExtension(file.originalname);const stat=await fs.stat(file.path);if(!stat.size)throw new Error('Empty files are not accepted.');if(stat.size>maxBytes)throw new Error('File exceeds the configured size limit.');
 const handle=await fs.open(file.path,'r');const head=Buffer.alloc(Math.min(4096,stat.size));try{await handle.read(head,0,head.length,0);}finally{await handle.close();}
 const start=(s)=>head.subarray(0,s.length).equals(Buffer.from(s,'latin1'));
 if(ext==='.pdf'&&!start('%PDF-'))throw new Error('This file is not a valid PDF. Its extension does not match its contents.');
 if(['.png','.jpg','.jpeg','.webp','.bmp','.tif','.tiff'].includes(ext)){
   const ok=ext==='.png'?start('\x89PNG\r\n\x1a\n'):/\.jpe?g$/.test(ext)?start('\xff\xd8\xff'):ext==='.webp'?head.subarray(0,4).toString()==='RIFF'&&head.subarray(8,12).toString()==='WEBP':ext==='.bmp'?start('BM'):/\.tiff?$/.test(ext)?start('II*\0')||start('MM\0*'):false;
   if(!ok)throw new Error('Image contents do not match the filename extension.');return {ext,mime:ext==='.png'?'image/png':/\.jpe?g$/.test(ext)?'image/jpeg':ext==='.webp'?'image/webp':ext==='.bmp'?'image/bmp':'image/tiff'};
 }
 if(office[ext]||['.doc','.ppt','.xls'].includes(ext)){
   if(start('PK\x03\x04')){
     if(!office[ext])throw new Error('Legacy Office extension contains a ZIP document. Use the matching modern extension.');
     const zip=await JSZip.loadAsync(await fs.readFile(file.path),{checkCRC32:false});const entries=Object.values(zip.files);if(entries.length>10000)throw new Error('Office archive contains too many entries.');let total=0;
     for(const e of entries){const size=Number(e._data?.uncompressedSize||0);total+=size;if(total>512*1024*1024||size>256*1024*1024)throw new Error('Office archive expands beyond safe processing limits.');if(e.name.includes('..')||e.name.startsWith('/'))throw new Error('Office archive contains unsafe paths.');}
     if(!zip.file('[Content_Types].xml')&&!zip.file('mimetype'))throw new Error('Office document structure is invalid.');
     const ct=zip.file('[Content_Types].xml');const text=ct?await ct.async('string'):(await zip.file('mimetype')?.async('string'))||'';
     if(!text.includes(office[ext]))throw new Error('Office document contents do not match its extension.');
     if(/TargetMode\s*=\s*["']External/i.test((await zip.file('_rels/.rels')?.async('string'))||''))throw new Error('External package relationships are blocked. Remove linked remote resources before uploading.');
   }else if(start('\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1')){if(!['.doc','.ppt','.xls'].includes(ext))throw new Error('Legacy Office contents require a .doc, .ppt or .xls extension.');}
   else throw new Error('Office document signature is invalid.');
   return {ext,mime:'application/octet-stream'};
 }
 if(['.ttf','.otf'].includes(ext)){if(!(start('\0\x01\0\0')||start('OTTO')||start('true')||start('typ1')))throw new Error('Upload a valid TTF or OTF font.');return {ext,mime:ext==='.ttf'?'font/ttf':'font/otf'};}
 if(['.p12','.pfx'].includes(ext)){if(head[0]!==0x30)throw new Error('Signing certificate must be a binary PKCS#12 file.');return {ext,mime:'application/pkcs12'};}
 if(ext==='.rtf'&&!start('{\\rtf'))throw new Error('RTF contents are invalid.');
 if(['.csv','.tsv','.txt','.md','.markdown','.html','.htm','.json'].includes(ext)){
   if(head.includes(0))throw new Error('Binary content cannot be uploaded as text.');let text;try{text=new TextDecoder('utf-8',{fatal:true}).decode(head);}catch{throw new Error('Text documents must use UTF-8 encoding.');}
   if(ext==='.json'){try{JSON.parse(await fs.readFile(file.path,'utf8'));}catch{throw new Error('JSON document is not valid.');}}
   return {ext,mime:ext==='.json'?'application/json':ext==='.html'||ext==='.htm'?'text/plain':'text/plain'};
 }
 return {ext,mime:ext==='.pdf'?'application/pdf':'application/octet-stream'};
}
export function validateOptions(o){
 if(!o||typeof o!=='object'||Array.isArray(o))throw new Error('Options must be an object.');
 if(JSON.stringify(o).length>10*1024*1024)throw new Error('Options exceed the 10 MB request limit.');
 let nodes=0;const walk=(v,depth)=>{if(++nodes>30000||depth>14)throw new Error('Options are too deeply nested.');if(v&&typeof v==='object')for(const [k,x] of Object.entries(v)){if(['__proto__','prototype','constructor'].includes(k))throw new Error('Unsafe option key.');walk(x,depth+1);}};walk(o,0);
 for(const k of ['pageSize','orientation','language'])if(o[k]!==undefined&&typeof o[k]!=='string')throw new Error('Invalid '+k+'.');
 if(o.pageSize&&!['a4','a3','a5','letter','legal','custom'].includes(o.pageSize))throw new Error('Unsupported page size.');
 if(o.orientation&&!['portrait','landscape'].includes(o.orientation))throw new Error('Unsupported orientation.');
 if(o.language&&!/^[a-z]{3,4}(\+[a-z]{3,4}){0,5}$/.test(o.language))throw new Error('Use installed OCR language codes such as eng or eng+hin.');
 if(o.url&&String(o.url).length>4096)throw new Error('URL is too long.');
 if(o.annotations&&(!Array.isArray(o.annotations)||o.annotations.length>2000))throw new Error('Use up to 2,000 marks per export.');
 return o;
}
