"""Generate reproducible, real documents for integration and manual smoke tests."""
from pathlib import Path
import sys, csv, json
import pymupdf as fitz
from PIL import Image,ImageDraw,ImageFont
from docx import Document
from docx.shared import Inches
from pptx import Presentation
from pptx.util import Inches as SlideInches
from openpyxl import Workbook
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'tests'/'samples';OUT.mkdir(parents=True,exist_ok=True)
font_path='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
font=ImageFont.truetype(font_path,24)
# A vector PDF with multiple pages, an embedded image, a real table and a heading outline.
doc=fitz.open()
for i in range(3):
    page=doc.new_page(width=595,height=842)
    page.insert_text((50,65),['Quarterly Project Report','Financial Summary','Next Steps'][i],fontsize=24,fontname='helv')
    page.insert_textbox((50,100,545,190),'PDF Studio integration fixture. This document contains real extractable text, a photograph, a table and multiple pages. CONFIDENTIAL draft for testing only.',fontsize=12,fontname='helv',lineheight=1.5)
    rows=[['Item','Quantity','Amount'],['Design services','10','1000.00'],['Development','20','2400.00'],['Total','30','3400.00']]
    for r,row in enumerate(rows):
        for c,value in enumerate(row):
            rect=fitz.Rect(50+c*165,220+r*35,215+c*165,255+r*35)
            page.draw_rect(rect,color=(.65,.65,.7),fill=(.92,.9,1) if r==0 else None,width=.5)
            page.insert_text((rect.x0+8,rect.y0+22),value,fontsize=11)
    page.insert_text((50,410),'Find this exact phrase: ORIGINAL TEXT.',fontsize=12)
    page.insert_text((50,450),'Private identifier: SECRET-12345',fontsize=12)
    page.insert_text((50,800),f'Personal document toolkit | Page {i+1}',fontsize=9,color=(.4,.4,.4))
image=Image.new('RGB',(640,360),'#ede7fa');draw=ImageDraw.Draw(image)
draw.rounded_rectangle((30,30,610,330),radius=25,fill='#d7c5f1')
draw.ellipse((65,65,225,225),fill='#9572cd');draw.polygon([(250,280),(410,90),(580,280)],fill='#7657a8')
draw.text((65,295),'A locally generated sample',font=ImageFont.truetype(font_path,19),fill='#4d365e')
image.save(OUT/'landscape.png');image.save(OUT/'landscape.jpg',quality=92);image.save(OUT/'landscape.webp',quality=88)
doc[0].insert_image(fitz.Rect(310,480,545,612),filename=str(OUT/'landscape.png'))
doc.set_toc([[1,'Quarterly Project Report',1],[1,'Financial Summary',2],[1,'Next Steps',3]])
doc.set_metadata({'title':'Quarterly Project Report','author':'PDF Studio Test Suite','subject':'Real document integration fixture','keywords':'pdf, studio, test'})
doc.save(OUT/'report.pdf',garbage=4,deflate=True);doc.close()
# A genuinely scanned PDF: no text objects, just a high-resolution image.
scan=Image.new('RGB',(1240,1754),'white');d=ImageDraw.Draw(scan)
big=ImageFont.truetype(font_path,45);medium=ImageFont.truetype(font_path,29)
d.text((100,120),'PROJECT APPROVAL',font=big,fill='black')
for j,line in enumerate(['Invoice number: INV-2026-001','Customer: Alex Morgan','Date: 31 October 2026','Service: Document design','Quantity: 10 hours','Rate: 100.00 per hour','Total amount: 1000.00','Please review this scanned document.']):d.text((100,250+j*80),line,font=medium,fill='black')
for y in range(960,1281,80):d.line((100,y,1100,y),fill='black',width=2)
for x in (100,600,850,1100):d.line((x,960,x,1280),fill='black',width=2)
for r,values in enumerate([['Item','Qty','Total'],['Design','10','1000.00'],['Review','2','200.00'],['Grand total','12','1200.00']]):
    for c,value in enumerate(values):d.text(([115,615,865][c],982+r*80),value,font=ImageFont.truetype(font_path,24),fill='black')
scan.save(OUT/'scanned.png');scan.save(OUT/'scanned.pdf',resolution=150)
scan.crop((70,235,1110,470)).save(OUT/'ocr-fragment.png')
# Office documents with actual content.
word=Document();word.add_heading('Project Proposal',0);word.add_paragraph('Prepared for Alex Morgan by the PDF Studio test suite.')
word.add_heading('Scope of work',level=1);word.add_paragraph('Create a reliable local document workflow with professional formatting. This paragraph tests word wrapping, pagination and real Office conversion.')
word.add_picture(str(OUT/'landscape.png'),width=Inches(4.5));t=word.add_table(rows=3,cols=3);t.style='Table Grid'
for r,row in enumerate([['Phase','Owner','Budget'],['Discovery','Alex','1000'],['Delivery','Team','2400']]):
    for c,v in enumerate(row):t.cell(r,c).text=v
word.add_heading('Approval',level=1);word.add_paragraph('Please review the terms before signing.');word.save(OUT/'proposal.docx')
prs=Presentation();slide=prs.slides.add_slide(prs.slide_layouts[0]);slide.shapes.title.text='A better way forward';slide.placeholders[1].text='PDF Studio · Real PPTX conversion test'
slide=prs.slides.add_slide(prs.slide_layouts[5]);slide.shapes.title.text='Project milestones';slide.shapes.add_picture(str(OUT/'landscape.png'),SlideInches(1),SlideInches(1.7),width=SlideInches(7));prs.save(OUT/'presentation.pptx')
wb=Workbook();ws=wb.active;ws.title='Budget';rows=[['Item','Quantity','Rate','Amount'],['Design',10,100,1000],['Development',20,120,2400],['Total',30,'',3400]]
for row in rows:ws.append(row)
ws.column_dimensions['A'].width=25;ws.freeze_panes='A2';wb.save(OUT/'budget.xlsx')
with open(OUT/'budget.csv','w',newline='') as f:csv.writer(f).writerows(rows)
(OUT/'notes.md').write_text('# Project notes\n\nA real **Markdown** document with a list and table.\n\n## Action items\n\n- Review the proposal\n- Approve the budget\n\n| Name | Status |\n| --- | --- |\n| Design | Ready |\n| Development | Planned |\n\n> Private, local-first processing.\n')
(OUT/'notes.txt').write_text('PDF Studio\n\nA plain text document with real paragraphs.\nCreated locally for integration testing.\n')
(OUT/'page.html').write_text('<!doctype html><html><head><meta charset="utf-8"><title>Local HTML fixture</title></head><body><h1>Good ideas deserve great documents.</h1><p>This HTML is rendered with local Chromium.</p><table><tr><th>Feature</th><th>Status</th></tr><tr><td>Private processing</td><td>Ready</td></tr></table></body></html>')
(OUT/'letter.rtf').write_text('{\\rtf1\\ansi\\deff0{\\fonttbl{\\f0 Arial;}}\\f0\\fs24 \\b Professional Letter\\b0\\par\\par Dear Alex,\\par This real RTF document tests local Office conversion.\\par\\par Kind regards,\\par PDF Studio\\par}')
print(f'Real sample documents generated in {OUT}')
