from pathlib import Path
import io, json, subprocess, shutil
import pymupdf as fitz
from common import open_pdf, output, note, UserError


def apply(ctx,files,o):
    op=ctx['operation'];f=files[0];stem=Path(f['name']).stem
    if op in ('protect','encrypt'):
        doc=open_pdf(f,o.get('password'));user=str(o.get('userPassword',''));owner=str(o.get('ownerPassword',''))
        if len(user)<6 and len(owner)<6:raise UserError('Use a password of at least 6 characters. A strong passphrase of 12+ characters is recommended.')
        if not owner:owner=user
        perms=0
        if o.get('allowPrint',True):perms|=fitz.PDF_PERM_PRINT|fitz.PDF_PERM_PRINT_HQ
        if o.get('allowCopy',True):perms|=fitz.PDF_PERM_COPY|fitz.PDF_PERM_ACCESSIBILITY
        if o.get('allowEdit',False):perms|=fitz.PDF_PERM_MODIFY
        if o.get('allowAnnotate',True):perms|=fitz.PDF_PERM_ANNOTATE|fitz.PDF_PERM_FORM
        p=Path(ctx['out'])/(stem+'-protected.pdf')
        doc.save(p,encryption=fitz.PDF_ENCRYPT_AES_256,user_pw=user,owner_pw=owner,permissions=perms,garbage=4,deflate=True)
        note(ctx,'Encrypted with AES-256. Permission flags are enforced by conforming PDF readers, not a substitute for encryption. User password controls opening; owner password controls permissions. Passwords are not saved in the library or history.')
        return output(ctx,p,encryption='AES-256')
    if op in ('unlock','decrypt'):
        doc=open_pdf(f,o.get('password'))
        if not f.get('encrypted',False):note(ctx,'This document was already unencrypted; an unprotected copy was saved.')
        return output(ctx,__import__('common').save(ctx,doc,stem,'-unlocked')['path'],encryption='none')
    if op=='sign':return sign(ctx,files,o)
    if op=='verify-signatures':return verify(ctx,files,o)
    if op=='pdfa':return pdfa(ctx,files,o)
    raise UserError('Unknown security operation.')


def sign(ctx,files,o):
    from pyhanko.sign import signers,fields
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    cert=next((f for f in files if Path(f['name']).suffix.lower() in ('.p12','.pfx')),None)
    if not cert:raise UserError('Choose a PKCS#12 (.p12 or .pfx) signing certificate and enter its password. A drawn signature is not a digital certificate signature.')
    try:signer=signers.SimpleSigner.load_pkcs12(cert['path'],passphrase=str(o.get('certificatePassword','')).encode())
    except Exception as e:raise UserError('Could not unlock the signing certificate. Check the PKCS#12 password. '+str(e)[:140])
    if not signer:raise UserError('No usable signing key was found in this certificate.')
    source=Path(files[0]['path']);doc=open_pdf(files[0],o.get('password'));encrypted=bool(doc.is_encrypted);doc.close()
    if encrypted:raise UserError('Unlock this PDF with the Unlock PDF tool before cryptographic signing. Signing an authorized decrypted copy avoids ambiguous password handling.')
    p=Path(ctx['out'])/(Path(files[0]['name']).stem+'-signed.pdf')
    with source.open('rb') as src:
        writer=IncrementalPdfFileWriter(src)
        visible=o.get('visible',False)
        spec=fields.SigFieldSpec('StudioSignature',on_page=0,box=(40,40,260,95)) if visible else None
        meta=signers.PdfSignatureMetadata(field_name='StudioSignature',reason=str(o.get('reason','Approved locally in PDF Studio')),name=str(o.get('signerName','PDF Studio user')),md_algorithm='sha256')
        with p.open('wb') as dest:signers.sign_pdf(writer,meta,signer=signer,new_field_spec=spec,output=dest)
    note(ctx,'Signed locally with a CMS/PKCS#7 cryptographic signature and SHA-256. No certificate or private key is uploaded. Certificate identity and trust depend on your PKCS#12 certificate; a self-signed certificate is not automatically trusted. No external timestamp or revocation service is contacted.')
    return output(ctx,p,signature='CMS / SHA-256')


def verify(ctx,files,o):
    from pyhanko.sign.validation import validate_pdf_signature
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko_certvalidator import ValidationContext
    from pyhanko.sign.diff_analysis import ModificationLevel
    reports=[]
    with open(files[0]['path'],'rb') as stream:
        reader=PdfFileReader(stream)
        # Validation of local integrity only: do not silently fetch OCSP/CRL or trust an unknown CA.
        vc=ValidationContext(trust_roots=[],allow_fetching=False,revocation_mode='soft-fail')
        for sig in reader.embedded_signatures:
            try:
                status=validate_pdf_signature(sig,signer_validation_context=vc)
                reports.append({'field':sig.field_name,'intact':bool(status.intact),'validSyntax':bool(status.valid),'trusted':bool(status.trusted),'modificationLevel':str(status.modification_level),'signer':status.signing_cert.subject.human_friendly,'signingTime':str(status.signer_reported_dt),'coverage':str(status.coverage),'permittedModifications':bool(status.docmdp_ok),'unmodified':bool(status.intact and status.valid and status.docmdp_ok and status.modification_level==ModificationLevel.NONE),'summary':status.summary()})
            except Exception as e:reports.append({'field':sig.field_name,'intact':False,'validSyntax':False,'trusted':False,'error':str(e)[:400]})
    if not reports:note(ctx,'No embedded cryptographic digital signatures were found. Visible signatures or stamped names are not cryptographic signatures.')
    else:note(ctx,'Integrity, syntax and post-signing changes are checked offline. An intact CMS digest alone does not mean the document is unchanged: also check unmodified and permittedModifications. Trust is not asserted without a trusted certificate chain. Revocation and timestamp validity are not established by this offline check.')
    p=Path(ctx['out'])/(Path(files[0]['name']).stem+'-signature-report.json');p.write_text(json.dumps({'file':files[0]['name'],'signatures':reports,'notes':ctx.get('notes',[])},indent=2))
    return output(ctx,p,signatures=reports)


def pdfa(ctx,files,o):
    if not shutil.which('gs'):raise UserError('Ghostscript is required for PDF/A conversion.')
    doc=open_pdf(files[0],o.get('password'));doc.close()
    root=Path(ctx['out']);p=root/(Path(files[0]['name']).stem+'-pdfa.pdf')
    icc=next(Path('/usr/share').glob('color/icc/**/srgb.icc'),None)
    if not icc:icc=next(Path('/usr/share').glob('ghostscript/**/iccprofiles/srgb.icc'),None)
    if not icc:raise UserError('An sRGB ICC profile is required. Install ghostscript and its ICC profiles.')
    definition=next(Path('/usr/share/ghostscript').glob('*/lib/PDFA_def.ps'),None)
    if not definition:raise UserError('Ghostscript PDF/A definition file not found.')
    text=definition.read_text();text=text.replace('/ICCProfile (srgb.icc)',f'/ICCProfile ({icc})')
    ps=root/'PDFA_def.ps';ps.write_text(text)
    cmd=['gs','-dPDFA=2','-dBATCH','-dNOPAUSE','-dNOOUTERSAVE','-sColorConversionStrategy=RGB','-sDEVICE=pdfwrite','-dPDFACompatibilityPolicy=1',f'-sOutputFile={p}',str(ps),files[0]['path']]
    run=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
    if run.returncode or not p.exists():raise UserError('PDF/A export failed: '+(run.stderr or run.stdout)[-600:])
    note(ctx,'Converted using Ghostscript PDF/A-2 settings. This is not a certified PDF/A validation result. Transparency, forms, encryption, nonembedded fonts or external references may be changed or rejected. Validate with a standards-compliant validator such as veraPDF before archival submission.')
    if run.stderr:note(ctx,'Ghostscript diagnostics: '+run.stderr[-600:])
    return output(ctx,p,standard='PDF/A-2 (conversion, not certified validation)')
