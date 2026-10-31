"""Real-file integration tests. No mocked processing results."""
import sys,json,subprocess,uuid,io,shutil,zipfile
from pathlib import Path
import pytest
import pymupdf as fitz
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];SAMPLES=ROOT/'tests'/'samples'
sys.path.insert(0,str(ROOT/'engines'))
from dispatcher import run
from common import UserError,parse_pages

@pytest.fixture(autouse=True)
def samples():
    if not (SAMPLES/'report.pdf').exists():subprocess.run([sys.executable,str(ROOT/'scripts/make_samples.py')],check=True)

def execute(tmp_path,operation,names=(),options=None):
    out=tmp_path/str(uuid.uuid4());out.mkdir();files=[]
    for name in names:
        p=out/('input-'+str(len(files))+Path(name).suffix);shutil.copyfile(SAMPLES/name,p)
        files.append({'id':str(uuid.uuid4()),'name':name,'path':str(p)})
    ctx={'operation':operation,'files':files,'options':options or {},'out':str(out),'manifest':str(tmp_path/'manifest.json'),'progress':str(tmp_path/'progress.json'),'results':[],'notes':[]}
    result=run(ctx)
    if isinstance(result,dict):result=[result]
    assert result
    for r in result:assert Path(r['path']).exists() and Path(r['path']).stat().st_size>0
    return result,ctx

def test_page_parser():
    assert parse_pages('1-3,5',6)==[0,1,2,4]
    assert parse_pages('odd',6)==[0,2,4]
    with pytest.raises(UserError):parse_pages('0-2',3)
    with pytest.raises(UserError):parse_pages('1,1',3)

def test_text_and_blank(tmp_path):
    r,_=execute(tmp_path,'create-text',options={'text':'Hello PDF Studio.\n'+('Real text content. '*600),'pageSize':'letter','fontSize':12})
    with fitz.open(r[0]['path']) as d:assert 'Hello PDF Studio.' in ''.join(p.get_text() for p in d);assert d.page_count>=2
    r,_=execute(tmp_path,'create-blank',options={'pageCount':3,'pageSize':'custom','width':210,'height':297,'layout':'grid'})
    with fitz.open(r[0]['path']) as d:assert d.page_count==3;assert abs(d[0].rect.width-595.28)<1

def test_images_to_pdf(tmp_path):
    r,_=execute(tmp_path,'images-pdf',['landscape.jpg','landscape.png'],{'pageSize':'a4'})
    with fitz.open(r[0]['path']) as d:assert d.page_count==2;assert all(len(p.get_images())==1 for p in d)

@pytest.mark.parametrize('name',['proposal.docx','presentation.pptx','budget.xlsx','letter.rtf','notes.txt','budget.csv'])
def test_office_to_pdf(tmp_path,name):
    if not shutil.which('libreoffice'):pytest.skip('LibreOffice not installed')
    r,_=execute(tmp_path,'office-pdf',[name]);d=fitz.open(r[0]['path']);assert d.page_count>=1;assert ''.join(p.get_text() for p in d).strip();d.close()

@pytest.mark.parametrize('op,ext',[('pdf-jpg','.jpg'),('pdf-png','.png'),('pdf-text','.txt'),('pdf-html','.html'),('pdf-markdown','.md'),('pdf-docx','.docx'),('pdf-xlsx','.xlsx'),('pdf-pptx','.pptx')])
def test_pdf_conversions(tmp_path,op,ext):
    r,_=execute(tmp_path,op,['report.pdf'],{'pages':'1-2','dpi':100});assert all(x['name'].endswith(ext) for x in r)
    if op in ('pdf-jpg','pdf-png'):assert len(r)==2;assert Image.open(r[0]['path']).width>500
    elif op=='pdf-text':assert 'ORIGINAL TEXT' in Path(r[0]['path']).read_text()
    elif op=='pdf-html':assert 'data:' in Path(r[0]['path']).read_text()
    elif op=='pdf-docx':
        from docx import Document
        d=Document(r[0]['path']);assert 'ORIGINAL TEXT' in '\n'.join(p.text for p in d.paragraphs);assert len(d.tables)==2
    elif op=='pdf-xlsx':
        from openpyxl import load_workbook
        wb=load_workbook(r[0]['path']);assert len(wb.sheetnames)==2;assert wb['Page 1']['A1'].value=='Item'
    elif op=='pdf-pptx':
        from pptx import Presentation
        assert len(Presentation(r[0]['path']).slides)==2

@pytest.mark.parametrize('kind',['text','image'])
def test_embedded_watermark_and_overrides(tmp_path,kind):
    opts={'watermark':{'type':kind,'text':'MANAGED BY LUNA © 2026','fontSize':32,'opacity':.25,'position':'diagonal','imageId':None},'overrides':{'2':{'enabled':False},'3':{'text':'DRAFT PAGE THREE'}}}
    if kind=='image':
        logo={'id':'logo','name':'landscape.png','path':str(SAMPLES/'landscape.png')}
        opts['watermark']['imageId']=logo['id'];opts['watermark']['imageWidth']=180
        r,ctx=execute(tmp_path,'create-blank',options={'pageCount':3});ctx['files']=[{'id':'doc','name':'report.pdf','path':str(SAMPLES/'report.pdf')},logo];ctx['out']=str(tmp_path);ctx['results']=[]
        from watermark import apply
        result=apply(ctx,ctx['files'],opts);result=[result]
    else:result,_=execute(tmp_path,'watermark',['report.pdf'],opts)
    d=fitz.open(result[0]['path'])
    if kind=='text':assert 'MANAGED BY LUNA' in d[0].get_text();assert 'DRAFT PAGE THREE' in d[2].get_text();assert 'MANAGED BY LUNA' not in d[1].get_text()
    else:assert len(d[0].get_images())>=2
    d.close()

def test_tiled_watermark(tmp_path):
    r,_=execute(tmp_path,'watermark',['report.pdf'],{'watermark':{'text':'DRAFT','tile':True,'fontSize':16,'gap':40,'position':'center'}})
    d=fitz.open(r[0]['path']);assert d[0].get_text().count('DRAFT')>8;d.close()

@pytest.mark.parametrize('op,options,expected',[
 ('merge',{},6),('extract-pages',{'pages':'1,3'},2),('delete-pages',{'pages':'2'},2),('reverse',{},3),('duplicate-pages',{'pages':'2'},4),('rotate-pages',{'pages':'1','angle':90},3),('reorder-pages',{'order':[3,1,2]},3),('insert-blank',{'at':2},4),('resize-pages',{'pageSize':'letter'},3),('crop-pages',{'left':10,'right':10,'top':10,'bottom':10},3)])
def test_organization(tmp_path,op,options,expected):
    names=['report.pdf','report.pdf'] if op=='merge' else ['report.pdf']
    r,_=execute(tmp_path,op,names,options);d=fitz.open(r[0]['path']);assert d.page_count==expected
    if op=='reverse':assert 'Next Steps' in d[0].get_text()
    if op=='rotate-pages':assert d[0].rotation==90
    if op=='merge':assert len(d.get_toc())==2
    d.close()

def test_split_replace_and_page_plan(tmp_path):
    r,_=execute(tmp_path,'split',['report.pdf'],{'every':2});assert len(r)==2
    single=fitz.open();single.new_page();single[0].insert_text((72,72),'Replacement page');single.save(SAMPLES/'single.pdf');single.close()
    r,_=execute(tmp_path,'replace-pages',['report.pdf','single.pdf'],{'pages':'1','at':1});assert fitz.open(r[0]['path']).page_count==3
    r,_=execute(tmp_path,'page-plan',['report.pdf'],{'pages':[{'original':3,'rotation':90},{'original':1,'rotation':0},{'original':1,'rotation':180},{'blank':True,'original':0,'rotation':0}]})
    d=fitz.open(r[0]['path']);assert d.page_count==4;assert d[0].rotation==90;assert not d[3].get_text().strip();d.close()

def test_extract_images(tmp_path):
    r,_=execute(tmp_path,'extract-images',['report.pdf']);assert len(r)==1;assert Image.open(r[0]['path']).size==(640,360)

def test_annotations_and_permanent_redaction(tmp_path):
    marks=[{'page':1,'type':'text','rect':[.1,.75,.6,.8],'text':'Added locally','color':'#7657dc','fontSize':16},{'page':1,'type':'pen','points':[[.1,.8],[.2,.85],[.3,.8]],'color':'#ff0000','width':2},{'page':1,'type':'note','rect':[.9,.1,.94,.14],'text':'Review this section'},{'page':1,'type':'redact','rect':[.07,.52,.7,.56]}]
    r,_=execute(tmp_path,'redact',['report.pdf'],{'annotations':marks});d=fitz.open(r[0]['path']);text=d[0].get_text();assert 'Added locally' in text;assert 'SECRET-12345' not in text;assert len(list(d[0].annots()))>=1;d.close()

def test_find_replace_numbers_metadata_bookmarks(tmp_path):
    r,_=execute(tmp_path,'find-replace',['report.pdf'],{'find':'ORIGINAL TEXT','replacement':'REVISED TEXT'})
    d=fitz.open(r[0]['path']);assert 'REVISED TEXT' in d[0].get_text();assert 'ORIGINAL TEXT' not in d[0].get_text();d.close()
    for op,o in [('page-numbers',{'format':'Page {n} of {total}','start':5}),('bates',{'prefix':'LGL-','digits':6}),('headers-footers',{'header':'Report','footer':'Page {n}'})]:
        r,_=execute(tmp_path,op,['report.pdf'],o);assert fitz.open(r[0]['path']).page_count==3
    r,_=execute(tmp_path,'metadata',['report.pdf']);assert r[0]['metadata']['pages']==3
    r,_=execute(tmp_path,'edit-metadata',['report.pdf'],{'metadata':{'title':'Edited title'}});assert fitz.open(r[0]['path']).metadata['title']=='Edited title'
    r,_=execute(tmp_path,'bookmarks',['report.pdf'],{'bookmarks':[[1,'Start',1],[2,'Finance',2]]});assert len(fitz.open(r[0]['path']).get_toc())==2

def test_compression_reports_real_size(tmp_path):
    r,_=execute(tmp_path,'compress',['report.pdf'],{'confirmed':True,'level':'high','dpi':96,'quality':50});assert r[0]['originalSize']>0;assert r[0]['size']>0;assert 'reduction' in r[0]
    with pytest.raises(UserError):execute(tmp_path,'compress',['report.pdf'],{'confirmed':False})

def test_aes_encryption_permissions_and_authorized_decrypt(tmp_path):
    r,_=execute(tmp_path,'protect',['report.pdf'],{'userPassword':'open-secret-123','ownerPassword':'owner-secret-123','allowPrint':False,'allowCopy':False,'allowEdit':False})
    path=Path(r[0]['path']);d=fitz.open(path);assert d.needs_pass;assert not d.authenticate('wrong');assert d.authenticate('open-secret-123');assert not d.permissions&fitz.PDF_PERM_PRINT;d.close()
    q= subprocess.run(['qpdf','--password=open-secret-123','--check',str(path)],capture_output=True,text=True);assert q.returncode in (0,3)
    # Run authorized decrypt against the protected file.
    from security import apply
    out=tmp_path/'decrypt';out.mkdir();ctx={'operation':'unlock','out':str(out),'results':[],'notes':[],'progress':str(tmp_path/'p.json'),'files':[{'id':'x','name':'protected.pdf','path':str(path),'encrypted':True}]}
    res=apply(ctx,ctx['files'],{'password':'open-secret-123'});assert not fitz.open(res['path']).needs_pass
    with pytest.raises(UserError):apply(ctx,ctx['files'],{'password':'incorrect'})

def test_ocr_and_searchable_pdf(tmp_path):
    if not shutil.which('tesseract'):pytest.skip('Tesseract not installed')
    r,_=execute(tmp_path,'ocr-text',['ocr-fragment.png'],{'language':'eng'});assert 'INV-2026-001' in Path(r[0]['path']).read_text()
    r,_=execute(tmp_path,'ocr-pdf',['scanned.pdf'],{'language':'eng','dpi':150});d=fitz.open(r[0]['path']);assert 'PROJECT APPROVAL' in d[0].get_text();assert d[0].search_for('INV-2026-001');d.close()
    r,_=execute(tmp_path,'ocr-tables',['scanned.pdf'],{'language':'eng'});assert r[0]['tables']>=1

def test_comparison(tmp_path):
    r,_=execute(tmp_path,'compare',['report.pdf','report.pdf'],{'visual':True});assert any(f['name'].endswith('.html') for f in r);assert any(f['name'].endswith('.png') for f in r);assert 'No extractable text differences' in next(Path(f['path']).read_text() for f in r if f['name'].endswith('.txt'))

def test_csv_xlsx_and_markdown_docx(tmp_path):
    r,_=execute(tmp_path,'csv-xlsx',['budget.csv']);from openpyxl import load_workbook
    wb=load_workbook(r[0]['path']);assert wb.active['A2'].value=='Design';assert wb.active['B2'].value=='10'
    r,_=execute(tmp_path,'markdown-docx',['notes.md']);from docx import Document
    d=Document(r[0]['path']);assert len(d.tables)==1;assert any(p.text=='Project notes' for p in d.paragraphs)

@pytest.mark.skipif(not shutil.which('openssl'),reason='openssl needed to create test certificate')
def test_real_cryptographic_signature_and_tamper_detection(tmp_path):
    key=tmp_path/'key.pem';cert=tmp_path/'cert.pem';p12=tmp_path/'signer.p12'
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(key),'-out',str(cert),'-days','2','-subj','/CN=PDF Studio Local Test'],check=True,capture_output=True)
    subprocess.run(['openssl','pkcs12','-export','-out',str(p12),'-inkey',str(key),'-in',str(cert),'-passout','pass:test-cert-password'],check=True,capture_output=True)
    shutil.copyfile(p12,SAMPLES/'test-signer.p12')
    try:r,_=execute(tmp_path,'sign',['report.pdf','test-signer.p12'],{'certificatePassword':'test-cert-password'})
    finally:(SAMPLES/'test-signer.p12').unlink(missing_ok=True)
    # Add certificate as a real input record.
    from security import verify
    ctx={'files':[{'name':'signed.pdf','path':r[0]['path']}],'out':str(tmp_path),'results':[],'notes':[]}
    report=verify(ctx,ctx['files'],{});sig=report['signatures'][0];assert sig['intact'] and sig['validSyntax'];assert not sig['trusted']
    tampered=tmp_path/'tampered.pdf';shutil.copyfile(r[0]['path'],tampered);d=fitz.open(tampered);d[0].insert_text((30,700),'TAMPERED');d.saveIncr();d.close()
    ctx['files'][0]['path']=str(tampered);report=verify(ctx,ctx['files'],{});assert not report['signatures'][0]['unmodified'];assert not report['signatures'][0]['permittedModifications']

@pytest.mark.skipif(not shutil.which('gs'),reason='Ghostscript not installed')
def test_pdfa_export_is_real_pdf(tmp_path):
    r,_=execute(tmp_path,'pdfa',['report.pdf']);d=fitz.open(r[0]['path']);assert d.page_count==3;assert 'not certified' in r[0]['standard'];d.close()


def test_grayscale_compression_changes_real_pixels(tmp_path):
    r,_=execute(tmp_path,'compress',['report.pdf'],{'confirmed':True,'grayscale':True,'dpi':100,'quality':60})
    d=fitz.open(r[0]['path']);images=d[0].get_images(full=True);assert images
    pix=fitz.Pixmap(d,images[0][0])
    if pix.colorspace and pix.n>=3:
        samples=pix.samples;assert all(samples[i]==samples[i+1]==samples[i+2] for i in range(0,len(samples)-pix.n,pix.n*17))
    d.close()

def test_comparison_html_is_self_contained(tmp_path):
    r,_=execute(tmp_path,'compare',['report.pdf','report.pdf'],{'visual':True})
    text=Path(next(x['path'] for x in r if x['name'].endswith('.html'))).read_text()
    assert 'data:image/png;base64,' in text and 'src="visual-page-' not in text

def test_markdown_to_editable_word(tmp_path):
    from docx import Document
    r,_=execute(tmp_path,'markdown-docx',['notes.md'])
    d=Document(r[0]['path']);assert d.paragraphs
    assert any(p.text for p in d.paragraphs)
    assert r[0]['name'].endswith('.docx')

def test_flatten_bakes_form_appearance(tmp_path):
    source=tmp_path/'form-source.pdf';d=fitz.open();p=d.new_page()
    p.insert_text((72,72),'Form field:')
    w=fitz.Widget();w.field_name='FullName';w.field_type=fitz.PDF_WIDGET_TYPE_TEXT;w.field_value='Local Studio';w.rect=fitz.Rect(72,90,280,120);p.add_widget(w)
    d.save(source);d.close()
    import shutil as sh
    target=SAMPLES/'form.pdf';sh.copyfile(source,target)
    r,_=execute(tmp_path,'flatten',['form.pdf']);d=fitz.open(r[0]['path'])
    assert not list(d[0].widgets());assert 'Local Studio' in d[0].get_text();d.close()

def test_csv_formula_is_imported_as_text(tmp_path):
    from openpyxl import load_workbook
    p=SAMPLES/'formula.csv';p.write_text('Name,Value\n=HYPERLINK("https://example.com"),001\n')
    r,_=execute(tmp_path,'csv-xlsx',['formula.csv']);ws=load_workbook(r[0]['path']).active
    assert ws['A2'].data_type=='s';assert ws['B2'].value=='001'

def test_hindi_creation_is_searchable_and_paginated(tmp_path):
    text='नमस्ते दुनिया। हिंदी PDF परीक्षण। '
    r,_=execute(tmp_path,'create-text',options={'text':(text+'\n')*80,'fontSize':14})
    with fitz.open(r[0]['path']) as d:
        assert len(d)>1
        assert 'नमस्ते दुनिया। हिंदी PDF परीक्षण।' in ''.join(p.get_text() for p in d)
        assert d[0].search_for('हिंदी')

def test_hindi_ocr_and_custom_watermark_font(tmp_path):
    from PIL import Image,ImageDraw,ImageFont
    root=tmp_path/'assets';root.mkdir();image=Image.new('RGB',(1200,240),'white');draw=ImageDraw.Draw(image)
    font=ImageFont.truetype('/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf',64)
    draw.text((20,50),'नमस्ते दुनिया हिंदी परीक्षण',font=font,fill='black');image.save(SAMPLES/'hindi.png')
    r,_=execute(tmp_path,'ocr-text',['hindi.png'],{'language':'hin+eng'})
    assert 'नमस्ते' in Path(next(x['path'] for x in r if x['name'].endswith('.txt'))).read_text()
    font_path=SAMPLES/'watermark-font.ttf'
    if not font_path.exists():
        import shutil;shutil.copyfile('/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf',font_path)
    r,_=execute(tmp_path,'watermark',['report.pdf','watermark-font.ttf'],{'text':'CONFIDENTIAL','fontFileId':None,'fontSize':30,'rotation':33,'x':50,'y':50,'position':'custom','units':'percent'})
    with fitz.open(r[0]['path']) as d:assert 'CONFIDENTIAL' in d[0].get_text()
