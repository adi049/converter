# PDF Studio 2.0 — My Personal Document Toolkit

A working, single-user document workbench with a responsive React interface and real local processing engines. No account, advertising, subscription, analytics, or third-party document-conversion service.

**Important:** this is a local application, not a static website. The browser handles previews, image processing and some PDF creation; a Node server on your own computer supervises Python, LibreOffice, Tesseract, Ghostscript and Chromium. Opening `index.html` directly will not start those engines.

## Start here

Tested environment: Debian 13, Node 20.20.2, Python 3.13.16, Chromium 156. Node 20.19+ and Python 3.11+ are recommended. Use a current desktop Chromium, Chrome, Edge or Firefox with Web Workers, IndexedDB and OffscreenCanvas support. Chromium is the browser tested here.

### 1. Install system engines

Debian/Ubuntu:

```bash
sudo apt update
sudo apt install -y libreoffice-writer libreoffice-calc libreoffice-impress \
  tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin tesseract-ocr-fra \
  tesseract-ocr-deu tesseract-ocr-spa qpdf ghostscript chromium \
  fonts-liberation fonts-dejavu-core fonts-noto-core icc-profiles-free
```

On Ubuntu, `chromium` may be a transitional package. If `chromium --version` does not work, install a working Chromium package and set `CHROMIUM_PATH` to its executable. The `icc-profiles-free` package name can vary by distribution; the environment check and PDF/A engine explain what is missing.

macOS, with Homebrew:

```bash
brew install --cask libreoffice chromium
brew install tesseract tesseract-lang qpdf ghostscript
```

Set `CHROMIUM_PATH` to the installed Chromium executable. macOS font and ICC locations differ from the Debian paths used by the watermark/PDF/A engines; see **Platform notes**. The complete test matrix was run on Linux, not macOS or Windows.

Windows: install Node, Python, LibreOffice, Tesseract, Ghostscript and Chromium separately; add their executables to `PATH`. Set `PYTHON_PATH` and `CHROMIUM_PATH` if automatic discovery fails. WSL2 with a Debian/Ubuntu distribution is the simpler route. Native Windows PDF/A/font discovery needs adaptation and is not claimed as tested.

### 2. Install application dependencies

From this directory:

```bash
npm ci
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm run check
```

The Python requirements are pinned to the tested environment. If a wheel is unavailable for your Python version, use Python 3.13 rather than silently substituting PyMuPDF 2.x: this application uses the documented PyMuPDF 1.26 API.

### 3. Configure and run

```bash
cp .env.example .env
# Windows PowerShell: Copy-Item .env.example .env
npm run dev
```

Open **http://localhost:5173**. Vite proxies `/api` to the local Node server. The default API bind is `127.0.0.1:3001`.

If using a virtual environment, set `PYTHON_PATH` in `.env` to its absolute Python executable, or activate the environment before starting npm. Example:

```dotenv
PYTHON_PATH=/absolute/path/to/pdf-studio/.venv/bin/python
```

`npm run check` uses the Python interpreter running the command; Settings → Local processing engines checks the interpreter configured for the server.

### Sandbox/reverse-proxy preview

Only for a trusted sandbox or properly authenticated reverse proxy:

```bash
HOST=0.0.0.0 npm run dev
```

For the built application served directly on port 3001 inside the trusted Arena sandbox, use `HOST=0.0.0.0 API_PORT=3001 PREVIEW_EMBED=true npm start`. The explicit `PREVIEW_EMBED` opt-in permits the cross-origin preview iframe; ordinary local/production launches retain `X-Frame-Options: SAMEORIGIN`. Do not enable this override on an untrusted public deployment.

The included Vite configuration accepts the sandbox preview hostname and proxies API requests. **Do not expose this personal API directly to the public internet.** Anyone allowed to create a session can consume local CPU, disk and installed engines. The loopback default additionally rejects non-loopback Host headers. The hosted Arena preview necessarily uses a public sandbox hostname; it is a development demonstration, not a recommendation for public deployment.

## Production on your own computer

```bash
npm run build
npm start
```

Open **http://localhost:3001**. Node serves both the built frontend and API from one origin. Keep `.env`, `engines/`, `server/`, `requirements.txt` and `dist/` together. `dist/` alone is not the complete application.

The build is generated locally and excluded from the source archive. There is no CDN dependency at runtime: fonts, PDF.js workers and application assets are bundled.

## New in 2.0

- One fixed premium theme, six dedicated studios, exact text-only Managed By Luna footer (no unofficial logo recreation).
- Hindi/Unicode plain-text creation uses local Chromium shaping. Complex-script text is outlined and paired with an exact invisible Unicode text layer for reliable search/copy. This preserves appearance but is not live editable text; the export includes a warning.
- Custom TTF/OTF fonts in Creator and Watermark Studio; shared watermark placement geometry; real selected-text replacement with an explicit no-reflow warning.
- OCR quality reports, installed-language validation, Hindi support, better DOCX reading order and mixed-page orientation.
- Library backups/restores as new copies, folder-aware ZIPs, content search and metadata exports. Batch cancel/retry and compression comparison.
- Content-sniffed uploads, owner-only temporary directories, bounded sessions/jobs, safer errors, CSP/security headers and session-scoped downloads.

See `docs/TEST-REPORT.md` for actual final test counts and `docs/V2-AUDIT.md` for the pre-upgrade findings. Some advanced requests remain best-effort or are not implemented; the limitations below and in the report are part of the product contract.

## What works

The catalog contains 58 tool entries backed by reusable operations, plus six dedicated studios. Multiple catalog entries can intentionally share an engine.

| Area | Implemented workflows |
|---|---|
| Dashboard | Fixed Violet / Matte Black / Crimson identity, responsive sidebar, reduced motion, global tool/document search, favorite tools, recent files, queue, history, settings |
| Create | Plain text, HTML, rich text/Tiptap, Markdown, images, blank/lined/grid pages, public URL capture, Office/RTF/TXT/CSV → PDF |
| Convert | PDF → DOCX/XLSX/PPTX, JPG/PNG, individual page images, text, self-contained positioned HTML and Markdown |
| Watermark Studio | Text or image/logo, custom TTF/OTF, font/size/color/opacity/rotation, shared preview/export geometry, point/percent coordinates, safe margins, tiling, page ranges, per-page text/disable overrides, local presets, batches up to 100 PDFs; marks are embedded in exports |
| Organize | Merge, split, extract/delete/reorder/duplicate/rotate/insert/replace/reverse, visual page plans, crop and resize |
| Edit | Selected existing-text redact-and-replace, overlay text, highlight/underline/strike, shapes, freehand, images, notes/comments, date marks, visible signatures, whiteout, permanent redaction, undo/redo; exact find/replace where native text exists |
| Optimize | Explicit DPI/image-quality presets/custom settings, lossy confirmation, optional grayscale image recompression, metadata removal, font subsetting, qpdf linearization, actual before/after sizes |
| Security | AES-256 encryption and reader permissions, authorized decryption, PKCS#12 CMS signing, offline signature integrity/modification/trust reporting |
| Images | Browser Worker conversion/compression/resize/crop/rotation/brightness/contrast, text/logo watermarks, connected light-background removal, images → PDF |
| OCR | Local Tesseract, installed language selection, text/DOCX, searchable PDF, native/image-heuristic table extraction |
| Office/data | LibreOffice conversion, CSV → XLSX with text-typed cells, Markdown → editable DOCX |
| Advanced | Text/visual comparison, metadata inspect/edit/remove, bookmarks, heuristic TOC, Bates/page numbers/headers/footers, flatten forms/annotations, Ghostscript PDF/A-2 conversion |
| Library | Explicit IndexedDB saves, folders/favorites, filename/content search, rename/filter/sort, confirmed deletion, folder ZIP, versioned non-destructive backup/restore, metadata export, temporary-file management |
| Output | PDF.js preview, download, browser print dialog, ZIP batches, optional local library save |

### A typical workflow

1. Open a tool and add compatible documents. Uploads go only to the local Node workspace.
2. Review the file preview and settings. Compression always requires explicit confirmation.
3. Process. The queue reports engine stages and available actual progress; some native operations are indeterminate rather than inventing a percentage.
4. Preview/download the output. Choose **Save to library** only if you want a persistent browser-local copy.
5. Clear temporary files in Settings when finished, or let their TTL expire.

The dashboard/global Ctrl/⌘+O upload shortcut opens the temporary library workspace. Tool-specific uploads remain inside the chosen tool. Library → **Use in a tool** creates a temporary working copy and opens a compatible tool automatically.

## Watermark behavior

- The live canvas is an appearance preview of the **first** PDF. Export embeds actual PDF content; it is not a CSS overlay on the downloaded file.
- Page ranges and per-page overrides apply by page number to each selected PDF. Shorter documents only have their existing pages. Preview pagination refers to the first file.
- Per-page overrides currently support custom text and enable/disable. Design settings are shared across the batch.
- Presets store design settings locally, not logo bytes or passwords. Reattach logo/custom-font files after reloading.
- Complex-script watermark text (including Hindi) is locally shaped into a high-resolution image. Latin text stays searchable. Browser and export font metrics can differ slightly.
- Built-in watermark fonts use Liberation/DejaVu files on the tested Linux installation. Upload a TTF/OTF for a custom font. Install the listed fonts for consistent output.
- A watermark identifies content; it does not redact, encrypt or prevent copying.

## Privacy, storage and security

- Temporary uploads and outputs live under `.studio-temp/<session UUID>/` with owner-only directory permissions on POSIX. They are not a permanent document library.
- Sessions use random bearer tokens. File IDs are scoped to their session; clients do not supply filesystem paths. Another session cannot download your file by guessing its UUID.
- The library is **opt-in** and stored in this browser profile’s IndexedDB. It is not operating-system-encrypted storage. Protect your OS account and browser profile, and download backups of important documents.
- History is optional metadata only: tool, filename, time, output count/size and engine notes. Passwords and document bytes are not intentionally recorded in history.
- Temporary files expire after 120 minutes of session inactivity by default; cleanup runs periodically and on normal shutdown. Startup removes stale application session directories. **Clear temporary files** refuses to delete files belonging to active jobs.
- Deletion means filesystem unlink/IndexedDB deletion, not guaranteed forensic overwriting. SSD wear leveling, filesystem journals, backups and swap can retain data. Use full-disk encryption and an appropriate secure-erase procedure for highly sensitive material.
- PDF open/owner passwords and certificate passwords are sent to the local API for the requested operation, not to an external service. Job request files are removed after processing; temporary documents remain until deletion/TTL. Do not share your temporary directory while working on sensitive files.
- URL capture is the explicit network exception. It requires confirmation, blocks private/local/reserved destinations, pins the validated IP for each HTTP request, revalidates redirects, disables JavaScript/service workers/downloads, and limits resource size/count/time. HTML/creator exports block remote assets by default.
- Office documents are opened by LibreOffice. Treat unknown documents as potentially hostile; use an isolated OS account/VM for untrusted files. No application can guarantee that a complex native parser is exploit-free.
- Reader permission flags are enforced by conforming PDF readers. Confidentiality comes from encryption and a strong open password, not permission checkboxes.
- Signing requires your own PKCS#12 certificate/key. A self-signed certificate can prove integrity relative to that key but is not automatically trusted. Verification separates digest integrity, syntax, post-signing modifications and chain trust. No timestamp authority, OCSP or CRL is contacted.
- Run `npm run test:security` periodically. The 2.0 verification found zero npm advisories and no known Python requirement vulnerabilities after upgrading Pillow to 13.0.0. The delivered lockfile uses patched Tiptap/Archiver dependencies and a patched transitive `minimatch` override.

## Fidelity and technical limits — please read

These are real implementations, not claims of perfect commercial-format equivalence.

| Feature | Limitation / recommended practice |
|---|---|
| PDF → Word | Best-effort reading order, text styles, images and detected tables. Columns, wrapping, headers, equations and original fonts may differ. Page-image mode preserves appearance but is not editable text. |
| PDF → Excel | Heuristic native table detection; one worksheet per page. Complex/merged grids and scans need review/OCR. It does not recover spreadsheet formulas. |
| PDF → PowerPoint | Page-image slides with extracted text in notes, or best-effort editable text boxes/images. It does not recover original slide objects/animations. |
| PDF → HTML/Markdown | HTML embeds images and absolutely positions text; it is self-contained but not semantic/reflowing. Markdown is reading-order text with heading hints, not exact layout. |
| Office → PDF | Uses LibreOffice, not Microsoft Office. Fonts, pagination, macros and advanced layout can vary. Spreadsheet output follows saved print settings. |
| Find/replace | Exact native-text matches only; redacts and inserts replacement text without paragraph reflow. Long replacements can require manual adjustment. OCR scans first. |
| Redaction | Removes marked text and affected image/vector content. Inspect every page, remove/share the redacted copy rather than the original, and consider metadata/attachments separately. Whiteout is explicitly only a visual cover. |
| Crop | Changes page boxes, not underlying content. It is not secure deletion. |
| Flatten/resize | Bakes visible annotation/widget appearances into content; fields/comments stop being interactive. Review appearances first. Resize preserves vector content but rebuilds pages and does not retain interactive structures/bookmarks as an editable form workflow. |
| Compression | Rewrites images at selected DPI/quality; vectors remain vectors. Grayscale applies to recompressed images, not every vector color. Already optimized files may become larger. Original/output bytes are shown. |
| OCR | Recognition is imperfect. Searchable PDF export rasterizes pages at the selected DPI; keep the original. Installed language packs determine available languages. Complex tables/skew/handwriting need review. |
| Background removal | Local connected-light-background flood fill, not AI subject segmentation. Hair, shadows and complex backgrounds need manual editing. |
| PDF/A | Ghostscript PDF/A-2 conversion, not certified validation. Transparency/forms/fonts can change. Validate with veraPDF before archival submission. |
| Signatures | Offline CMS/SHA-256 signing and integrity checks. No external trust/timestamp/revocation assertion. An intact original signature can coexist with later incremental changes; inspect `unmodified` and `permittedModifications`, not only `intact`. |
| TOC | Larger-text heuristic, not semantic understanding. The optional inserted contents page supports up to 40 entries; review overflow and references. |
| Library search | Searches saved filenames and file-type/folder metadata. For content search, extract text/OCR first; this is not a full-text indexing service. |
| Undo/redo | Available in rich text, annotations, watermarks and page organization. It is not a universal undo for completed server exports. |

Default limits: 100 MB per upload, 1 GiB per temporary session including registered outputs, 50 uploads/request, 100 inputs/job, 1,500 pages/PDF, 3,000 pages in a visual plan, two concurrent jobs, ten-minute Python job timeout. LibreOffice has a 180-second subprocess timeout. Browser image output is capped at 40 megapixels and 12,000 pixels per side. URL capture: ports 80/443, 20 MB/resource, 80 MB total, 100 requests, 20 seconds/resource and a two-minute capture deadline.

## Configuration

See `.env.example`.

| Variable | Default | Purpose |
|---|---|---|
| `HOST` | `127.0.0.1` | API bind address; use `0.0.0.0` only for a trusted preview/proxy |
| `API_PORT` | `3001` | API/production HTTP port; Vite reads this for its proxy |
| `PYTHON_PATH` | `python` | Python executable with requirements installed |
| `CHROMIUM_PATH` | auto-detected | Explicit Chromium executable path |
| `TEMP_DIR` | `.studio-temp` | Dedicated temporary directory; do not point at a general-purpose folder |
| `TEMP_TTL_MINUTES` | `120` | Session inactivity TTL |
| `MAX_FILE_MB` | `100` | Per-upload limit; browser dropzones also enforce 100 MB |
| `MAX_SESSION_MB` | `1024` | Temporary workspace budget |
| `MAX_CONCURRENT_JOBS` | `2` | Queue concurrency; native Office and capture jobs are additionally serialized |
| `JOB_TIMEOUT_MINUTES` | `10` | Python subprocess timeout |

Changing server environment variables requires a server restart. Settings → Check again refreshes engine availability, not environment variables.

## Tests and real sample documents

The repository includes generated, non-personal PDF/Office/image/CSV/Markdown/HTML fixtures and their generator. Tests inspect actual output bytes, extracted text, page counts, embedded marks, encryption round trips, signatures, table cells and HTTP downloads—not mocked success responses.

```bash
npm run samples             # regenerate fixtures
npm test                    # Python engine integration tests
npm run test:api            # requires npm run dev in another terminal
npm run test:capture        # local transport, size, timeout and cancellation tests
npm run test:ui             # Chromium workflows; starts/reuses local dev servers
npm run test:all            # build + engine/API/transport/UI suites
```

For an explicit **public-network** capture/redirect test (retrieves public example.com and a public redirect fixture; no user documents are uploaded):

```bash
node tests/test_capture.mjs --public
```

The browser configuration uses `/usr/bin/chromium` by default. Set `CHROMIUM_PATH` to another executable if needed. UI tests require the Python/system engines to be installed. Test output is written to `test-results/` and `playwright-report/`; these are disposable.

See `docs/TEST-REPORT.md` for the delivered verification results and `docs/ARCHITECTURE.md` for module boundaries and request lifecycle.

## Troubleshooting

| Symptom | Fix |
|---|---|
| “Could not start the local processing API” | Start `npm run dev`; check API port and `/api/health`. Do not open the source HTML as a file. |
| Session expired / input no longer exists | TTL elapsed or the server restarted. Add the file again; explicitly saved library copies remain in IndexedDB. |
| Engine shows Setup needed | Run `npm run check`, install the missing dependency, verify `PYTHON_PATH`, restart server and refresh capabilities. |
| `pymupdf` import/version errors | Activate the intended venv and install `requirements.txt`; keep PyMuPDF 1.26.7. |
| Office conversion fails | Run `libreoffice --version`; install Writer/Calc/Impress. Close conflicting LibreOffice profiles and retry a smaller file. The server serializes these jobs and uses isolated profiles. |
| OCR language missing | Install the Tesseract language pack, verify `tesseract --list-langs`, restart/refresh. Use codes such as `eng+fra`, not display names. |
| Chromium unavailable | Install it or set `CHROMIUM_PATH`. Browser tests and URL/HTML printing need an executable, not just the npm Playwright library. |
| URL blocked | Only public HTTP(S), standard ports and public addresses are allowed. Private networks, credentials in URLs and localhost are intentionally blocked. |
| URL output missing dynamic content | JavaScript is deliberately disabled. Use a static/printable page or save the rendered page locally and use HTML → PDF. |
| PDF/A ICC/definition missing | Install Ghostscript, free ICC profiles and its `PDFA_def.ps`; Linux discovery is tested. Other platforms may need path adaptation. |
| Watermark font differs | Install Liberation/DejaVu fonts and review the exported PDF. Browser font substitution can differ from embedded PDF fonts. |
| Compression does not shrink file | Keep the original. The input may already be optimized or mostly vector/font data. Adjust settings explicitly if appropriate. |
| Browser image worker fails | Use a current browser, reduce image dimensions/batch size, and ensure OffscreenCanvas is available. Server-side images → PDF supports additional TIFF/BMP inputs. |
| Print button only opens a PDF | Allow popups, then use the browser/PDF viewer’s Print command. This avoids printing the app shell. |
| Saved library disappeared | Browser site data/profile was cleared or another profile/origin is being used. Restore from downloaded backups. |
| Port already in use | Stop the conflicting process or change `API_PORT`; restart both Vite and API. |
| Active file cannot be deleted | Wait for completion or cancel the job, then clear temporary files. |

## Project layout

```text
src/pages/       Dashboard, catalog, dedicated studios, library and settings
src/components/  Uploads, controls, PDF.js previews and result downloads
src/lib/         Tool registry, API client, IndexedDB and application context
src/engines/     Browser image/PDF Worker
server/          Session API, job supervision and safe Chromium capture
engines/         Independent Python processing modules and dispatcher
scripts/         Environment diagnostics and sample generation
tests/           Real-file engine, HTTP, transport and browser tests
docs/            Architecture, limitations and verification report
```

## Licenses

Application source is provided for your personal use and modification. Third-party packages retain their own licenses. LibreOffice, Tesseract, Ghostscript, Chromium, PyMuPDF/Artifex and pyHanko have separate license terms; review them before redistribution or commercial use. PyMuPDF is AGPL/commercially licensed by Artifex. This repository does not replace those licenses.

## Verification commands

```bash
npx tsc --noEmit
npm run build
npm test                    # real Python document fixtures
npm run test:validation     # upload signature / path / option checks
npm run test:api            # requires the local API running
npm run test:capture        # local transport, limits, cancellation
npm run test:ui             # starts/reuses Vite; or TEST_WEB_URL=http://127.0.0.1:3001
npm run test:security       # npm and Python advisory databases
```

For a production-browser regression, run `npm run build`, `npm start`, then `TEST_WEB_URL=http://127.0.0.1:3001 npm run test:ui`. Public URL capture is tested separately with `node tests/test_capture.mjs --public`; only public test pages are retrieved, never your documents. Browser tests save fixtures under `/tmp` and screenshots under `artifacts/`. Test reports are local HTML and may contain document filenames.
