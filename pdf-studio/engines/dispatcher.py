"""Local document worker. Invoke: python engines/dispatcher.py request.json.
Request paths are supplied by the trusted local API. Outputs are recorded in result.json.
"""
from pathlib import Path
import json, sys, traceback
from common import UserError, progress, note, output, safe_name


def run(ctx):
    op=ctx['operation'];files=ctx.get('files',[]);o=ctx.get('options',{})
    import creation, conversion, watermark, organize, editing, optimization, security, ocr, advanced
    needs_file={'create-text','create-blank','create-markdown-text','create-html-rendered','create-url'}
    if op not in needs_file and not files:raise UserError('Choose a document first.')
    if op in ('create-text',):return creation.create_text(ctx,files,o)
    if op=='create-blank':return creation.blank(ctx,files,o)
    if op=='page-plan':return organize.page_plan(ctx,files,o)
    if op=='markdown-docx':return advanced.markdown_docx(ctx,files,o)
    if op=='images-pdf':return creation.images(ctx,files,o)
    if op=='office-pdf':return creation.office_to_pdf(ctx,files,o)
    if op.startswith('pdf-') and op in ('pdf-jpg','pdf-png','pdf-images','pdf-text','pdf-html','pdf-markdown','pdf-docx','pdf-xlsx','pdf-pptx'):return conversion.apply(ctx,files,o)
    if op=='watermark':return watermark.apply(ctx,files,o)
    if op in ('merge','split','extract-pages','delete-pages','reverse','duplicate-pages','rotate-pages','reorder-pages','insert-blank','replace-pages','crop-pages','resize-pages','extract-images'):return organize.apply(ctx,files,o)
    if op in ('annotate','redact','find-replace','page-numbers','bates','headers-footers'):return editing.apply(ctx,files,o)
    if op=='compress':return optimization.apply(ctx,files,o)
    if op in ('protect','encrypt','unlock','decrypt','sign','verify-signatures','pdfa'):return security.apply(ctx,files,o)
    if op in ('ocr-text','ocr-docx','ocr-pdf'):return ocr.apply(ctx,files,o)
    if op=='ocr-tables':return ocr.tables(ctx,files,o)
    return advanced.apply(ctx,files,o)

def main():
    request=Path(sys.argv[1]);ctx=json.loads(request.read_text())
    Path(ctx['out']).mkdir(parents=True,exist_ok=True);ctx['results']=[];ctx['notes']=[]
    try:
        progress(ctx,'Processing locally',0)
        result=run(ctx)
        if isinstance(result,dict):result=[result]
        if not result:result=ctx['results']
        # Only records created by common.output are exposed by the API.
        by_path={str(r['path']):r for r in ctx['results']}
        ctx['results']=[by_path[str(r['path'])] for r in result if str(r['path']) in by_path]
        manifest={'ok':True,'results':ctx['results'],'notes':ctx['notes']}
    except UserError as e:manifest={'ok':False,'error':str(e)}
    except Exception as e:
        # Never leak document contents, passwords or keys into logs.
        sys.stderr.write(f'Engine error ({type(e).__name__}): {str(e)[:500]}\n')
        manifest={'ok':False,'error':f'{type(e).__name__}: {str(e)[:500]}'}
    Path(ctx['manifest']).write_text(json.dumps(manifest,ensure_ascii=False,default=str))
    progress(ctx,'Complete' if manifest['ok'] else 'Processing failed',100 if manifest['ok'] else None)
    return 0 if manifest['ok'] else 1

if __name__=='__main__':sys.exit(main())
