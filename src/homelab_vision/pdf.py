"""Bounded PDF evidence bundles. Text-layer presence is a routing heuristic."""
import hashlib
import html
import json
from contextlib import closing
from pathlib import Path


class PdfValidationError(ValueError):
    pass


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_pdf(source: Path, output: Path, *, max_bytes=20_000_000,
                max_pages=40, max_page_pixels=20_000_000, dpi=144):
    import pypdfium2 as pdfium
    if not 72<=dpi<=200 or not 1<=max_pages<=100:
        raise ValueError('Unsupported rendering limits')
    source=source.resolve(strict=True)
    if source.stat().st_size>max_bytes:
        raise PdfValidationError('PDF exceeds byte limit')
    with source.open('rb') as stream:
        data=stream.read(max_bytes+1)
    if len(data)>max_bytes: raise PdfValidationError('PDF exceeds byte limit')
    if not data[:1024].lstrip().startswith(b'%PDF-'):
        raise PdfValidationError('Input has no PDF header')
    digest=hashlib.sha256(data).hexdigest()
    try:
        document=pdfium.PdfDocument(data)
    except pdfium.PdfiumError as error:
        raise PdfValidationError('Encrypted, malformed or unsupported PDF') from error
    try:
        count=len(document)
        if not 1<=count<=max_pages: raise PdfValidationError('Page count exceeds limit')
        for number in range(count):
            with closing(document[number]) as page:
                width,height=page.get_size()
                if width<=0 or height<=0 or int(width*dpi/72+1)*int(height*dpi/72+1)>max_page_pixels:
                    raise PdfValidationError('Rendered page exceeds pixel limit')
        output.mkdir(parents=True,exist_ok=False)
        manifest=dict(source_sha256=digest,bytes=len(data),page_count=count,
            dpi=dpi,state='processing',pages=[],note='Review extracted text against pixels. Routing does not prove usable OCR or reading order.')
        manifest_path=output/'manifest.json'
        manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        try:
            for number in range(count):
                with closing(document[number]) as page:
                    with closing(page.get_textpage()) as textpage: text=textpage.get_text_bounded()
                    with closing(page.render(scale=dpi/72)) as bitmap:
                        image=bitmap.to_pil().convert('RGB')
                        image_name=f'page-{number+1:03d}.png'
                        image.save(output/image_name);size=image.size;image.close()
                text_name=f'page-{number+1:03d}.txt'
                (output/text_name).write_text(text,encoding='utf-8')
                characters=sum(not c.isspace() for c in text)
                manifest['pages'].append(dict(page=number+1,image=image_name,text=text_name,
                    image_sha256=sha(output/image_name),text_sha256=sha(output/text_name),
                    width=size[0],height=size[1],nonspace_characters=characters,
                    route='text_layer_review' if characters>=20 else 'ocr_or_blank_review'))
            sections=[]
            for item in manifest['pages']:
                text=(output/item['text']).read_text(encoding='utf-8')
                sections.append(f'<section><h2>Page {item["page"]}: {item["route"]}</h2>'
                    f'<div class="page"><img src="{item["image"]}" alt="Original page {item["page"]}">'
                    f'<pre>{html.escape(text) or "No extracted text. Inspect before choosing OCR or blank."}</pre></div></section>')
            template='''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'">
<title>PDF evidence review</title><style>body{font:17px system-ui;max-width:1400px;margin:2rem auto;padding:0 1rem;color:#172c37;background:#fafafa}.page{display:grid;grid-template-columns:1fr 1fr;gap:1rem}img{width:100%;border:1px solid #aaa}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:white;padding:1rem;font:15px monospace}section{margin:2rem 0}@media(max-width:800px){.page{grid-template-columns:1fr}}</style>
<h1>Compare text with its source page</h1><p>Routing is a proposal. Review numbers, missing text, reading order, and blank or scanned pages.</p>'''
            (output/'review.html').write_text(template+'\n'.join(sections),encoding='utf-8')
            manifest['state']='review_required'
        except Exception:
            manifest['state']='failed_partial_bundle';raise
        finally:
            manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        return manifest
    finally: document.close()


def worker_main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args()
    result=prepare_pdf(args.source,args.output)
    print(json.dumps(dict(state=result['state'],pages=result['page_count'],routes=[p['route'] for p in result['pages']])))


if __name__=='__main__': worker_main()
