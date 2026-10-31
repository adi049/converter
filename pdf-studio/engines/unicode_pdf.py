"""Preserve Unicode search semantics without changing Chromium's visual shaping.

Chromium supplies the visible, correctly shaped page. Complex-script glyphs are
outlined locally; an invisible, zero-width Unicode mapping retains the original
text. No OCR guess or third-party service is involved in this text-only path.
"""
from pathlib import Path
import subprocess
import pymupdf


def searchable_copy(source, output, original_text=None):
    with pymupdf.open(source) as doc:
        lines = [[(line['bbox'], ''.join(s['text'] for s in line.get('spans', [])), max((s['size'] for s in line.get('spans', [])), default=12)) for block in page.get_text('dict')['blocks'] for line in block.get('lines', [])] for page in doc]
    if original_text:
        # Chromium may extract a non-BMP character as U+FFFD even when its visual font supports it.
        astral=iter(c for c in original_text if ord(c)>0xFFFF)
        for page_lines in lines:
            for j,(rect,text,size) in enumerate(page_lines):
                if '\ufffd' in text:
                    rebuilt=''
                    for c in text:rebuilt+=next(astral,c) if c=='\ufffd' else c
                    page_lines[j]=(rect,rebuilt,size)
    subprocess.run(['gs', '-q', '-dNOPAUSE', '-dBATCH', '-sDEVICE=pdfwrite', '-dNoOutputFonts', '-sOutputFile=' + str(output), str(source)], check=True, capture_output=True, timeout=180)
    with pymupdf.open(output) as doc:
        for page, page_lines in zip(doc, lines):
            chars = sorted(set(''.join(t for _, t, _ in page_lines)))
            if not chars:
                continue
            cmap = '/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n/CMapName /Unicode def\n/CMapType 2 def\n1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n'
            # Bfchar ranges are limited to 100 entries by the PDF specification.
            for start in range(0, len(chars), 100):
                group = chars[start:start+100]
                cmap += f'{len(group)} beginbfchar\n' + ''.join(f'<{i+1:04X}> <{c.encode("utf-16-be").hex().upper()}>\n' for i,c in enumerate(group,start=start)) + 'endbfchar\n'
            cmap += 'endcmap\nCMapName currentdict /CMap defineresource pop\nend end'
            cm = doc.get_new_xref(); doc.update_object(cm, '<<>>'); doc.update_stream(cm, cmap.encode())
            fd = doc.get_new_xref(); doc.update_object(fd, '<< /Type /FontDescriptor /FontName /UnicodeSearch /Flags 4 /FontBBox [0 0 0 0] /ItalicAngle 0 /Ascent 0 /Descent 0 /CapHeight 0 /StemV 0 >>')
            cid = doc.get_new_xref(); doc.update_object(cid, f'<< /Type /Font /Subtype /CIDFontType0 /BaseFont /UnicodeSearch /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> /FontDescriptor {fd} 0 R /DW 0 >>')
            font = doc.get_new_xref(); doc.update_object(font, f'<< /Type /Font /Subtype /Type0 /BaseFont /UnicodeSearch /Encoding /Identity-H /DescendantFonts [{cid} 0 R] /ToUnicode {cm} 0 R >>')
            doc.xref_set_key(page.xref, 'Resources/Font/UnicodeSearch', f'{font} 0 R')
            stream = b''
            for rect, text, size in page_lines:
                if not text.strip(): continue
                mapping={c:i+1 for i,c in enumerate(chars)};encoded=''.join(f'{mapping[c]:04X}' for c in text)
                stream += f'\nBT /UnicodeSearch {max(1,size):.3f} Tf 3 Tr {rect[0]:.3f} {page.rect.height-rect[3]+size*.2:.3f} Td <{encoded}> Tj ET\n'.encode()
            contents = page.get_contents(); doc.update_stream(contents[0], doc.xref_stream(contents[0]) + stream)
        doc.saveIncr()
