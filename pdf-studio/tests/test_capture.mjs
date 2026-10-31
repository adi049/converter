// Transport safety tests use a local fixture server, never user documents.
import assert from 'node:assert/strict';
import http from 'node:http';
import fs from 'node:fs/promises';
import {checkPublicURL,fetchPinned,capturePDF} from '../server/capture.mjs';

for(const url of ['http://127.0.0.1','http://10.0.0.1','http://169.254.169.254','http://[::1]','http://[::ffff:127.0.0.1]','http://192.0.2.1','https://example.com:8443','file:///etc/passwd','https://user:password@example.com']){
  await assert.rejects(()=>checkPublicURL(url));
}
console.log('✓ Private, mapped-loopback, documentation, credential and nonstandard-port URLs rejected');
const server=http.createServer((req,res)=>{
  if(req.url==='/large'){res.writeHead(200,{'Content-Type':'application/octet-stream'});res.write(Buffer.alloc(21*1024*1024,65));res.end();}
  else if(req.url==='/slow'){res.writeHead(200,{'Content-Type':'text/plain'});res.write('waiting');}
  else {res.writeHead(200,{'Content-Type':'text/plain'});res.end('Local transport fixture');}
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const port=server.address().port;
const pinned=path=>{const u=new URL(`http://127.0.0.1:${port}${path}`);u.studioAddress='127.0.0.1';u.studioFamily=4;return u;};
const request=path=>({method:()=> 'GET',headers:()=>({}),postDataBuffer:()=>null,url:()=>`http://127.0.0.1:${port}${path}`});
try{
  const normal=await fetchPinned(request('/'),pinned('/'),new AbortController().signal);
  assert.equal(normal.body.toString(),'Local transport fixture');
  console.log('✓ Pinned HTTP transport returns real response bytes');
  await assert.rejects(()=>fetchPinned(request('/large'),pinned('/large'),new AbortController().signal),/20 MB/);
  console.log('✓ Resource byte limit enforced while streaming');
  const start=Date.now();
  await assert.rejects(()=>fetchPinned(request('/slow'),pinned('/slow'),new AbortController().signal),/20 seconds/);
  assert(Date.now()-start<23000);
  console.log('✓ Stalled resource reaches a real timeout');
  const controller=new AbortController();setTimeout(()=>controller.abort(),100);
  await assert.rejects(()=>fetchPinned(request('/slow'),pinned('/slow'),controller.signal));
  console.log('✓ Cancellation aborts an in-flight resource');
  if(process.argv.includes('--public')){
    await fs.mkdir('artifacts/network-tests',{recursive:true});
    for(const [name,url] of [['public','https://example.com'],['redirect','https://httpbingo.org/redirect-to?url=https%3A%2F%2Fexample.com&status_code=302']]){
      const out=`artifacts/network-tests/${name}.pdf`;
      await capturePDF({url,options:{allowRemoteAssets:true,consent:true},out});
      const bytes=await fs.readFile(out);assert.equal(bytes.subarray(0,4).toString(),'%PDF');assert(bytes.length>1000);
      console.log('✓ Public pinned-IP capture:',name,bytes.length,'bytes');
    }
  }
}finally{server.closeAllConnections();await new Promise(r=>server.close(r));}
