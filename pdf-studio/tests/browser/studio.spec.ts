import {test,expect} from '@playwright/test';
import path from 'node:path';
const sample=(name:string)=>path.resolve('tests/samples',name);
test('dashboard, tool search, fixed theme and responsive navigation',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));await page.goto('/');await expect(page.getByRole('heading',{name:/Good work starts here./})).toBeVisible();
 await expect(page.locator('html')).toHaveAttribute('data-theme','studio');await expect(page.getByRole('button',{name:/Switch to.*mode/})).toHaveCount(0);await expect(page.getByRole('link',{name:/Managed By Luna website/})).toBeVisible();
 await page.keyboard.press('Control+k');await page.getByRole('textbox',{name:'Search all tools and documents'}).fill('watermark');await page.getByRole('button',{name:'Watermark Studio Edit & annotate'}).click();await expect(page.getByRole('heading',{name:'Watermark Studio',exact:true})).toBeVisible();
 await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'Open navigation'}).click();await page.getByRole('button',{name:'All tools',exact:false}).first().click();await expect(page.getByRole('heading',{name:'One studio. Every possibility.'})).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();expect(errors).toEqual([]);
});
test('real Word to PDF upload, processing, preview and download',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Word to PDF',exact:false}).first().click();await page.locator('.dropzone input[type=file]').first().setInputFiles(sample('proposal.docx'));await expect(page.locator('.file-chip').getByText('proposal.docx',{exact:true})).toBeVisible();await page.getByRole('button',{name:'Process',exact:true}).click();await expect(page.getByRole('heading',{name:'Your documents are ready'})).toBeVisible({timeout:45000});await expect(page.getByText('proposal.pdf',{exact:true})).toBeVisible();
 const download=page.waitForEvent('download');await page.getByRole('button',{name:'Download',exact:true}).click();expect((await download).suggestedFilename()).toBe('proposal.pdf');
 await page.getByRole('button',{name:'Preview proposal.pdf'}).click();await expect(page.locator('.modal canvas')).toBeVisible();await page.getByRole('button',{name:'Close dialog'}).click();
});
test('watermark settings apply to a real PDF and export embedded text',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Watermark Studio',exact:true}).click();await page.locator('.dropzone input[type=file]').first().setInputFiles(sample('report.pdf'));await expect(page.locator('.watermark-page-wrap canvas').first()).toBeVisible();await page.getByRole('button',{name:'MANAGED BY LUNA',exact:true}).click();await page.getByRole('button',{name:'Apply watermark',exact:true}).click();await expect(page.getByRole('heading',{name:'Your documents are ready'})).toBeVisible();await expect(page.getByText('report-watermarked.pdf',{exact:true})).toBeVisible();
 const d=page.waitForEvent('download');await page.getByRole('button',{name:'Download',exact:true}).click();const file=await d;await file.saveAs('/tmp/studio-ui-watermarked.pdf');const fs=await import('node:fs/promises');const pdfjs=await import('pdfjs-dist/legacy/build/pdf.mjs');const doc=await pdfjs.getDocument({data:new Uint8Array(await fs.readFile('/tmp/studio-ui-watermarked.pdf')),useSystemFonts:true}).promise;const p=await doc.getPage(1);expect((await p.getTextContent()).items.map((x:any)=>x.str).join(' ')).toContain('MANAGED BY LUNA');await doc.destroy();
});
test('visual page organizer duplicates, rotates and exports a real page plan',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Page Organizer',exact:true}).click();await page.locator('.dropzone input[type=file]').first().setInputFiles(sample('report.pdf'));await expect(page.locator('.page-tile')).toHaveCount(3);await page.getByRole('checkbox',{name:'Select page 1',exact:true}).check();await page.getByRole('button',{name:'Duplicate selected pages'}).click();await expect(page.locator('.page-tile')).toHaveCount(4);await page.getByRole('button',{name:'Rotate selected right'}).click();await page.getByRole('button',{name:'Apply page organization'}).click();await expect(page.getByText('report-organized.pdf',{exact:true})).toBeVisible();
});
test('image conversion runs in browser and produces a downloadable JPG',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Image Workshop',exact:true}).click();await page.locator('.dropzone input[type=file]').first().setInputFiles(sample('landscape.png'));await page.getByLabel('Output format',{exact:true}).selectOption('jpg');await page.getByRole('button',{name:'Process image',exact:true}).click();await expect(page.getByText('landscape-edited.jpg',{exact:true})).toBeVisible();const d=page.waitForEvent('download');await page.getByRole('button',{name:'Download',exact:true}).click();expect((await d).suggestedFilename()).toBe('landscape-edited.jpg');
});
test('rich text creator exports with a table and saved template',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Document creator',exact:false}).click();await page.locator('.tiptap').fill('My local document studio test.');await page.getByRole('button',{name:'Insert 3 by 3 table'}).click();await expect(page.locator('.tiptap table')).toBeVisible();await page.getByRole('button',{name:'Export PDF',exact:true}).click();await expect(page.getByRole('heading',{name:'Your documents are ready'})).toBeVisible({timeout:30000});await page.getByRole('button',{name:'Save as template'}).click();await page.getByLabel('Template name',{exact:true}).fill('Test reusable layout');await page.getByRole('button',{name:'Save template',exact:true}).click();await expect(page.getByText('Reusable layout saved locally.')).toBeVisible();
});
test('library saves explicitly, renames, favorites and survives reload',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Document library',exact:false}).click();await page.getByRole('button',{name:'Add documents',exact:true}).click();await page.locator('.modal .dropzone input[type=file]').setInputFiles(sample('report.pdf'));await expect(page.locator('.modal-backdrop')).toHaveCount(0);await expect(page.getByRole('button',{name:/report.pdf My documents/})).toBeVisible();await page.getByRole('button',{name:'Add favorite',exact:true}).click();await expect(page.getByRole('button',{name:'Remove favorite'})).toBeVisible();await page.getByRole('button',{name:'Rename report.pdf'}).click();await page.getByLabel('File name',{exact:true}).fill('My report.pdf');await page.getByRole('button',{name:'Save name'}).click();await expect(page.getByText('My report.pdf',{exact:true})).toBeVisible();await page.reload();await page.getByRole('button',{name:'Document library',exact:false}).click();await expect(page.getByText('My report.pdf',{exact:true})).toBeVisible();
});
test('compression requires explicit quality confirmation',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Compress PDF',exact:false}).first().click();await page.locator('.dropzone input[type=file]').first().setInputFiles(sample('report.pdf'));await page.getByRole('button',{name:'Compress',exact:true}).click();await expect(page.getByText(/Review and confirm the compression settings/)).toBeVisible();await page.getByRole('checkbox',{name:'I understand image recompression is lossy at these settings'}).check();await page.getByRole('button',{name:'Compress',exact:true}).click();await expect(page.getByRole('heading',{name:'Your documents are ready'})).toBeVisible();
});


test('batch watermark exports two real PDFs and a ZIP',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Watermark Studio',exact:true}).click();
 await page.locator('.dropzone input[type=file]').first().setInputFiles([sample('report.pdf'),sample('scanned.pdf')]);
 await page.getByRole('button',{name:'Apply watermark to 2 PDFs',exact:true}).click();
 await expect(page.locator('.output-row')).toHaveCount(2,{timeout:30000});
 await expect(page.getByText('report-watermarked.pdf',{exact:true})).toBeVisible();
 await expect(page.getByText('scanned-watermarked.pdf',{exact:true})).toBeVisible();
 const d=page.waitForEvent('download');await page.getByRole('button',{name:'Download all as ZIP'}).click();expect((await d).suggestedFilename()).toContain('.zip');
});
test('Markdown to Word and live history are real workflows',async({page})=>{
 await page.goto('/');await page.keyboard.press('Control+k');await page.getByRole('textbox',{name:'Search all tools and documents'}).fill('Markdown to Word');await page.getByRole('button',{name:'Markdown to Word Office & data'}).click();
 await page.locator('.dropzone input[type=file]').first().setInputFiles(sample('notes.md'));await page.getByRole('button',{name:'Process',exact:true}).click();
 await expect(page.getByText('notes.docx',{exact:true})).toBeVisible({timeout:20000});
 await page.getByRole('button',{name:'Processing history',exact:true}).click();await expect(page.getByRole('heading',{name:'Markdown to Word',exact:true})).toBeVisible();
});
test('editor places a real image and exports an annotation',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'PDF Editor',exact:true}).click();await page.locator('.dropzone input[type=file]').first().setInputFiles(sample('report.pdf'));
 const canvas=page.locator('.annotation-layer');await expect(canvas).toBeVisible();await page.getByRole('button',{name:'Image',exact:true}).click();
 await canvas.click({position:{x:120,y:180}});
 await page.locator('.modal .dropzone input[type=file]').setInputFiles(sample('landscape.png'));await expect(page.getByAltText('Placed image',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Export edited PDF',exact:true}).click();await expect(page.getByText('report-edited.pdf',{exact:true})).toBeVisible({timeout:20000});
});
test('saved library document opens directly in a working tool',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Document library',exact:false}).click();await page.getByRole('button',{name:'Add documents',exact:true}).click();await page.locator('.modal .dropzone input[type=file]').setInputFiles(sample('report.pdf'));
 await expect(page.locator('.modal-backdrop')).toHaveCount(0);await page.getByRole('button',{name:'Use report.pdf in a tool',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Merge PDFs',exact:true})).toBeVisible();await expect(page.locator('.file-chip').getByText('report.pdf',{exact:true})).toBeVisible();
});


test('image logo watermark includes its uploaded asset in the export job',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Watermark Studio',exact:true}).click();
 await page.locator('.dropzone input[type=file]').first().setInputFiles(sample('report.pdf'));await expect(page.locator('.watermark-page-wrap canvas').first()).toBeVisible();
 await page.getByRole('button',{name:'Image / logo',exact:true}).click();await page.locator('.dropzone input[type=file]').first().setInputFiles(sample('landscape.png'));
 await page.getByRole('button',{name:'Apply watermark',exact:true}).click();await expect(page.getByText('report-watermarked.pdf',{exact:true})).toBeVisible({timeout:20000});
 const d=page.waitForEvent('download');await page.getByRole('button',{name:'Download',exact:true}).click();const file=await d;await file.saveAs('/tmp/studio-logo-watermark.pdf');
 const fs=await import('node:fs/promises');const bytes=await fs.readFile('/tmp/studio-logo-watermark.pdf');expect(bytes.length).toBeGreaterThan(10000);expect(bytes.subarray(0,4).toString()).toBe('%PDF');
});
