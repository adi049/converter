from pathlib import Path
import subprocess, shutil
import pymupdf as fitz
from common import open_pdf, save, note, UserError, progress

def apply(ctx,files,o):
    doc=open_pdf(files[0],o.get('password'));source=Path(files[0]['path']).stat().st_size
    presets={'low':{'dpi':220,'quality':88},'medium':{'dpi':150,'quality':75},'high':{'dpi':96,'quality':50}}
    settings=presets.get(o.get('level','medium'),presets['medium'])
    dpi=int(o.get('dpi',settings['dpi']));quality=int(o.get('quality',settings['quality']))
    if not 36<=dpi<=600 or not 10<=quality<=100:raise UserError('DPI must be 36–600 and quality 10–100.')
    if o.get('confirmed') is not True:raise UserError('Review and confirm the compression settings before exporting.')
    progress(ctx,'Rewriting embedded images at the selected resolution')
    if o.get('recompressImages',True):
        try:doc.rewrite_images(dpi_threshold=dpi+20,dpi_target=dpi,quality=quality,lossy=True,lossless=True,bitonal=False,set_to_gray=bool(o.get('grayscale',False)))
        except Exception as e:note(ctx,'Image recompression was unavailable for some resources: '+str(e)[:160])
    if o.get('grayscale',False):
        # Explicitly chosen; color images are transformed before compression.
        note(ctx,'Grayscale was explicitly enabled for recompressed images.')
    if o.get('removeMetadata',True):
        doc.set_metadata({});doc.del_xml_metadata()
    if o.get('subsetFonts',True):
        try:doc.subset_fonts()
        except Exception:note(ctx,'Font subsetting was not possible for all embedded fonts.')
    stem=Path(files[0]['name']).stem
    result=save(ctx,doc,stem,'-compressed',originalSize=source,settings={'dpi':dpi,'quality':quality,'removeMetadata':o.get('removeMetadata',True)})
    doc.close()
    if o.get('webOptimize',True) and shutil.which('qpdf'):
        p=Path(result['path']);tmp=p.with_suffix('.web.pdf')
        run=subprocess.run(['qpdf','--linearize',str(p),str(tmp)],capture_output=True,text=True,timeout=120)
        if run.returncode in (0,3):tmp.replace(p)
        else:note(ctx,'PDF structure was optimized, but web linearization could not be applied.')
    result['size']=Path(result['path']).stat().st_size;result['originalSize']=source
    result['reduction']=round((1-result['size']/source)*100,1)
    if result['size']>=source:note(ctx,'This PDF was already well optimized. The output is not smaller; the original remains available. Try a lower DPI or keep the original.')
    else:note(ctx,f'Actual size reduction: {result["reduction"]}%. Image recompression is lossy at {dpi} DPI / quality {quality}. Vector text remains vector text.')
    return result
