"""Read-only environment diagnostics; never prints document contents or credentials."""
import shutil,subprocess,sys,importlib.util
from pathlib import Path
print('PDF Studio — environment check\n')
print('Python:',sys.version.split()[0])
for command in ['node','npm','libreoffice','tesseract','qpdf','gs','chromium']:
    p=shutil.which(command);print(('READY' if p else 'MISSING'),command,p or '')
for name in ['pymupdf','pypdf','PIL','docx','pptx','openpyxl','pytesseract','pyhanko','markdown','bs4']:
    print(('READY' if importlib.util.find_spec(name) else 'MISSING'),name)
try:
    import pytesseract
    print('OCR languages:',', '.join(pytesseract.get_languages()))
except Exception as e:print('OCR language check:',e)
root=Path(__file__).resolve().parents[1]
print('Frontend dependencies:', 'READY' if (root/'node_modules/vite').exists() else 'MISSING — run npm ci')
print('\nInstall missing dependencies using README.md, then refresh Settings → Local processing engines.')
