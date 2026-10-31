from pathlib import Path
import math, io
import pymupdf as fitz
from PIL import Image, ImageOps, ImageDraw, ImageFont
from common import open_pdf, color, save, progress, UserError, note

FONT_FILES={
 'Helvetica':'/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
 'Times':'/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf',
 'Courier':'/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf',
 'DejaVu Sans':'/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
}

def apply(ctx, files, o):
    doc=open_pdf(files[0],o.get('password'))
    if not o.get('enabled',True):return save(ctx,doc,Path(files[0]['name']).stem,'-unchanged')
    defaults=o.get('watermark',o);overrides=o.get('overrides',{})
    cache={}
    for i,page in enumerate(doc):
        settings={**defaults,**overrides.get(str(i+1),{})}
        if settings.get('enabled',True):mark(page,settings,ctx,cache)
        progress(ctx,f'Embedding watermark on page {i+1} of {doc.page_count}',100*(i+1)/doc.page_count)
    note(ctx,'Watermarks are embedded in the exported PDF, not just the preview. A watermark does not redact or secure the underlying content.')
    return save(ctx,doc,Path(files[0]['name']).stem,'-watermarked')

def geometry(w,pw,ph,tw,th):
    margin=max(0,min(float(w.get('margin',24)),min(pw,ph)/3))
    align=w.get('align','center');valign=w.get('valign','middle')
    px={'left':margin+tw/2,'center':pw/2,'right':pw-margin-tw/2}.get(align,pw/2)
    py={'top':margin+th/2,'middle':ph/2,'bottom':ph-margin-th/2}.get(valign,ph/2)
    if w.get('position')=='custom':
        if w.get('unit')=='pt':px=float(w.get('x',pw/2));py=float(w.get('y',ph/2))
        else:px=float(w.get('x',50))/100*pw;py=float(w.get('y',50))/100*ph
    elif w.get('position') in ('top','bottom','left','right','center','diagonal'):
        px,py={'top':(pw/2,margin+th/2),'bottom':(pw/2,ph-margin-th/2),'left':(margin+tw/2,ph/2),'right':(pw-margin-tw/2,ph/2),'center':(pw/2,ph/2),'diagonal':(pw/2,ph/2)}[w['position']]
    angle=math.radians(float(w.get('rotation',0)));bw=abs(tw*math.cos(angle))+abs(th*math.sin(angle));bh=abs(tw*math.sin(angle))+abs(th*math.cos(angle))
    px=max(margin+bw/2,min(pw-margin-bw/2,px));py=max(margin+bh/2,min(ph-margin-bh/2,py))
    return px,py,bw,bh

def mark(page,w,ctx,cache):
    typ=w.get('type','text');opacity=max(0,min(1,float(w.get('opacity',.18))))
    rotation=float(w.get('rotation',45 if w.get('position')=='diagonal' else 0));text=str(w.get('text','CONFIDENTIAL'))
    custom=next((f for f in ctx['files'] if f['id']==w.get('fontId')),None)
    fontfile=custom['path'] if custom else FONT_FILES.get(w.get('font','Helvetica'),FONT_FILES['Helvetica'])
    if not Path(fontfile).exists():fontfile=str(__import__('common').unicode_font())
    try:font=fitz.Font(fontfile=fontfile)
    except Exception:raise UserError('Custom font could not be loaded. Use a valid TTF/OTF font.')
    size=max(6,min(200,float(w.get('fontSize',48))));col=color(w.get('color','#7C3AED'),(.48,.23,.93))
    width,height=page.rect.width,page.rect.height;image=None;key=None
    if typ=='image':
        image=next((f for f in ctx['files'] if f['id']==w.get('imageId')),None)
        if not image:raise UserError('Upload or select a watermark image first.')
        try:im=ImageOps.exif_transpose(Image.open(image['path'])).convert('RGBA')
        except Exception:raise UserError('The watermark image could not be read.')
        if im.width*im.height>40000000:raise UserError('Watermark image exceeds 40 megapixels.')
        tw=max(10,min(width*2,float(w.get('imageWidth',220))));th=tw*im.height/im.width;original_tw,original_th=tw,th
        key=(image['id'],round(tw),opacity,rotation)
        if key not in cache:
            im=im.resize((max(1,round(tw)),max(1,round(th))),Image.Resampling.LANCZOS);im.putalpha(im.getchannel('A').point(lambda a:round(a*opacity)))
            if rotation:im=im.rotate(-rotation,expand=True,resample=Image.Resampling.BICUBIC)
            bio=io.BytesIO();im.save(bio,format='PNG');cache[key]=bio.getvalue()
    else:
        if not text.strip():raise UserError('Watermark text cannot be empty.')
        tw=font.text_length(text,fontsize=size);th=size
        shaped=any(ord(c)>0x24f for c in text)
        if shaped:
            scale=4;pf=ImageFont.truetype(fontfile,round(size*scale));box=pf.getbbox(text);tw=(box[2]-box[0])/scale;th=(box[3]-box[1])/scale
            im=Image.new('RGBA',(max(1,round(tw*scale)+12),max(1,round(th*scale)+12)),(0,0,0,0));draw=ImageDraw.Draw(im);draw.text((6-box[0],6-box[1]),text,font=pf,fill=tuple(round(c*255) for c in col)+(round(opacity*255),))
            if rotation:im=im.rotate(-rotation,expand=True,resample=Image.Resampling.BICUBIC)
            bio=io.BytesIO();im.save(bio,format='PNG');key=('shaped',text,fontfile,size,rotation,opacity);cache[key]=bio.getvalue();tw,th=im.width/scale,im.height/scale
    px,py,bw,bh=geometry(w,width,height,original_tw if image else tw,original_th if image else th);under=w.get('layer')=='under'
    fontname='WatermarkFont'
    if not image and not (typ=='text' and any(ord(c)>0x24f for c in text)):page.insert_font(fontname=fontname,fontfile=fontfile)
    def one(cx,cy):
        if image or key:page.insert_image(fitz.Rect(cx-tw/2,cy-th/2,cx+tw/2,cy+th/2),stream=cache[key],overlay=not under,rotate=0)
        else:
            # Baseline offset centers the actual em box. MuPDF rotates clockwise in page coordinates.
            dx=-tw/2;dy=size*.35;angle=math.radians(rotation)
            ox=cx+dx*math.cos(angle)-dy*math.sin(angle);oy=cy+dx*math.sin(angle)+dy*math.cos(angle)
            page.insert_text((ox,oy),text,fontname=fontname,fontsize=size,color=col,fill_opacity=opacity,stroke_opacity=opacity,morph=(fitz.Point(cx,cy),fitz.Matrix(1,0,0,1,0,0).prerotate(rotation)),overlay=not under)
    if w.get('tile'):
        gap=max(0,float(w.get('gap',100)));sx=bw+gap;sy=bh+gap
        cols=min(30,max(1,math.ceil(width/sx)));rows=min(30,max(1,math.ceil(height/sy)))
        for row in range(rows):
            for column in range(cols):one((column+.5)*width/cols,(row+.5)*height/rows)
    else:one(px,py)
