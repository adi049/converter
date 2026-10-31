from pathlib import Path
import io, shutil, csv, json, re
import pymupdf as fitz
from PIL import Image
from common import open_pdf, parse_pages, output, progress, note, UserError


def languages():
    import pytesseract
    try:return [x for x in pytesseract.get_languages(config='') if x!='osd']
    except Exception:return []

def pil_page(page,dpi):
    pix=page.get_pixmap(dpi=dpi,alpha=False)
    return Image.open(io.BytesIO(pix.tobytes('png'))).convert('RGB')

def recognize(page,o):
    import pytesseract
    lang=o.get('language','eng')
    if lang not in languages():raise UserError('The requested OCR language is not installed. Choose an available language in Settings.')
    try:return pytesseract.image_to_string(pil_page(page,int(o.get('dpi',200))),lang=lang,config='--psm '+str(int(o.get('psm',3))),timeout=90)
    except Exception as e:raise UserError('OCR failed: '+str(e)[:300])


def apply(ctx,files,o):
    import pytesseract, json
    if not shutil.which('tesseract'):raise UserError('Tesseract OCR is not installed.')
    op=ctx['operation'];f=files[0];is_pdf=Path(f['name']).suffix.lower()=='.pdf';doc=open_pdf(f,o.get('password')) if is_pdf else None
    pages=parse_pages(o.get('pages'),doc.page_count) if doc else [0];stem=Path(f['name']).stem;texts=[];quality=[]
    lang=str(o.get('language','eng'));available=languages()
    if not re_lang(lang,available):raise UserError('An OCR language pack is missing. Install it or select an available language in Settings.')
    dpi=max(100,min(300,int(o.get('dpi',200))));psm=int(o.get('psm',3))
    if psm not in range(14):raise UserError('OCR page segmentation mode must be 0–13.')
    searchable=fitz.open() if op=='ocr-pdf' else None
    for k,i in enumerate(pages):
        image=pil_page(doc[i],dpi) if doc else Image.open(f['path']).convert('RGB')
        if image.width*image.height>40000000:raise UserError('OCR page exceeds 40 megapixels. Lower the DPI.')
        native=doc[i].get_text('text').strip() if doc else ''
        if len(native)>30 and not o.get('force',False):
            text=native;conf=None;method='native'
            if searchable:searchable.insert_pdf(doc,from_page=i,to_page=i)
        else:
            data=pytesseract.image_to_data(image,lang=lang,config='--psm '+str(psm),output_type=pytesseract.Output.DICT,timeout=90)
            words=[(str(t),float(c)) for t,c in zip(data['text'],data['conf']) if str(t).strip() and float(c)>=0]
            conf=round(sum(c for _,c in words)/len(words),1) if words else 0
            text=pytesseract.image_to_string(image,lang=lang,config='--psm '+str(psm),timeout=90);method='ocr'
            if searchable:
                pdfbytes=pytesseract.image_to_pdf_or_hocr(image,lang=lang,extension='pdf',config='--psm '+str(psm),timeout=90)
                with fitz.open('pdf',pdfbytes) as part:searchable.insert_pdf(part)
        texts.append(text);quality.append({'page':i+1,'method':method,'confidence':conf,'characters':len(text)})
        image.close();progress(ctx,f'Recognized page {k+1} of {len(pages)}',100*(k+1)/len(pages))
    if searchable:
        result=__import__('common').save(ctx,searchable,stem,'-searchable',pages=len(pages),language=lang,quality=quality)
        qp=Path(ctx['out'])/(stem+'-ocr-quality.json');qp.write_text(json.dumps(quality,indent=2));output(ctx,qp)
        note(ctx,'Searchable PDF generated locally. Forced OCR rasterizes pages at the selected DPI. Existing native-text pages are retained unless Force OCR is enabled. Confidence is a Tesseract estimate, not a correctness guarantee.')
        return [ctx['results'][-2],result]
    text='\
\
'.join(f'--- Page {i+1} ---\
{t}' for i,t in zip(pages,texts))
    if op=='ocr-docx':
        from docx import Document
        from docx.oxml.ns import qn
        d=Document();d.core_properties.title=stem+' — OCR'
        normal=d.styles['Normal'];normal.font.name='Noto Sans Devanagari' if 'hin' in lang else 'Noto Sans';normal.font.size=__import__('docx').shared.Pt(11)
        normal.element.rPr.rFonts.set(qn('w:eastAsia'),normal.font.name);normal.element.rPr.rFonts.set(qn('w:cs'),normal.font.name)
        for i,t in zip(pages,texts):
            d.add_heading(f'Page {i+1}',level=1)
            for para in t.split('\
\
'):d.add_paragraph(para)
        p=Path(ctx['out'])/(stem+'-ocr.docx');d.save(p)
    else:p=Path(ctx['out'])/(stem+'-ocr.txt');p.write_text(text,encoding='utf-8')
    qp=Path(ctx['out'])/(stem+'-ocr-quality.json');qp.write_text(json.dumps(quality,indent=2));output(ctx,qp)
    avg=[q['confidence'] for q in quality if q['confidence'] is not None];mean=round(sum(avg)/len(avg),1) if avg else None
    note(ctx,'OCR is machine-recognized text. Review names, numbers and Hindi matras against the source. The quality report shows per-page word confidence; low confidence suggests a higher DPI or a different language pack.')
    primary=output(ctx,p,characters=len(text),quality=quality,confidence=mean)
    return [primary,next(x for x in ctx['results'] if x['path'].endswith('.json'))]

def re_lang(lang,available):
    return bool(lang) and all(x in available for x in lang.split('+'))

def tables(ctx,files,o):
    import pytesseract
    from openpyxl import Workbook
    f=files[0];pdf=Path(f['name']).suffix.lower()=='.pdf';doc=open_pdf(f,o.get('password')) if pdf else None
    pages=parse_pages(o.get('pages'),doc.page_count) if doc else [0]
    wb=Workbook();wb.remove(wb.active);count=0
    for i in pages:
        ws=wb.create_sheet(f'Page {i+1}');native=[]
        if doc:
            try:native=doc[i].find_tables().tables
            except Exception:pass
        if native and not o.get('force',False):
            rown=1
            for table in native:
                for row in table.extract():
                    for c,v in enumerate(row,1):ws.cell(rown,c,v)
                    rown+=1
                rown+=2;count+=1
        else:
            image=pil_page(doc[i],200) if doc else Image.open(f['path']).convert('RGB')
            data=pytesseract.image_to_data(image,lang=o.get('language','eng'),output_type=pytesseract.Output.DICT,timeout=90)
            lines={}
            for j,txt in enumerate(data['text']):
                if not txt.strip():continue
                key=(data['block_num'][j],data['par_num'][j],data['line_num'][j])
                lines.setdefault(key,[]).append((data['left'][j],txt))
            # Heuristic columns based on horizontal gaps, not a claimed table reconstruction.
            for r,words in enumerate(lines.values(),1):
                words.sort();col=1;last=None
                for x,txt in words:
                    if last is not None and x-last>image.width*.06:col+=1
                    ws.cell(r,col,((str(ws.cell(r,col).value)+' ') if ws.cell(r,col).value else '')+txt);last=x+len(txt)*9;col+=1
            count+=1
        ws.column_dimensions['A'].width=30
    p=Path(ctx['out'])/(Path(f['name']).stem+'-tables.xlsx');wb.save(p)
    note(ctx,'Native PDF tables use PyMuPDF grid detection. Scanned/image tables use a best-effort OCR line-and-gap heuristic; merged cells and complex grids need manual review. This is not an exact table reconstruction.')
    return output(ctx,p,tables=count,fidelity='best-effort')
