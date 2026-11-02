"""Run a local Tesseract baseline on verified PDF page derivatives."""
import csv
import hashlib
import io
import json
import subprocess
from pathlib import Path
from PIL import Image


def ocr_bundle(bundle: Path, output: Path, *, executable='tesseract', psm=3):
    if psm not in {3,6,11}: raise ValueError('Choose a supported segmentation mode: 3, 6 or 11')
    bundle=bundle.resolve(strict=True)
    manifest=json.loads((bundle/'manifest.json').read_text(encoding='utf-8'))
    if manifest['state']!='review_required' or not 1<=len(manifest['pages'])<=40:
        raise ValueError('A complete bounded page bundle is required')
    images=[]
    for page in manifest['pages']:
        path=(bundle/page['image']).resolve(strict=True)
        if not path.is_relative_to(bundle): raise ValueError('Page path escapes bundle')
        if path.stat().st_size>20_000_000: raise ValueError('Page bytes exceed limit')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=page['image_sha256']:
            raise ValueError('Page image hash mismatch')
        with Image.open(path) as image:
            if image.format!='PNG' or image.width*image.height>20_000_000 or image.size!=(page['width'],page['height']):
                raise ValueError('Invalid page raster')
            image.verify()
        images.append((page,path))
    version=subprocess.run([executable,'--version'],capture_output=True,text=True,check=True,timeout=10)
    output.mkdir(parents=True,exist_ok=False)
    record=dict(source_sha256=manifest['source_sha256'],engine=version.stdout.splitlines()[0],
        psm=psm,language='eng',state='processing',pages=[],
        note='Word confidence is an engine score, not probability of correctness. Boxes use rendered-page pixel coordinates.')
    try:
        for page,path in images:
            result=subprocess.run([executable,str(path),'stdout','-l','eng','--psm',str(psm),'tsv'],
                capture_output=True,text=True,encoding='utf-8',check=True,timeout=60)
            raw=output/f'page-{page["page"]:03d}.tsv'
            raw.write_text(result.stdout,encoding='utf-8')
            words=[]
            for row in csv.DictReader(io.StringIO(result.stdout),delimiter='\t'):
                if row.get('level')=='5' and row.get('text','').strip():
                    box=[int(row[k]) for k in ['left','top','width','height']]
                    if (min(box)<0 or box[0]+box[2]>page['width'] or box[1]+box[3]>page['height']):
                        raise ValueError('OCR returned a box outside its source page')
                    words.append(dict(text=row['text'],confidence=float(row['conf']),
                        box=box,
                        block=int(row['block_num']),paragraph=int(row['par_num']),line=int(row['line_num'])))
            record['pages'].append(dict(page=page['page'],image_sha256=page['image_sha256'],
                width=page['width'],height=page['height'],words=words,raw=raw.name))
        record['state']='review_required'
    except Exception:
        record['state']='failed_partial_bundle';raise
    finally:
        (output/'ocr.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    return record
