# PDF Studio 2.0 — verification report

Verified 31 October 2026 in the delivered Linux workspace. Counts below refer to executed checks, not an assertion that arbitrary documents or operating systems are error-free.

## Final executed results

| Check | Result |
|---|---|
| Environment check | All required system/Python/frontend engines ready |
| TypeScript `npx tsc --noEmit` | Passed |
| Production build `npm run build` | Passed; final build 10.22 s |
| Python real-file suite | **57 passed**, 39.31 s |
| Upload/validation checks | **6 passed** |
| Live production HTTP API | **18 passed** |
| Capture/transport, including two public-page requests | **7 passed** |
| Production Chromium browser workflows | **19 passed**, approximately 1.3 min |
| npm advisory audit | **0 vulnerabilities** |
| Python pinned-requirement advisory audit | **No known vulnerabilities found** |
| Luna branding in exported PDF | Absent; application footer stays outside document content |

Environment: Debian 13; Node 20.20.2; npm 10.8.2; Python 3.13.16; PyMuPDF 1.26.7; Pillow 13.0.0; Chromium 156. LibreOffice, Tesseract, qpdf and Ghostscript are installed. OCR languages: `deu eng fra hin osd spa`. Browser coverage uses Chromium at 1440×1000 and a 390×844 mobile viewport, not a cross-browser or formal accessibility certification.

The final browser run targets the actual built Node application on port 3002, not Vite HMR. Production API checks also target that server. The development preview remains separately available on port 5173.

## Real-file coverage

Fixtures include a three-page PDF containing native text, a photograph, table and outline; a scanned PDF and OCR image; Hindi raster text; DOCX with content; PPTX slides; XLSX formulas; RTF/TXT/CSV/Markdown/HTML; and JPEG/PNG images. Additional tests create a 160-page PDF, mixed page orientations, password-protected PDFs, signing certificates, replacement targets and custom-font inputs.

Python checks cover creation, pagination, blank/custom pages, images, Office conversion, PDF-to-Office/text/HTML/Markdown/images, organization, embedded text/logo watermarks, per-page overrides, safe margins, custom fonts, annotations, permanent redaction, selected-text replacement, find/replace, numbering, metadata, bookmarks/TOC, compression, AES encryption/authorized unlock, CMS signing/verification/tampering, PDF/A generation, OCR languages/quality/tables, comparison, Markdown-to-DOCX, form flattening and CSV formula safety.

New 2.0 regressions specifically verify:

- Hindi creation remains multipage and searchable; mixed Hindi/Japanese and a mapping spanning more than 100 Unicode characters survive the invisible text layer.
- Hindi OCR returns real recognized text and a separate quality report.
- Selected original text is removed and replacement text is embedded.
- Custom TTF watermark input and safe-margin geometry produce real PDFs.
- DOCX blocks retain reading order around tables and mixed page orientations become separate sections.
- A 160-page PDF can be extracted and have noncontiguous pages selected.
- Missing OCR languages fail explicitly instead of silently substituting English.
- Spoofed PDF/PNG/Office files, binary text, invalid JSON, executable extensions, unsafe filenames/prototype keys and invalid fonts are rejected.

Browser checks cover real Word upload/export/download, embedded watermark text, logo/custom-font/tiled watermark export, page organization, browser image conversion, rich-text/table export and saved templates, library persistence/rename/favorites, compression confirmation, batch ZIP, Markdown-to-Word/history, editor image and existing-text replacement, global search, fixed theme/footer/mobile overflow, Hindi creation/search, backup/restore/metadata export and failed-job retry after correcting settings.

## Failures found and resolved during verification

These were real failures, not counted as passes until rerun successfully:

1. Missing restored system/Python dependencies caused the initial post-checkpoint baseline to fail. Engines were reinstalled before product verification.
2. Hindi text initially rendered incorrectly with standard PDF fonts, and Chromium's native extraction map split conjuncts. Plain-text creation now uses Chromium shaping, local outlining and an invisible Unicode mapping. The export warns that complex-script text is outlined rather than live editable text.
3. PNG signature comparison used UTF-8 conversion and rejected valid PNG bytes. It now compares the original binary signature; valid image workflows pass.
4. Dispatcher filtering discarded OCR primary-result ordering. It now preserves the engine's returned order; text/searchable PDF appears before its quality JSON.
5. Existing-text buttons propagated pointer events to the annotation canvas. They now stop propagation and open the replacement dialog.
6. No-file creation tools built zero batches. They now create one no-input job.
7. Development HMR/dependency optimization reset long browser runs. Final browser verification uses the production build and passed all 19 workflows.
8. Repeated test sessions reached the intentional 20-session cap. Tests now close their sessions through the real cleanup endpoint; the cap was not weakened.
9. Retry verification initially omitted compression confirmation. The corrected test confirms the lossy settings, retries the failed task and receives an actual compressed PDF.
10. A dummy OCR-report checkbox was removed; the quality report is always generated and explained as an output, not controlled by a nonfunctional setting.
11. Pillow 12.3.0 had known advisories. The requirement was upgraded to Pillow 13.0.0 and the final audit reports no known vulnerabilities.

## Security boundaries verified

- Random session tokens and session-scoped file access; another token cannot download a file.
- Extension/content checks, ZIP-container type checks, size/count/depth limits and safe names.
- Cross-site origin rejection, `nosniff`, referrer/permissions policies and production CSP.
- Owner-only temporary directories on POSIX; no public temporary-directory route.
- Active-job-safe temporary deletion and explicit session cleanup.
- Public URL capture rejects private/reserved/local targets, pins the validated IP, revalidates redirects, disables scripts/downloads and enforces byte/request/time/cancellation limits.
- No document bytes are sent to external conversion services. Public capture tests retrieve only public test pages.

This is a personal local application, not a hardened multi-tenant hosting service. Native document parsers still require OS-level isolation for hostile files. File deletion is unlinking, not forensic erasure. IndexedDB and backup ZIPs are not encrypted. PDF permission flags are reader-enforced restrictions, not a substitute for a strong open password. Signature verification is offline and does not assert CA trust, revocation or timestamp validity.

## Remaining limitations / not claimed complete

- PDF/Office conversion is best-effort reconstruction; no guarantee of exact original formatting, formulas, slide objects, columns, equations or fonts. Facsimile modes preserve appearance at the expense of editability.
- Existing-text editing is redact-and-overlay, not a word processor: surrounding paragraphs do not reflow. Scanned/outlined text requires OCR or an overlay.
- Complex-script watermark marks are high-resolution shaped images, not searchable live text. Latin watermark text remains extractable. Custom-font metrics can differ slightly between browser and PDF.
- The Hindi/Unicode plain-text export's outlined search layer is not live editable text. Missing visual fonts can still produce missing glyphs; install appropriate Noto/language fonts. Arbitrary emoji/font coverage was not certified.
- Templates are editable starting points, not legally/financially validated documents. There is no dedicated tax-compliant invoice system or certified resume/contract generator.
- PDF/A output is generated, not certified with veraPDF. Redaction must be visually reviewed; crop/whiteout are not secure deletion. Metadata/attachments may need separate removal.
- Library recovery is via explicit saves/backups; expired temporary documents are not recoverable. Backups restore new copies and do not overwrite existing documents.
- The queue is bounded and cancellable within the running local server; it is not a durable cross-restart job scheduler. Some engines expose indeterminate rather than fabricated progress.
- No native Windows/macOS test run, formal WCAG audit, malware sandbox, authenticated public deployment or exhaustive every-format test matrix is claimed.

## Reproduce

Start the API/application, then run the commands in README's **Verification commands** section. For production UI tests use `TEST_WEB_URL=http://127.0.0.1:3001 npm run test:ui`. Run public transport tests separately with `node tests/test_capture.mjs --public`. Advisory results are time-sensitive and should be rerun after dependency changes.
