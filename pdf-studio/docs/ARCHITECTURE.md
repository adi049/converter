# PDF Studio — architecture and implementation notes

## Product boundary
A single-user, local-first document workbench. The Node server listens locally in a normal installation; the hosted sandbox uses 0.0.0.0 solely for its preview. No third-party document processing, analytics, accounts, ads, or subscriptions. A URL capture is the explicit exception: it asks the local browser engine to retrieve the URL entered by the user.

## Layers
- `src/`: React 18 + TypeScript + Tailwind; responsive desktop shell, searchable tool registry, accessible dialogs, drag/drop upload, PDF.js previews, Tiptap editor, tool workspaces.
- `src/engines/`: browser image worker and pdf-lib PDF creation. No document bytes leave this machine.
- `src/lib/`: typed API client, opt-in IndexedDB library, page-range parser, settings and history storage.
- `server/`: Express API; session-isolated temporary workspaces; bounded job queue; subprocess supervision; static production serving; Chromium capture.
- `engines/`: independently callable Python modules. A dispatcher receives a JSON request and writes real output files plus a result manifest.
- `tests/`: actual document fixtures and integration tests, not mocked conversions.
- `scripts/`: reproducible fixtures and environment checks.

## Processing engines
1. **Creation** — Chromium print for rich text/HTML/URL; PyMuPDF for text/blank PDFs; LibreOffice for Office/RTF; pdf-lib for image composition in a Web Worker.
2. **Conversion** — LibreOffice for Office → PDF; PyMuPDF rendering/text/HTML; python-docx, openpyxl and python-pptx for editable, best-effort PDF → Office. Exact reverse conversion is not claimed.
3. **Watermark** — PyMuPDF embedded text/image overlays, selected pages, per-page overrides, opacity, rotation, tiling, coordinates, reusable presets.
4. **Editing/organization** — PyMuPDF annotations, true redaction, signatures as visible marks, page operations, crops and layout changes. In-place text replacement is explicitly best effort.
5. **Optimization** — explicit quality/DPI settings, image recompression, garbage collection, stream compression, metadata removal. Reports actual byte counts; can produce a larger output.
6. **Security** — PyMuPDF AES-256 encryption and permission flags; authorized decryption; pyHanko cryptographic signing/verification. Visible signature marks are not cryptographic signatures.
7. **OCR** — local Tesseract, selectable installed languages, extracted text and searchable PDF text layers. Tables are heuristic and identified as such.
8. **Images** — browser Worker/Canvas for conversion, quality, resizing, rotation, cropping, brightness/contrast, watermarking and practical light-background removal. Server-side extraction from PDF images.
9. **Management/batch** — temporary files by default; user-initiated IndexedDB saves; folders, favorites, search, metadata and history; bounded per-file processing jobs and ZIP downloads.
10. **Advanced** — text/page-render comparison, metadata/outlines, Bates/page numbering, find/replace via redact-and-overlay without reflow, PDF/A via Ghostscript when available.

## Request lifecycle
Upload → session-scoped UUID record → inspect/preview → select operation and visible settings → enqueue → Python/LibreOffice/browser processing → output manifest → preview/download → optional library save. Jobs expose actual lifecycle stages; no fabricated percentage counters. Temporary workspaces expire and can be deleted immediately. Library saves are explicit and local to this browser profile.

## Safety and fidelity
- No arbitrary output paths from clients; UUID lookup only.
- File size/count/page limits; subprocess timeouts; serialized LibreOffice jobs.
- URL capture blocks private/loopback/link-local destinations and requires explicit confirmation.
- Redaction removes content rather than merely drawing a box; encrypted inputs require a password.
- Compression exposes lossy image settings; no silent quality reduction.
- PDF/A and digital signature trust report engine limitations rather than claiming certification.
- Capability endpoint exposes installed engines and OCR languages.

## Implementation order
1. Scaffold, dependency/capability checks and API contracts.
2. Creation, conversion, watermark and organization engines.
3. Editing, optimization, security, OCR and advanced operations.
4. Complete UI workspaces, editor, preview, library and batch queue.
5. Generate real PDF/DOCX/XLSX/PPTX/image fixtures; integration tests; browser smoke tests; production build and documentation.


## Delivered safeguards and contracts

- `POST /api/session` creates and registers a random bearer session. Uploads, jobs, downloads and deletion are scoped to that session. Loopback binds reject non-loopback Host headers.
- Browser image jobs use module Workers. Common image → PDF jobs stay in the browser; TIFF/BMP and library-seeded image jobs use the Python engine.
- The shared tool workspace submits independent per-file jobs, or one multi-input job for merge/compare/replace/sign/images. Watermark Studio uses the same queue with per-document page overrides. Auxiliary image assets are included in editor/logo-watermark job inputs.
- Native Python jobs run in a process group so cancellation/timeout terminates LibreOffice/Ghostscript descendants too. Capture cancellation closes Chromium and aborts pinned resource requests.
- Output registration enforces the session budget. Error/cancelled job directories are removed; successful outputs remain temporary until explicit deletion/TTL. Normal shutdown removes session directories.
- URL capture uses separate IPv4/IPv6 reserved-address block lists, validates every resolved address, pins the selected address in Node HTTP(S), retains hostname/TLS semantics, and re-enters the route for redirects. Resource and aggregate byte/count/deadline limits are enforced.
- Custom template previews are sanitized with DOMPurify and rendered in an opaque sandbox iframe with a restrictive CSP. Creator exports disable scripts and remote assets.
- Comparison HTML embeds its difference images as data URIs. CSV → XLSX explicitly marks cells as strings to avoid formula execution.
- The frontend records completed API and browser jobs in optional metadata history. Library saves, temporary files and history have separate deletion controls.

## Verification

The delivered source includes 46 Python engine tests, 17 live HTTP checks, seven transport/public-capture checks and 13 Chromium UI workflows. See `docs/TEST-REPORT.md` for exact scope and results. The production build was also served by Node and exercised with a real upload/export/cleanup cycle.


## 2.0 additions

- `server/validation.mjs`: extension/signature/Office-container checks, safe filenames and option-tree bounds.
- `src/lib/watermarkGeometry.ts` and `WatermarkCanvas.tsx`: shared placement model and high-DPI preview. Python implements the same geometry independently.
- `scripts/render_text.mjs` and `engines/unicode_pdf.py`: local Chromium text shaping, Ghostscript outlining and invisible Unicode mapping for complex-script plain-text exports. No network service receives the text.
- `src/lib/backup.ts`: versioned manifest, archive expansion limits, staged reads and new-ID restore. Existing library records are not overwritten.
- `tests/test_v2.py`, `tests/test_security.mjs`, `tests/browser/v2.spec.ts`: Hindi, large documents, replacement, geometry/fonts, conversion order/orientation, validation, backups and mobile/brand regressions.
- The API remains session-scoped and local. A fixed theme is applied at the shell; document pages and exports are never recolored. Footer links use `noopener noreferrer` and are outside document content.
