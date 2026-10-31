from pathlib import Path
import json, io, zipfile
import pymupdf as fitz
from PIL import Image
from common import open_pdf, parse_pages, save, output, page_size, UserError, progress, note


def apply(ctx, files, o):
    op=ctx['operation'];doc=open_pdf(files[0],o.get('password'));stem=Path(files[0]['name']).stem
    count=doc.page_count;selected=parse_pages(o.get('pages'),count)
    if op=='merge':
        merged=fitz.open()
        for f in files:
            part=open_pdf(f,o.get('passwords',{}).get(f['id'],o.get('password')))
            start=merged.page_count+1
            merged.insert_pdf(part)
            if o.get('bookmarks',True):
                toc=merged.get_toc();toc.append([1,Path(f['name']).stem,start]);merged.set_toc(toc)
            part.close()
        return save(ctx,merged,o.get('filename','Merged document'))
    if op in ('extract-pages','delete-pages','split','reverse','duplicate-pages'):
        if op=='reverse':order=list(reversed(range(count)))
        elif op=='delete-pages':
            if len(selected)==count:raise UserError('Cannot delete every page. Keep at least one page.')
            order=[i for i in range(count) if i not in selected]
        elif op=='duplicate-pages':
            order=list(range(count))
            for i in selected:order.insert(order.index(i)+1,i)
        elif op=='split':
            every=int(o.get('every',1))
            if every<1:raise UserError('Pages per file must be at least 1.')
            results=[]
            for start in range(0,count,every):
                part=fitz.open();part.insert_pdf(doc,from_page=start,to_page=min(start+every,count)-1)
                results.append(save(ctx,part,stem,f'-pages-{start+1}-{min(start+every,count)}'))
            return results
        else:
            if not selected:raise UserError('Select at least one page.')
            order=selected
        result=fitz.open()
        for i in order:result.insert_pdf(doc,from_page=i,to_page=i)
        return save(ctx,result,stem,'-'+op)
    if op=='rotate-pages':
        angle=int(o.get('angle',90))
        if angle not in (-270,-180,-90,0,90,180,270):raise UserError('Rotation must be a multiple of 90 degrees.')
        for i in selected:doc[i].set_rotation((doc[i].rotation+angle)%360)
        return save(ctx,doc,stem,'-rotated')
    if op=='reorder-pages':
        order=o.get('order',[])
        if sorted(int(x)-1 for x in order)!=list(range(count)):raise UserError('The page order must include each original page exactly once.')
        result=fitz.open()
        for x in order:result.insert_pdf(doc,from_page=int(x)-1,to_page=int(x)-1)
        return save(ctx,result,stem,'-organized')
    if op=='insert-blank':
        at=int(o.get('at',count+1))-1
        if not 0<=at<=count:raise UserError('Insert position is outside the document.')
        w,h=page_size(o)
        doc.new_page(pno=at,width=w,height=h)
        return save(ctx,doc,stem,'-inserted')
    if op=='replace-pages':
        if len(files)<2:raise UserError('Choose the original PDF first, then the replacement PDF.')
        replacement=open_pdf(files[1],o.get('replacementPassword'))
        at=int(o.get('at',1))-1
        if not selected or len(selected)!=replacement.page_count:raise UserError('The selected page count must match the replacement PDF page count.')
        if min(selected)<at or max(selected)>=at+replacement.page_count:raise UserError('Replacement pages must be consecutive starting at the specified position.')
        doc.delete_pages(at,at+replacement.page_count-1);doc.insert_pdf(replacement,start_at=at)
        return save(ctx,doc,stem,'-replaced')
    if op=='crop-pages':
        margins=[float(o.get(k,10)) for k in ('left','top','right','bottom')]
        if min(margins)<0:raise UserError('Crop margins cannot be negative.')
        for i in selected:
            p=doc[i];r=p.cropbox
            box=fitz.Rect(r.x0+margins[0],r.y0+margins[1],r.x1-margins[2],r.y1-margins[3])
            if box.width<36 or box.height<36:raise UserError('Crop would leave a page smaller than 0.5 inch.')
            p.set_cropbox(box)
        note(ctx,'Cropping changes the visible page box, not the underlying content. Use permanent redaction to remove sensitive content outside the crop.')
        return save(ctx,doc,stem,'-cropped')
    if op=='resize-pages':
        w,h=page_size(o)
        # Reliable layout scaling using a new document and PDF form XObjects.
        doc.bake(annots=True,widgets=True)
        result=fitz.open()
        for i in range(count):
            p=result.new_page(width=w if i in selected else doc[i].rect.width,height=h if i in selected else doc[i].rect.height)
            src=doc[i];scale=min(p.rect.width/src.rect.width,p.rect.height/src.rect.height)
            sw,sh=src.rect.width*scale,src.rect.height*scale
            target=fitz.Rect((p.rect.width-sw)/2,(p.rect.height-sh)/2,(p.rect.width+sw)/2,(p.rect.height+sh)/2)
            p.show_pdf_page(target,doc,i)
        note(ctx,'Resizing scales page content and preserves vectors. Interactive annotations and form fields are flattened into the page appearance.')
        return save(ctx,result,stem,'-resized')
    if op=='extract-images':
        seen=set();n=0
        for i in selected:
            for item in doc[i].get_images(full=True):
                xref=item[0]
                if xref in seen:continue
                seen.add(xref)
                try:data=doc.extract_image(xref)
                except Exception:continue
                n+=1;p=Path(ctx['out'])/f'image-{n:03d}.{data["ext"]}'
                p.write_bytes(data['image']);output(ctx,p,page=i+1,width=data['width'],height=data['height'])
        if not n:raise UserError('No embedded raster images found. Scanned text can be rendered with PDF to images or OCR.')
        return ctx['results'][-n:]
    raise UserError('Unknown page organization operation.')

def page_plan(ctx,files,o):
    """One atomic page plan, retaining blank insertions, duplicates and per-page rotation."""
    source=open_pdf(files[0],o.get('password'));plan=o.get('pages',[])
    if not plan or len(plan)>3000:raise UserError('A page plan must contain 1–3,000 pages.')
    result=fitz.open();base=source[0].rect
    for entry in plan:
        original=int(entry.get('original',0));rotation=int(entry.get('rotation',0))
        if rotation not in (0,90,180,270):raise UserError('Page rotation must be 0, 90, 180 or 270 degrees.')
        if entry.get('blank'):
            p=result.new_page(width=base.width,height=base.height)
        elif 1<=original<=source.page_count:
            result.insert_pdf(source,from_page=original-1,to_page=original-1)
            p=result[-1];p.set_rotation((p.rotation+rotation)%360)
        else:raise UserError('A page in the plan is outside the source document.')
    note(ctx,'Applied your visual page plan, including selected rotations, duplicates and blank pages. The source PDF was not changed.')
    return save(ctx,result,Path(files[0]['name']).stem,'-organized',pages=result.page_count)
