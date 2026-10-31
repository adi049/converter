from pathlib import Path
import io, datetime, re
import pymupdf as fitz
from common import open_pdf, parse_pages, color, font_name, save, UserError, note, progress, insert_unicode


def apply(ctx,files,o):
    op=ctx['operation'];doc=open_pdf(files[0],o.get('password'));stem=Path(files[0]['name']).stem
    if op in ('annotate','redact'):
        items=o.get('annotations',[])
        if not items and op=='annotate':note(ctx,'No marks were added; an unchanged copy was exported.')
        redactions=0;replacements=[]
        for item in items:
            i=int(item.get('page',1))-1
            if not 0<=i<doc.page_count:raise UserError('Annotation page is outside the document.')
            p=doc[i];kind=item.get('type');r=fitz.Rect(item.get('rect',[.1,.1,.4,.2]))
            # Editor sends page-normalized coordinates.
            r=fitz.Rect(r.x0*p.rect.width,r.y0*p.rect.height,r.x1*p.rect.width,r.y1*p.rect.height)
            c=color(item.get('color','#7657dc'),(.4,.3,.8));width=float(item.get('width',2));size=float(item.get('fontSize',16));text=str(item.get('text',''))
            if kind in ('redact','whiteout','replace'):
                if kind=='whiteout':
                    note(ctx,'Whiteout is a visual cover, not secure redaction. Use Redact to permanently remove content.')
                    p.draw_rect(r,color=None,fill=(1,1,1),overlay=True)
                else:
                    p.add_redact_annot(r,fill=(1,1,1) if kind=='redact' else None)
                    redactions+=1
                if text and kind=='replace':replacements.append((p,r,text,size,c))
                elif text and kind!='redact':insert_unicode(p,r,text,size,c)
            elif kind=='text':insert_unicode(p,r,text,size,c)
            elif kind=='image':
                f=next((f for f in ctx['files'] if f['id']==item.get('fileId')),None)
                if not f:raise UserError('The annotation image is missing.')
                p.insert_image(r,filename=f['path'],keep_proportion=True,overlay=True)
            elif kind in ('rectangle','ellipse','highlight'):
                if kind=='ellipse':p.draw_oval(r,color=c,width=width,overlay=True)
                elif kind=='rectangle':p.draw_rect(r,color=c,width=width,overlay=True)
                if kind=='highlight':
                    a=p.add_highlight_annot(r);a.set_colors(stroke=c);a.set_opacity(.3);a.update()
            elif kind in ('underline','strike'):
                y=(r.y1 if kind=='underline' else (r.y0+r.y1)/2)
                p.draw_line((r.x0,y),(r.x1,y),color=c,width=width,overlay=True)
            elif kind=='pen':
                points=item.get('points',[])
                if len(points)>1:
                    draw=p.new_shape()
                    draw.draw_polyline([fitz.Point(x*p.rect.width,y*p.rect.height) for x,y in points])
                    draw.finish(color=c,width=width);draw.commit(overlay=True)
            elif kind in ('note','comment'):
                a=p.add_text_annot(r.tl,text,icon='Comment' if kind=='comment' else 'Note');a.set_colors(stroke=c);a.set_info(content=text);a.update()
            elif kind=='signature':
                if item.get('fileId'):
                    f=next((f for f in ctx['files'] if f['id']==item['fileId']),None)
                    if f:p.insert_image(r,filename=f['path'],keep_proportion=True,overlay=True)
                else:p.insert_textbox(r,text or o.get('signatureText','Signed'),fontsize=size,fontname='tiro',color=c)
            elif kind=='date':p.insert_textbox(r,datetime.datetime.now().strftime(item.get('format','%Y-%m-%d %H:%M')),fontsize=size,color=c)
            else:raise UserError('Unsupported annotation type: '+str(kind))
        if redactions:
            for p in doc:
                p.apply_redactions(images=2,graphics=2,text=0)
            for p,r,text,size,c in replacements:insert_unicode(p,r,text,size,c)
            note(ctx,'Existing-text edits remove the selected text and place Unicode replacement text in the same box. Surrounding content does not reflow; review font fit and layout.')
        if redactions:note(ctx,f'Applied {redactions} permanent redaction(s). Underlying text and affected image/vector content were removed. Inspect the result; keep the unredacted original separately.')
        return save(ctx,doc,stem,'-redacted' if op=='redact' else '-edited')
    if op=='find-replace':
        find=str(o.get('find',''));replacement=str(o.get('replacement',''))
        if not find:raise UserError('Enter the text to find.')
        n=0
        for i in parse_pages(o.get('pages'),doc.page_count):
            p=doc[i]
            hits=p.search_for(find)
            for r in hits:
                p.add_redact_annot(r,fill=(1,1,1))
            if hits:p.apply_redactions(images=0,graphics=0)
            for r in hits:
                insert_unicode(p,fitz.Rect(r.x0,r.y0-2,max(r.x1,r.x0+24),r.y1+5),replacement,min(12,r.height*.85))
            n+=len(hits)
        if not n:raise UserError('No exact, extractable text matches found. Scanned documents need OCR; this does not perform fuzzy matching.')
        note(ctx,f'Replaced {n} occurrence(s) using redact-and-overlay. Replacement text does not reflow surrounding paragraphs; long replacements may need a smaller font or manual editing.')
        return output_result(ctx,doc,stem,'-replaced',matches=n)
    if op in ('page-numbers','bates','headers-footers'):
        pages=parse_pages(o.get('pages'),doc.page_count);start=int(o.get('start',1));size=float(o.get('fontSize',10));prefix=str(o.get('prefix',''));position=o.get('position','bottom-center')
        for n,i in enumerate(pages):
            p=doc[i]
            if op=='bates':text=prefix+str(start+n).zfill(int(o.get('digits',6)))
            elif op=='page-numbers':text=str(o.get('format','{n} / {total}')).replace('{n}',str(start+n)).replace('{total}',str(len(pages)+start-1)).replace('{page}',str(start+n))
            else:text=str(o.get('header','')).replace('{n}',str(i+1))
            footer=str(o.get('footer','')).replace('{n}',str(i+1))
            r=p.rect;m=28
            if op=='headers-footers':
                p.insert_textbox(fitz.Rect(m,12,r.width-m,35),text,fontname='helv',fontsize=size,align=1,color=(.3,.3,.3))
                p.insert_textbox(fitz.Rect(m,r.height-28,r.width-m,r.height-8),footer,fontname='helv',fontsize=size,align=1,color=(.3,.3,.3))
            else:
                align=0 if position.endswith('left') else 2 if position.endswith('right') else 1
                y=15 if position.startswith('top') else r.height-28
                p.insert_textbox(fitz.Rect(m,y,r.width-m,y+20),prefix+text if op=='page-numbers' else text,fontname='helv',fontsize=size,align=align,color=(.25,.25,.25))
        return output_result(ctx,doc,stem,'-'+op)
    raise UserError('Unknown editing operation.')

def output_result(ctx,doc,stem,suffix,**meta):return save(ctx,doc,stem,suffix,**meta)
