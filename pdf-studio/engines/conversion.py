from pathlib import Path
import io, re, html, base64, json
import pymupdf as fitz
from common import open_pdf, parse_pages, output, progress, note, UserError


def apply(ctx, files, o):
    op=ctx['operation'];doc=open_pdf(files[0],o.get('password'));stem=Path(files[0]['name']).stem
    pages=parse_pages(o.get('pages'),doc.page_count)
    if not pages:raise UserError('Select at least one page.')
    if op in ('pdf-jpg','pdf-png','pdf-images'):
        fmt='jpg' if op=='pdf-jpg' else 'png';dpi=max(72,min(300,int(o.get('dpi',150))))
        for k,i in enumerate(pages):
            pix=doc[i].get_pixmap(dpi=dpi,alpha=False)
            p=Path(ctx['out'])/f'{stem}-{i+1:03d}.{fmt}'
            if fmt=='jpg':pix.pil_save(p,quality=int(o.get('quality',90)),optimize=True)
            else:pix.pil_save(p,optimize=True)
            output(ctx,p,page=i+1,width=pix.width,height=pix.height)
            progress(ctx,f'Rendered page {i+1}',100*(k+1)/len(pages))
        return ctx['results'][-len(pages):]
    if op=='pdf-text':
        chunks=[]
        for i in pages:chunks.append(f'--- Page {i+1} ---\n'+doc[i].get_text('text',sort=True))
        text='\n\n'.join(chunks)
        if len(text.strip())<len(pages)*20 and o.get('ocr',False):
            from ocr import recognize
            text='\n\n'.join(recognize(doc[i],o) for i in pages)
            note(ctx,'Text recovered using local Tesseract OCR. Review recognition errors.')
        p=Path(ctx['out'])/(stem+'.txt');p.write_text(text,encoding='utf-8');return output(ctx,p,characters=len(text))
    if op=='pdf-html':
        parts=['<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(stem)+'</title><style>body{margin:0;background:#eceef2;font-family:Arial,sans-serif}.page{position:relative;margin:24px auto;background:white;box-shadow:0 2px 16px #0002;overflow:hidden}.page p{position:absolute;margin:0;white-space:pre-wrap}.page img{position:absolute} @media print{body{background:white}.page{margin:0;box-shadow:none;break-after:page}}</style></head><body>']
        for i in pages:
            p=doc[i];parts.append(f'<section class="page" aria-label="Page {i+1}" style="width:{p.rect.width}px;height:{p.rect.height}px">')
            data=p.get_text('dict')
            for block in data['blocks']:
                if block['type']==1:
                    enc=base64.b64encode(block['image']).decode();x0,y0,x1,y1=block['bbox']
                    parts.append(f'<img alt="Embedded image" style="left:{x0}px;top:{y0}px;width:{x1-x0}px;height:{y1-y0}px" src="data:{block.get("ext","png")};base64,{enc}">')
                else:
                    for line in block.get('lines',[]):
                        for span in line['spans']:
                            x,y=span['origin'];c=span['color'];family='monospace' if 'mono' in span['font'].lower() else 'serif' if any(s in span['font'].lower() for s in ('times','serif','roman')) else 'sans-serif'
                            style=f'left:{x}px;top:{y-span["size"]*.88}px;font-size:{span["size"]}px;color:#{c:06x};font-family:{family};'
                            if 'bold' in span['font'].lower():style+='font-weight:bold;'
                            if 'italic' in span['font'].lower():style+='font-style:italic;'
                            parts.append('<p style="'+style+'">'+html.escape(span['text'])+'</p>')
            parts.append('</section>')
        parts.append('</body></html>');p=Path(ctx['out'])/(stem+'.html');p.write_text(''.join(parts),encoding='utf-8')
        note(ctx,'Self-contained HTML uses absolute text positioning and embedded images to preserve the page appearance. It is not a semantic, reflowing web document.')
        return output(ctx,p)
    if op=='pdf-markdown':
        chunks=['# '+stem]
        for i in pages:
            chunks.append(f'\n## Page {i+1}\n')
            blocks=doc[i].get_text('blocks',sort=True)
            for b in blocks:
                text=b[4].strip()
                if not text:continue
                sizes=[s['size'] for bl in doc[i].get_text('dict')['blocks'] if bl['type']==0 for l in bl['lines'] for s in l['spans'] if s['text'].strip()]
                average=sum(sizes)/len(sizes) if sizes else 12
                prefix='### ' if b[4].strip() and max((s['size'] for bl in doc[i].get_text('dict')['blocks'] if bl['type']==0 and abs(bl['bbox'][1]-b[1])<3 for l in bl['lines'] for s in l['spans']),default=12)>average*1.3 else ''
                chunks.append(prefix+text.replace('\n',' ')+'\n')
        p=Path(ctx['out'])/(stem+'.md');p.write_text('\n'.join(chunks),encoding='utf-8')
        note(ctx,'Markdown preserves reading order and heading hints, not PDF coordinates. Review tables and multi-column documents.');return output(ctx,p)
    if op=='pdf-docx':return to_docx(ctx,doc,pages,stem,o)
    if op=='pdf-xlsx':return to_xlsx(ctx,doc,pages,stem,o,files)
    if op=='pdf-pptx':return to_pptx(ctx,doc,pages,stem,o)
    raise UserError('Unknown conversion.')


def to_docx(ctx,doc,pages,stem,o):
    from docx import Document
    from docx.shared import Pt, Inches
    from docx.oxml.ns import qn
    font_name='Noto Sans Devanagari' if o.get('language')=='hin' else 'Noto Sans'
    out=Document();out.core_properties.title=stem;out.styles['Normal'].font.name=font_name;out.styles['Normal'].element.rPr.rFonts.set(qn('w:eastAsia'),font_name);out.styles['Normal'].element.rPr.rFonts.set(qn('w:cs'),font_name)
    sec=out.sections[0]
    def size_section(sec,page):
        from docx.enum.section import WD_ORIENT
        w,h=page.rect.width,page.rect.height;sec.page_width=Pt(w);sec.page_height=Pt(h);sec.orientation=WD_ORIENT.LANDSCAPE if w>h else WD_ORIENT.PORTRAIT;sec.top_margin=sec.bottom_margin=Inches(.6);sec.left_margin=sec.right_margin=Inches(.6)
    size_section(sec,doc[pages[0]])
    for k,i in enumerate(pages):
        page=doc[i]
        if k:
            prev=doc[pages[k-1]]
            if (prev.rect.width,prev.rect.height)!=(page.rect.width,page.rect.height):sec=out.add_section();size_section(sec,page)
            else:out.add_page_break()
        if o.get('mode','editable')=='facsimile':
            bio=io.BytesIO();page.get_pixmap(dpi=150,alpha=False).pil_save(bio,format='PNG')
            out.add_picture(bio,width=sec.page_width-sec.left_margin-sec.right_margin)
        else:
            table_boxes=[];table_items=[]
            if o.get('tables',True):
                try:
                    for table in page.find_tables().tables:
                        table_boxes.append(table.bbox)
                        values=table.extract();table_items.append({'type':4,'bbox':(0,table.bbox[1],0,table.bbox[1]+1),'values':values})
                except Exception:note(ctx,'Some tables could not be reconstructed and were exported as text.')
            blocks=page.get_text('dict')['blocks']
            for b in sorted(blocks+table_items,key=lambda b:(b['bbox'][1],b['bbox'][0])):
                x0,y0,x1,y1=b['bbox']
                if b['type']==4:
                    values=b['values'];t=out.add_table(rows=len(values),cols=max(len(r) for r in values));t.style='Table Grid'
                    for ri,row in enumerate(values):
                        for ci,val in enumerate(row):t.cell(ri,ci).text=val or ''
                    continue
                if any(x0>=tb[0]-2 and y0>=tb[1]-2 and x1<=tb[2]+2 and y1<=tb[3]+2 for tb in table_boxes):continue
                if b['type']==1:
                    try:out.add_picture(io.BytesIO(b['image']),width=min(Inches(6),Pt(x1-x0)))
                    except Exception:note(ctx,'An unsupported embedded image could not be exported to DOCX.')
                    continue
                p=out.add_paragraph()
                for line in b.get('lines',[]):
                    for s in line['spans']:
                        run=p.add_run(s['text']+' ');run.font.size=Pt(min(48,max(6,s['size'])));run.bold='bold' in s['font'].lower();run.italic='italic' in s['font'].lower()
        progress(ctx,f'Exported page {i+1} to DOCX',100*(k+1)/len(pages))
    p=Path(ctx['out'])/(stem+'.docx');out.save(p)
    note(ctx,'PDF → Word is a best-effort reconstruction. Reading order, font styles, images and detected tables are retained; complex columns, text wrapping and original font metrics may differ. Choose page-image fidelity for an exact visual reference.')
    return output(ctx,p,engine='python-docx + PyMuPDF',fidelity='best-effort')


def to_xlsx(ctx,doc,pages,stem,o,files):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    wb=Workbook();wb.remove(wb.active);tables_count=0
    for i in pages:
        ws=wb.create_sheet(f'Page {i+1}');rownum=1;found=[]
        try:found=doc[i].find_tables().tables
        except Exception:found=[]
        if not found:
            try:
                import pdfplumber
                with pdfplumber.open(files[0]['path']) as plumber:grid=plumber.pages[i].extract_tables()
                if grid:
                    for values in grid:
                        for row in values:
                            for c,v in enumerate(row,1):ws.cell(rownum,c,v or '')
                            rownum+=1
                        rownum+=2;tables_count+=1
                    continue
            except Exception:note(ctx,'Secondary table detection was unavailable for a page; extracted text was retained.')
        for t in found:
            for row in t.extract():
                for c,v in enumerate(row,1):
                    cell=ws.cell(rownum,c,v or '');cell.alignment=Alignment(wrap_text=True,vertical='top')
                    if rownum==t.row_count:cell.font=Font(bold=True)
                if rownum==1:
                    for cell in ws[rownum]:cell.fill=PatternFill('solid',fgColor='E9E2FF');cell.font=Font(bold=True)
                rownum+=1
            tables_count+=1;rownum+=2
        if not found:
            ws.cell(1,1,'Extracted text — no reliable table grid detected').font=Font(bold=True)
            for line in doc[i].get_text('text',sort=True).splitlines():ws.cell(rownum+1,1,line);rownum+=1
        ws.column_dimensions['A'].width=36
        for col in 'BCDEFGHIJKLMNOP':ws.column_dimensions[col].width=22
        ws.freeze_panes='A2'
    p=Path(ctx['out'])/(stem+'.xlsx');wb.save(p)
    note(ctx,f'Detected {tables_count} table(s). Each PDF page becomes a worksheet. Untabled text is exported into column A; scanned PDFs require OCR first. Verify cell boundaries and values.')
    return output(ctx,p,tables=tables_count,fidelity='heuristic table detection')


def to_pptx(ctx,doc,pages,stem,o):
    from pptx import Presentation
    from pptx.util import Pt
    prs=Presentation();prs.slide_width=Pt(doc[pages[0]].rect.width);prs.slide_height=Pt(doc[pages[0]].rect.height)
    for k,i in enumerate(pages):
        page=doc[i];slide=prs.slides.add_slide(prs.slide_layouts[6])
        scale=min(prs.slide_width/page.rect.width,prs.slide_height/page.rect.height);sx=sy=scale
        if o.get('mode','facsimile')=='facsimile':
            bio=io.BytesIO();page.get_pixmap(dpi=150,alpha=False).pil_save(bio,format='PNG')
            slide.shapes.add_picture(bio,int((prs.slide_width-page.rect.width*scale)/2),int((prs.slide_height-page.rect.height*scale)/2),width=int(page.rect.width*scale),height=int(page.rect.height*scale))
            slide.notes_slide.notes_text_frame.text=page.get_text('text')
        else:
            blocks=sorted(page.get_text('dict')['blocks'],key=lambda b:(b['bbox'][1],b['bbox'][0]))
            for b in blocks:
                x0,y0,x1,y1=b['bbox']
                if b['type']==1:
                    try:slide.shapes.add_picture(io.BytesIO(b['image']),int(x0*sx),int(y0*sy),width=int((x1-x0)*sx),height=int((y1-y0)*sy))
                    except Exception:pass
                else:
                    shape=slide.shapes.add_textbox(int(x0*sx),int(y0*sy),max(Pt(30),int((x1-x0)*sx)),max(Pt(16),int((y1-y0)*sy)))
                    tf=shape.text_frame;tf.word_wrap=True
                    for j,line in enumerate(b.get('lines',[])):
                        p=tf.paragraphs[0] if j==0 else tf.add_paragraph()
                        for s in line['spans']:
                            r=p.add_run();r.text=s['text']+' ';r.font.size=Pt(max(6,min(72,s['size'])));r.font.bold='bold' in s['font'].lower()
        progress(ctx,f'Exported slide {k+1}',100*(k+1)/len(pages))
    p=Path(ctx['out'])/(stem+'.pptx');prs.save(p)
    note(ctx,'Page-image mode preserves appearance but slide content is not editable; extracted text is included in speaker notes. Editable mode reconstructs text boxes and images, not the original PowerPoint objects.')
    if any((doc[i].rect.width,doc[i].rect.height)!=(doc[pages[0]].rect.width,doc[pages[0]].rect.height) for i in pages):note(ctx,'PowerPoint requires one slide size. Mixed PDF page sizes were scaled proportionally and centered, not stretched.')
    return output(ctx,p,engine='python-pptx',fidelity=o.get('mode','facsimile'))
