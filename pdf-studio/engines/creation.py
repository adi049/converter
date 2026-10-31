from pathlib import Path
import csv, io, html, json
import pymupdf as fitz
from common import UserError, page_size, open_pdf, save, output, image_pdf, note, safe_name


def create_text(ctx, files, o):
    """Chromium shapes Unicode; Ghostscript outlines it and a hidden Unicode map preserves search."""
    import html, subprocess, json, shutil
    from pathlib import Path
    from unicode_pdf import searchable_copy
    text=str(o.get('text',''))
    if not text.strip():raise ValueError('Write some text before creating a PDF.')
    if len(text)>500000:raise ValueError('Use an uploaded text file for more than 500,000 characters.')
    out=Path(ctx['out'])/(safe_name(o.get('filename') or 'Text document')+'.pdf');raw=Path(ctx['out'])/'unicode-render.pdf'
    size=max(6,min(72,float(o.get('fontSize',12))));margin=max(0,min(144,float(o.get('margin',50))))
    css=f"body{{font-family:Arial,'Noto Sans','Noto Sans Devanagari',sans-serif;font-size:{size}pt;line-height:1.6}}pre{{font-family:inherit;white-space:pre-wrap;overflow-wrap:anywhere;background:none;padding:0;margin:0}}"
    request={'out':str(out),'html':'<pre>'+html.escape(text)+'</pre>','options':{'pageSize':o.get('pageSize','a4'),'orientation':o.get('orientation','portrait'),'margin':margin,'textCss':css,'header':o.get('header',''),'footer':o.get('footer',''),'pageNumbers':o.get('pageNumbers',False)}}
    node=shutil.which('node')
    if not node:raise ValueError('Unicode PDF creation requires Node.js and local Chromium. See setup guide.')
    result=subprocess.run([node,str(Path(__file__).resolve().parents[1]/'scripts/render_text.mjs')],input=json.dumps(request),text=True,capture_output=True,timeout=180)
    if result.returncode:raise ValueError('Local Unicode renderer failed: '+result.stdout[-500:])
    if any(ord(c)>127 for c in text):
        try:searchable_copy(out,raw,text);shutil.move(str(raw),str(out));note(ctx,'Complex text is visually outlined with an exact invisible Unicode text layer. Selectable/searchable, but not editable as live text.')
        except Exception as exc:note(ctx,'Unicode PDF created, but enhanced search-layer generation failed: '+str(exc)[:150])
    else:shutil.move(str(out),str(raw));shutil.move(str(raw),str(out))
    return [output(ctx,out)]

def blank(ctx, files, o):
    doc=fitz.open(); w,h=page_size(o)
    count=int(o.get('pageCount',1))
    if not 1<=count<=500: raise UserError('Choose between 1 and 500 blank pages.')
    for i in range(count):
        p=doc.new_page(width=w,height=h)
        if o.get('layout') in ('lined','grid'):
            step=24
            for y in range(48,int(h)-30,step): p.draw_line((40,y),(w-40,y),color=(.83,.86,.88),width=.5)
            if o.get('layout')=='grid':
                for x in range(40,int(w)-30,step):p.draw_line((x,40),(x,h-40),color=(.83,.86,.88),width=.5)
    return save(ctx,doc,o.get('filename','Blank document'))


def images(ctx, files, o):
    if not files: raise UserError('Add one or more images.')
    doc=fitz.open(); size=page_size(o) if o.get('fitPage',True) else None
    for f in files:
        if Path(f['path']).suffix.lower() not in ('.jpg','.jpeg','.png','.bmp','.tif','.tiff','.webp'):
            raise UserError('Image to PDF accepts JPG, PNG, BMP, TIFF and WEBP (browser can convert WEBP).')
        tmp=Path(ctx['out'])/'image-composition.pdf'
        image_pdf(f['path'],str(tmp),size)
        part=fitz.open(tmp);doc.insert_pdf(part);part.close();tmp.unlink()
    return save(ctx,doc,o.get('filename','Images'))


def markdown_html(ctx, files, o):
    import markdown
    from bs4 import BeautifulSoup
    text=Path(files[0]['path']).read_text(errors='replace') if files else str(o.get('text',''))
    body=markdown.markdown(text,extensions=['tables','fenced_code','toc'])
    soup=BeautifulSoup(body,'html.parser')
    for tag in soup.find_all(True):
        if tag.name in ('script','iframe','object','embed','form'): tag.decompose()
        for key,value in list(tag.attrs.items()):
            if key.startswith('on') or key not in ('href','src','alt','colspan','rowspan','id'): del tag.attrs[key]
            elif key in ('href','src') and not str(value).startswith(('https://','http://','#','data:image/')): del tag.attrs[key]
    return str(soup)


def csv_pdf(ctx, files, o):
    with open(files[0]['path'],newline='',encoding='utf-8-sig',errors='replace') as f:
        rows=list(csv.reader(f,delimiter='\t' if Path(files[0]['name']).suffix.lower()=='.tsv' else ','))
    if len(rows)>10000: raise UserError('CSV preview is limited to 10,000 rows. Split the source file first.')
    body='<table><thead><tr>'+''.join('<th>'+html.escape(x)+'</th>' for x in rows[0])+'</tr></thead><tbody>'
    body+=''.join('<tr>'+''.join('<td>'+html.escape(x)+'</td>' for x in row)+'</tr>' for row in rows[1:])+'</tbody></table>'
    return body


def office_to_pdf(ctx, files, o):
    import subprocess, shutil, tempfile
    if not shutil.which('libreoffice'): raise UserError('LibreOffice is not installed. See the installation guide.')
    if not files: raise UserError('Choose an Office document.')
    results=[]
    profile=Path(ctx['out'])/'lo-profile'
    for f in files:
        if Path(f['name']).suffix.lower() not in ('.doc','.docx','.ppt','.pptx','.xls','.xlsx','.rtf','.odt','.ods','.odp','.txt','.csv'):
            raise UserError('Unsupported Office input. Use DOCX, PPTX, XLSX, RTF, ODF, TXT or CSV.')
        # Give legacy/ambiguous formats their original extension in an isolated directory.
        inp=Path(ctx['out'])/('source'+Path(f['name']).suffix.lower());shutil.copyfile(f['path'],inp)
        cmd=['libreoffice',f'-env:UserInstallation={profile.as_uri()}','--headless','--norestore','--convert-to','pdf:writer_pdf_Export','--outdir',ctx['out'],str(inp)]
        try:
            p=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        except subprocess.TimeoutExpired: raise UserError('LibreOffice timed out after 180 seconds. Try a smaller document.')
        expected=Path(ctx['out'])/'source.pdf'
        if p.returncode or not expected.exists(): raise UserError('Office conversion failed: '+(p.stderr or p.stdout or 'No PDF produced.')[:500])
        dest=Path(ctx['out'])/(Path(f['name']).stem+'.pdf');expected.replace(dest)
        results.append(output(ctx,dest,engine='LibreOffice'))
        inp.unlink(missing_ok=True)
    note(ctx,'Converted locally with LibreOffice. Complex fonts, macros and layout features can vary; review the PDF before distribution.')
    return results
