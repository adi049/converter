from pathlib import Path
import json, html, difflib, io, csv, base64
import pymupdf as fitz
from PIL import Image, ImageChops, ImageEnhance
from common import open_pdf, save, output, note, UserError, progress


def apply(ctx,files,o):
    op=ctx['operation'];f=files[0];stem=Path(f['name']).stem
    if op=='compare':
        if len(files)<2:raise UserError('Choose two PDFs: the original first, then the revised version.')
        a=open_pdf(files[0],o.get('password'));b=open_pdf(files[1],o.get('replacementPassword',o.get('password')))
        ta=[p.get_text('text',sort=True) for p in a];tb=[p.get_text('text',sort=True) for p in b]
        diff='\n'.join(difflib.unified_diff('\n\n'.join(ta).splitlines(),'\n\n'.join(tb).splitlines(),fromfile=files[0]['name'],tofile=files[1]['name'],lineterm=''))
        p=Path(ctx['out'])/(stem+'-comparison.txt');p.write_text(diff or 'No extractable text differences.',encoding='utf-8');output(ctx,p)
        parts=['<!doctype html><meta charset="utf-8"><title>PDF comparison</title><style>body{font:14px system-ui;margin:40px auto;max-width:1100px;color:#292438}pre{white-space:pre-wrap;padding:12px;border-radius:8px}.add{background:#e4f6ed}.del{background:#ffe8e8}.ctx{background:#f3f3f6}img{max-width:100%;border:1px solid #ddd}section{margin:32px 0}</style><h1>Document comparison</h1><p>Original: '+html.escape(files[0]['name'])+'<br>Revised: '+html.escape(files[1]['name'])+'</p><p>Page counts: '+str(len(ta))+' → '+str(len(tb))+'. Visual differences are highlighted in magenta at 90 DPI. Scanned PDFs require OCR for meaningful text differences.</p>']
        changes=[]
        for line in diff.splitlines():
            cls='add' if line.startswith('+') else 'del' if line.startswith('-') else 'ctx'
            parts.append('<pre class="'+cls+'">'+html.escape(line)+'</pre>')
        for i in range(max(len(ta),len(tb))):
            changed=i>=len(ta) or i>=len(tb) or ta[i]!=tb[i]
            if o.get('visual',True) and i<len(ta) and i<len(tb):
                pa=a[i].get_pixmap(dpi=90,alpha=False);pb=b[i].get_pixmap(dpi=90,alpha=False)
                ia=Image.open(io.BytesIO(pa.tobytes('png'))).convert('RGB');ib=Image.open(io.BytesIO(pb.tobytes('png'))).convert('RGB')
                size=(max(ia.width,ib.width),max(ia.height,ib.height));basea=Image.new('RGB',size,'white');baseb=Image.new('RGB',size,'white');basea.paste(ia);baseb.paste(ib)
                mask=ImageChops.difference(basea,baseb).convert('L').point(lambda x:255 if x>24 else 0)
                changed=changed or bool(mask.getbbox())
                overlay=Image.new('RGB',size,'#d839ad');baseb.paste(overlay,(0,0),mask)
                bio=io.BytesIO();baseb.save(bio,format='PNG');dp=Path(ctx['out'])/f'visual-page-{i+1}.png';dp.write_bytes(bio.getvalue());output(ctx,dp,page=i+1)
                parts.append(f'<section><h2>Page {i+1} {"— changed" if changed else "— visually identical"}</h2><img src="data:image/png;base64,{base64.b64encode(bio.getvalue()).decode()}" alt="Visual comparison page {i+1}"></section>')
            changes.append({'page':i+1,'changed':changed})
            progress(ctx,f'Compared page {i+1}',100*(i+1)/max(len(ta),len(tb)))
        hp=Path(ctx['out'])/(stem+'-comparison.html');hp.write_text(''.join(parts),encoding='utf-8');output(ctx,hp)
        note(ctx,'Comparison uses extracted text and optional raster differences. Font or rendering differences can appear visual; OCR is not run automatically. Identical extracted text does not guarantee identical vector content.');return ctx['results'][:]
    if op=='csv-xlsx':return csv_xlsx(ctx,files,o)
    doc=open_pdf(f,o.get('password'))
    if op=='metadata':
        data={'file':f['name'],'pages':doc.page_count,'metadata':doc.metadata,'bookmarks':doc.get_toc(),'permissions':doc.permissions,'encrypted':bool(doc.is_encrypted),'pageSizes':[{'page':i+1,'width':p.rect.width,'height':p.rect.height} for i,p in enumerate(doc)]}
        p=Path(ctx['out'])/(stem+'-metadata.json');p.write_text(json.dumps(data,indent=2));return output(ctx,p,metadata=data)
    if op=='edit-metadata':
        if o.get('remove',False):doc.set_metadata({});doc.del_xml_metadata()
        else:
            metadata=doc.metadata or {}
            for key in ('title','author','subject','keywords','creator','producer'):
                if key in o.get('metadata',{}):metadata[key]=str(o['metadata'][key])
            doc.set_metadata(metadata)
        return save(ctx,doc,stem,'-metadata')
    if op=='bookmarks':
        if o.get('remove',False):doc.set_toc([])
        else:
            toc=o.get('bookmarks',[])
            if not isinstance(toc,list) or len(toc)>2000:raise UserError('Provide up to 2,000 bookmarks as [level, title, page] entries.')
            clean=[];previous=1
            for row in toc:
                if not isinstance(row,list) or len(row)!=3:raise UserError('Each bookmark must be [level, title, page].')
                level,title,page=int(row[0]),str(row[1]),int(row[2])
                if not 1<=page<=doc.page_count or not 1<=level<=previous+1:raise UserError('Bookmark page or hierarchy is invalid.')
                clean.append([level,title,page]);previous=level
            if clean and clean[0][0]!=1:raise UserError('The first bookmark must have level 1.')
            doc.set_toc(clean)
        return save(ctx,doc,stem,'-bookmarks')
    if op=='generate-toc':
        toc=[]
        for i,p in enumerate(doc):
            spans=[s for b in p.get_text('dict')['blocks'] if b['type']==0 for l in b['lines'] for s in l['spans'] if s['text'].strip()]
            if not spans:continue
            avg=sum(s['size'] for s in spans)/len(spans);large=[s for s in spans if s['size']>avg*1.25 and len(s['text'].strip())>2]
            if large:toc.append([1,large[0]['text'].strip()[:120],i+1])
        if not toc:raise UserError('No larger heading text was detected. Add bookmarks manually in Bookmarks management.')
        doc.set_toc(toc)
        if o.get('insertPage',False):
            p=doc.new_page(pno=0,width=doc[1].rect.width,height=doc[1].rect.height);p.insert_text((50,65),'Table of contents',fontsize=24,fontname='helv')
            for j,(_,title,page) in enumerate(toc[:40]):p.insert_text((50,110+j*18),f'{title[:75]}  ......  {page+1}',fontsize=11);toc[j][2]+=1
            for row in toc[40:]:row[2]+=1
            doc.set_toc(toc)
        note(ctx,'Generated from larger-than-body text. Review heading detection and page references, especially in multi-column or scanned documents.');return save(ctx,doc,stem,'-contents',bookmarks=len(toc))
    if op=='flatten':
        doc.bake(annots=True,widgets=True)
        note(ctx,'Form and annotation appearances are baked into permanent page content using PyMuPDF. Interactive fields and comments are no longer editable. Review filled fields before distribution.')
        return save(ctx,doc,stem,'-flattened')
    raise UserError('Unknown advanced operation.')

def markdown_docx(ctx,files,o):
    import markdown
    from bs4 import BeautifulSoup, NavigableString
    from docx import Document
    from docx.shared import Pt
    text=Path(files[0]['path']).read_text(encoding='utf-8-sig',errors='replace')
    soup=BeautifulSoup(markdown.markdown(text,extensions=['tables','fenced_code']), 'html.parser')
    doc=Document();doc.core_properties.title=Path(files[0]['name']).stem
    def inline(paragraph,node,bold=False,italic=False):
        if not isinstance(node,NavigableString):
            if node.name in ('script','style','iframe','object'):return
            b=bold or node.name in ('strong','b');i=italic or node.name in ('em','i')
            if node.name=='br':paragraph.add_run().add_break()
            for child in node.children:inline(paragraph,child,b,i)
        else:
            run=paragraph.add_run(str(node));run.bold=bold;run.italic=italic
            if getattr(node,'parent',None) and node.parent.name=='code':run.font.name='Courier New'
    for node in soup.children:
        if not isinstance(node,NavigableString):
            if node.name in ('h1','h2','h3','h4','h5','h6'):doc.add_heading(node.get_text(),level=int(node.name[1])-1)
            elif node.name=='table':
                rows=node.find_all('tr');t=doc.add_table(rows=len(rows),cols=max(len(r.find_all(['td','th'])) for r in rows));t.style='Table Grid'
                for r,row in enumerate(rows):
                    for c,cell in enumerate(row.find_all(['td','th'])):inline(t.cell(r,c).paragraphs[0],cell,bold=cell.name=='th')
            elif node.name in ('ul','ol'):
                for li in node.find_all('li',recursive=False):inline(doc.add_paragraph(style='List Bullet' if node.name=='ul' else 'List Number'),li)
            elif node.name=='blockquote':inline(doc.add_paragraph(style='Quote'),node)
            elif node.name in ('p','pre','div'):inline(doc.add_paragraph(),node)
            elif node.name=='hr':doc.add_paragraph('────────────────────────')
        elif str(node).strip():doc.add_paragraph(str(node))
    p=Path(ctx['out'])/(Path(files[0]['name']).stem+'.docx');doc.save(p)
    note(ctx,'Markdown headings, paragraphs, lists, tables and inline emphasis were converted to editable DOCX. Remote images are not fetched; complex raw HTML is exported as text.')
    return output(ctx,p)


def csv_xlsx(ctx,files,o):
    f=files[0];stem=Path(f['name']).stem
    from openpyxl import Workbook
    with open(f['path'],encoding='utf-8-sig',newline='') as src:rows=list(csv.reader(src))
    if len(rows)>100000:raise UserError('CSV import is limited to 100,000 rows.')
    wb=Workbook();ws=wb.active;ws.title='Data'
    for row in rows:
        if len(row)>16384:raise UserError('CSV import is limited to 16,384 columns.')
        ws.append(row)
        for cell in ws[ws.max_row]:cell.data_type='s'
    ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
    p=Path(ctx['out'])/(stem+'.xlsx');wb.save(p);note(ctx,'CSV fields are imported as text to preserve leading zeros and avoid spreadsheet formula injection.');return output(ctx,p)
