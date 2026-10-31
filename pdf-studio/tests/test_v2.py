"""PDF Studio 2.0 real-file regressions."""
import sys,uuid,shutil,json,io
from pathlib import Path
import pytest,pymupdf as fitz
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'engines'))
from dispatcher import run
from common import UserError

def execute(tmp,op,files=(),options=None):
 out=tmp/str(uuid.uuid4());out.mkdir();records=[]
 for i,f in enumerate(files):
  p=out/f'input-{i}{Path(f).suffix}';shutil.copyfile(f,p);records.append({'id':str(uuid.uuid4()),'name':Path(f).name,'path':str(p)})
 ctx={'operation':op,'files':records,'options':options or {},'out':str(out),'manifest':str(tmp/'manifest.json'),'progress':str(tmp/'progress.json'),'results':[],'notes':[]}
 result=run(ctx);result=[result] if isinstance(result,dict) else result
 assert result
 for r in result:assert Path(r['path']).stat().st_size>0
 return result,ctx

def test_hindi_creation_is_searchable_and_paginated(tmp_path):
 text='नमस्ते दुनिया। हिंदी PDF परीक्षण।\n'*180
 r,_=execute(tmp_path,'create-text',options={'text':text,'pageSize':'a4','fontSize':14,'margin':45})
 with fitz.open(r[0]['path']) as d:
  assert d.page_count>=2;assert 'नमस्ते दुनिया।' in ''.join(p.get_text() for p in d)
  assert d[0].search_for('नमस्ते')

def test_hindi_ocr_and_quality(tmp_path):
 if not shutil.which('tesseract'):pytest.skip('Tesseract missing')
 langs=__import__('ocr').languages()
 if 'hin' not in langs:pytest.skip('Hindi pack missing')
 text='नमस्ते दुनिया हिंदी भाषा परीक्षण'
 image=Image.new('RGB',(1500,260),'white');font=ImageFont.truetype('/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf',64);ImageDraw.Draw(image).text((50,70),text,font=font,fill='black')
 p=tmp_path/'hindi.png';image.save(p)
 r,_=execute(tmp_path,'ocr-text',[p],{'language':'hin','dpi':200});actual=Path(r[0]['path']).read_text()
 assert 'नमस्ते' in actual and 'हिंदी' in actual
 quality=json.loads(Path(next(x['path'] for x in r if x['name'].endswith('.json'))).read_text());assert quality[0]['confidence']>50

def test_selected_text_replacement_removes_original(tmp_path):
 p=tmp_path/'source.pdf';d=fitz.open();page=d.new_page();page.insert_text((60,80),'ORIGINAL TEXT',fontsize=16);d.save(p);d.close()
 r,_=execute(tmp_path,'redact',[p],{'annotations':[{'page':1,'type':'replace','rect':[60/595,64/842,200/595,88/842],'text':'REVISED TEXT','fontSize':14}]})
 with fitz.open(r[0]['path']) as d:text=d[0].get_text();assert 'REVISED TEXT' in text;assert 'ORIGINAL TEXT' not in text

def test_watermark_safe_margin_and_custom_font(tmp_path):
 from watermark import geometry
 x,y,bw,bh=geometry({'position':'custom','unit':'pt','x':0,'y':0,'rotation':45,'margin':24},595,842,200,40)
 assert x-bw/2>=23.9 and y-bh/2>=23.9
 p=tmp_path/'source.pdf';d=fitz.open();d.new_page();d.save(p);d.close()
 font=ROOT/'tests/samples/custom.ttf';shutil.copyfile('/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf',font)
 out=tmp_path/'out';out.mkdir();ctx={'operation':'watermark','files':[{'id':'doc','name':'source.pdf','path':str(p)},{'id':'font','name':'custom.ttf','path':str(font)}],'options':{'watermark':{'text':'गोपनीय','fontId':'font','fontSize':30,'position':'center','rotation':0}},'out':str(out),'results':[],'notes':[],'progress':str(tmp_path/'progress.json')}
 r=__import__('watermark').apply(ctx,ctx['files'],ctx['options']);assert Path(r['path']).exists()

def test_docx_reading_order_and_mixed_orientation(tmp_path):
 p=tmp_path/'mixed.pdf';d=fitz.open();a=d.new_page(width=595,height=842);a.insert_text((50,60),'BEFORE TABLE');a.insert_text((50,300),'AFTER TABLE');a.draw_rect(fitz.Rect(45,100,400,200));a.draw_line((45,150),(400,150));a.draw_line((200,100),(200,200));a.insert_text((55,130),'Cell A');a.insert_text((210,130),'Cell B');b=d.new_page(width=842,height=595);b.insert_text((50,60),'LANDSCAPE');d.save(p);d.close()
 r,_=execute(tmp_path,'pdf-docx',[p]);from docx import Document
 doc=Document(r[0]['path']);body=' '.join(x.text for x in doc.paragraphs);assert body.index('BEFORE TABLE')<body.index('AFTER TABLE');assert len(doc.sections)==2;assert doc.sections[1].page_width>doc.sections[1].page_height

def test_large_multipage_pdf(tmp_path):
 p=tmp_path/'large.pdf';d=fitz.open()
 for i in range(160):
  page=d.new_page();page.insert_text((50,60),f'Large document page {i+1}. '+('Real vector content. '*30),fontsize=11)
 d.save(p,deflate=True);d.close()
 r,_=execute(tmp_path,'pdf-text',[p]);assert 'Large document page 160' in Path(r[0]['path']).read_text()
 r,_=execute(tmp_path,'extract-pages',[p],{'pages':'160,1'});assert fitz.open(r[0]['path']).page_count==2

def test_invalid_ocr_language_is_rejected(tmp_path):
 p=ROOT/'tests/samples/ocr-fragment.png'
 with pytest.raises(UserError):execute(tmp_path,'ocr-text',[p],{'language':'zzz'})

def test_mixed_unicode_search_layer(tmp_path):
 r,_=execute(tmp_path,'create-text',options={'text':'Unicode search: नमस्ते 日本語'})
 with fitz.open(r[0]['path']) as d:
  text=d[0].get_text();assert 'नमस्ते' in text and '日本語' in text

def test_large_unicode_mapping_is_chunked(tmp_path):
 text=''.join(chr(0x4E00+i) for i in range(160))
 r,_=execute(tmp_path,'create-text',options={'text':text})
 with fitz.open(r[0]['path']) as d:assert text in d[0].get_text().replace('\n','')
