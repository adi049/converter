# Third-party components

PDF Studio uses independently licensed open-source components. Their notices and licenses remain in the installed packages and system distributions. This file is an inventory, not a replacement for those licenses.

## Application dependencies

React, React DOM, Vite, TypeScript, Tailwind CSS, Lucide, Tiptap/ProseMirror, DOMPurify, PDF.js, pdf-lib, react-dropzone, idb, JSZip, Express, Multer, Archiver, dotenv, marked, Playwright and fontsource fonts. See `package.json`, `package-lock.json` and each installed package's license file.

## Local engines

- PyMuPDF / MuPDF — Artifex; AGPL/commercial licensing. Review https://artifex.com/licensing/ before redistribution or commercial deployment.
- pypdf — BSD-style license.
- pyHanko and pyhanko-certvalidator — MIT licenses; review transitive ASN.1/cryptography dependencies.
- Pillow — MIT-CMU license.
- python-docx, python-pptx, openpyxl — MIT licenses.
- pytesseract — Apache-2.0; Tesseract — Apache-2.0.
- Markdown, Beautiful Soup, lxml, fonttools, ReportLab and other Python packages — see pinned distributions in `requirements.txt` and their metadata.
- LibreOffice — Mozilla Public License v2.0 and associated component licenses.
- Chromium — BSD and many bundled component licenses.
- qpdf — Apache-2.0.
- Ghostscript — AGPL/commercial licensing by Artifex.
- Liberation and DejaVu fonts — their respective font licenses.

No third-party rights are granted by the personal-use statement for the application source. If you distribute a combined product, comply with all applicable notices, source-offer requirements and copyleft obligations. Installing dependencies separately does not automatically remove those obligations.
