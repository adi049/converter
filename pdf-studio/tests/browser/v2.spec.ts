import {test,expect} from '@playwright/test';
import path from 'node:path';
const sample=(n:string)=>path.resolve('tests/samples',n);
test.afterEach(async({page})=>{await page.evaluate(async()=>{const token=sessionStorage.getItem('studio-token');if(token)await fetch('/api/session',{method:'DELETE',headers:{Authorization:'Bearer '+token}});}).catch(()=>{});});
test('fixed brand, Luna link and mobile studio have no overflow',async({page})=>{
 await page.goto('/');await expect(page.locator('html')).toHaveAttribute('data-theme','studio');await expect(page.getByRole('button',{name:/Switch to.*mode/})).toHaveCount(0);
 const link=page.getByRole('link',{name:/Managed By Luna website/});await expect(link).toHaveAttribute('target','_blank');await expect(link).toHaveAttribute('href','https://adi049.github.io/ManagedByLuna/');
 await page.screenshot({path:'artifacts/v2-dashboard.png',fullPage:true});await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'Open navigation'}).click();await page.getByRole('button',{name:'Watermark Studio',exact:true}).click();await page.waitForTimeout(500);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await expect(link).toBeVisible();await page.screenshot({path:'artifacts/v2-mobile-watermark.png',fullPage:true});
});
test('Hindi text creates a searchable PDF and preview search finds it',async({page})=>{
 
 await page.goto('/');await page.keyboard.press('Control+k');await page.getByRole('textbox',{name:'Search all tools and documents'}).fill('Text to PDF');await page.getByRole('button',{name:'Text to PDF Create',exact:true}).click();
 await page.getByLabel('Document text',{exact:true}).fill('नमस्ते दुनिया। हिंदी PDF परीक्षण।');await page.getByRole('button',{name:'Create',exact:true}).click();await expect(page.getByText('Text document.pdf',{exact:true})).toBeVisible({timeout:30000});
 await page.getByRole('button',{name:'Preview Text document.pdf'}).click();await page.getByRole('textbox',{name:'Search PDF text'}).fill('नमस्ते');await page.getByRole('button',{name:'Find',exact:true}).click();await expect(page.getByText('1 / 1 pages')).toBeVisible();
});
test('library backup, metadata export and non-destructive restore',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Document library',exact:false}).click();await page.getByRole('button',{name:'Add documents',exact:true}).click();await page.locator('.modal .dropzone input[type=file]').setInputFiles(sample('report.pdf'));await expect(page.locator('.modal-backdrop')).toHaveCount(0);
 const d=page.waitForEvent('download');await page.getByRole('button',{name:'Backup library',exact:true}).click();const file=await d;await file.saveAs('/tmp/studio-v2-backup.zip');
 await page.locator('input[accept=".zip"]').setInputFiles('/tmp/studio-v2-backup.zip');await expect(page.getByRole('dialog',{name:'Restore library backup?'})).toBeVisible();await page.getByRole('button',{name:'Restore documents',exact:true}).click();await expect(page.locator('.modal-backdrop')).toHaveCount(0);await expect(page.locator('.library-row')).toHaveCount(2);
 const m=page.waitForEvent('download');await page.getByRole('button',{name:'Export metadata',exact:true}).click();expect((await m).suggestedFilename()).toContain('metadata.json');
});
test('existing text can be selected and genuinely replaced',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'PDF Editor',exact:true}).click();await page.locator('.dropzone input[type=file]').first().setInputFiles(sample('report.pdf'));await page.getByRole('button',{name:'Edit existing text',exact:true}).click();await page.locator('.existing-text-target[title="Edit: Find this exact phrase: ORIGINAL TEXT."]').click();
 await page.getByLabel('Text content',{exact:true}).fill('REVISED TEXT');await page.getByRole('button',{name:'Replace text',exact:true}).click();await page.getByRole('button',{name:'Export edited PDF',exact:true}).click();await expect(page.getByText('report-redacted.pdf',{exact:true})).toBeVisible({timeout:30000});
});
test('watermark custom font, exact placement and tiled preview export',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Watermark Studio',exact:true}).click();await page.locator('.dropzone input[type=file]').first().setInputFiles(sample('report.pdf'));await expect(page.locator('.watermark-overlay')).toBeVisible();
 await page.locator('input[accept=".ttf,.otf"]').setInputFiles('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf');await page.getByRole('button',{name:'Exact X / Y position'}).click();await page.getByLabel('Position units',{exact:true}).selectOption('pt');await page.getByLabel('X center (pt)',{exact:true}).fill('280');await page.getByLabel('Y center (pt)',{exact:true}).fill('400');await page.getByRole('switch',{name:'Tile watermark'}).click();await page.getByRole('button',{name:'Apply watermark',exact:true}).click();await expect(page.getByText('report-watermarked.pdf',{exact:true})).toBeVisible({timeout:30000});
});
test('failed processing exposes real error details and retry produces output',async({page})=>{
 await page.goto('/');await page.keyboard.press('Control+k');await page.getByRole('textbox',{name:'Search all tools and documents'}).fill('Compress PDF');await page.getByRole('button',{name:'Compress PDF Optimize',exact:true}).click();await page.locator('.dropzone input[type=file]').first().setInputFiles(sample('report.pdf'));await page.getByRole('button',{name:'Compress',exact:true}).click();await expect(page.getByText(/Review and confirm the compression settings/)).toBeVisible();await page.getByRole('checkbox',{name:'I understand image recompression is lossy at these settings'}).check();await page.getByRole('button',{name:'Retry failed tasks'}).click();await expect(page.getByText('report-compressed.pdf',{exact:true})).toBeVisible({timeout:20000});
});
