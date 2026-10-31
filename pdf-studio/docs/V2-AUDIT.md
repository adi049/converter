# PDF Studio 2.0 — pre-change audit and upgrade plan

Checkpoint: `/home/user/checkpoints/pdf-studio-1.0-before-2.0.zip`
SHA-256: `76f22bc303f8c64140b4ad1e3eefb8abcfac4c7b23a8b5d9dd7cdd6070aaca0c`.

## Architecture retained
React/TypeScript shell and IndexedDB library; PDF.js previews; pdf-lib/OffscreenCanvas workers; Express session-scoped uploads and background subprocess queue; independent Python engines; local Chromium and LibreOffice. Existing API routes remain compatible. No replacement application or cloud service is introduced.

## Findings from source inspection
- Working 1.0 coverage includes real PDF creation/conversion, embedded watermarks, organization, AES, CMS signing, OCR, annotations/redaction, templates, image workers and explicit library saves.
- Plain-text PDF creation uses Helvetica and cannot render Hindi correctly. Rich HTML has no explicit Hindi fallback or custom-font pipeline.
- Watermark tiling/rotation preview is CSS-only and does not use export geometry. Custom fonts, point-based coordinates and safe margins are absent.
- Editor explicitly lacks existing-text replacement. Find/replace is redact-and-overlay and cannot render Hindi.
- Organizer's move-earlier arrow depends on drag state. Image background removal can export PNG bytes with a JPG/WebP filename.
- Library lacks backup/restore, metadata export, download history and content search. Global search does not filter the library.
- Batch jobs lack retry-failed and cancel-all controls. Folder structure is not exported in ZIPs.
- Upload validation trusts extensions; PDF parse failure is incorrectly treated as unencrypted. Internal exception text can reach clients. Security headers and global session bounds need strengthening.
- Light/system themes and a theme switcher conflict with the requested fixed identity. No official Luna logo asset exists; the user approved an exact text-only treatment.
- OCR language validation is inconsistent between native-text and forced-OCR paths; no confidence preview. PDF-to-DOCX emits all tables before other blocks, losing reading order. Mixed page sizes are flattened in editable DOCX/PPTX.
- Compression reports real sizes but has no side-by-side comparison control.

## Baseline environment failure (not a product pass)
The source and npm lockfile survived, but installed executables/Python packages did not. Initial baseline: engine collection failed (`pymupdf` missing), API reported 7 passes with document-engine failures, and all 13 browser tests failed because Chromium was absent. Dependencies are being restored. These failures are recorded, not counted as passes.

## Implementation priorities
1. Fixed violet/black/crimson visual system; accessible shell, dashboard, studios, dialogs, footer.
2. Unicode creation, custom fonts, watermark geometry/preview, genuine selected-text replacement workflow, OCR quality reporting.
3. Library backup/restore/search/download history; global search; recent/favorite tools; batch retry/cancel and folder-aware ZIP.
4. Content-sniffed uploads, bounded sessions, safe errors, security headers, cleanup and dependency audits.
5. Real Hindi, large/multipage, Office, security, conversion, browser and production regressions. Update this record with actual outcomes and remaining limitations.

## Final disposition
The upgrade retains the original architecture and working catalog. The fixed identity, watermark/editor improvements, Unicode/Hindi creation, OCR quality reporting, conversion fixes, library backup/recovery, batch controls and security hardening are implemented. Final verification: 57 Python checks, 6 validation checks, 18 production API checks, 7 capture/transport checks and 19 production browser workflows passed. TypeScript/build and both dependency audits passed. See `TEST-REPORT.md` for failures resolved and explicit remaining limitations; this is not a claim of perfect format fidelity or completion of every advanced commercial-suite feature.
