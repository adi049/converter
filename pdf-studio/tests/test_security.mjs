import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {validateUpload,validateOptions,safeName} from '../server/validation.mjs';
import os from 'node:os';import path from 'node:path';
const dir=await fs.mkdtemp(path.join(os.tmpdir(),'studio-validation-'));let passed=0;
async function test(name,fn){try{await fn();passed++;console.log('✓',name);}catch(e){console.error('✗',name,e);process.exitCode=1;}}
async function fixture(name,bytes){const p=path.join(dir,'file');await fs.writeFile(p,bytes);return {path:p,originalname:name};}
await test('PDF signature accepted; spoofed PDF rejected',async()=>{await validateUpload(await fixture('real.pdf',await fs.readFile('tests/samples/report.pdf')),100e6);await assert.rejects(async()=>validateUpload(await fixture('fake.pdf','<script>alert(1)</script>'),100e6),/not a valid PDF/);});
await test('PNG signature accepted; renamed text rejected',async()=>{await validateUpload(await fixture('real.png',await fs.readFile('tests/samples/landscape.png')),100e6);await assert.rejects(async()=>validateUpload(await fixture('fake.png','hello'),100e6),/Image contents/);});
await test('Office ZIP structure and type verified',async()=>{await validateUpload(await fixture('real.docx',await fs.readFile('tests/samples/proposal.docx')),100e6);await assert.rejects(async()=>validateUpload(await fixture('fake.xlsx',await fs.readFile('tests/samples/proposal.docx')),100e6),/do not match/);});
await test('executable, NUL text and invalid JSON rejected',async()=>{await assert.rejects(async()=>validateUpload(await fixture('payload.exe','MZ'),100e6),/Unsupported/);await assert.rejects(async()=>validateUpload(await fixture('payload.txt',Buffer.from([65,0,66])),100e6),/Binary/);await assert.rejects(async()=>validateUpload(await fixture('bad.json','{'),100e6),/not valid/);});
await test('filenames cannot traverse and options reject prototype keys',async()=>{assert.equal(safeName('../../secret.pdf'),'secret.pdf');assert.throws(()=>validateOptions(JSON.parse('{"__proto__":{"polluted":true}}')),/Unsafe/);assert.throws(()=>validateOptions({language:'eng;rm'}),/language/);});
await test('TTF signature and size limit enforced',async()=>{await validateUpload(await fixture('font.ttf',Buffer.from([0,1,0,0,1])),100);await assert.rejects(async()=>validateUpload(await fixture('font.ttf',Buffer.alloc(101)),100),/size limit/);});
console.log(`${passed} upload/validation checks passed.`);await fs.rm(dir,{recursive:true,force:true});
