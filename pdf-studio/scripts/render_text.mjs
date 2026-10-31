// Local Unicode text renderer. No HTTP server or third-party document service.
import {capturePDF} from '../server/capture.mjs';
import fs from 'node:fs';
const request=JSON.parse(fs.readFileSync(0,'utf8'));
try{await capturePDF({...request,html:request.html ?? request.options?.html ?? '',url:request.url ?? request.options?.url});process.stdout.write(JSON.stringify({ok:true}));}catch(e){process.stdout.write(JSON.stringify({ok:false,error:e.message}));process.exitCode=1;}
