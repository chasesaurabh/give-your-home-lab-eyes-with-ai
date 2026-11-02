"""Verify the recorded OCR preprocessing study offline; no Docker or model."""
import argparse,hashlib,json
from collections import defaultdict
from pathlib import Path
from PIL import Image, ImageChops
from compare_label_ocr import extract, parse_tsv


def verify(root):
    root=root.resolve(strict=True)
    hashes=json.loads((root/'sha256.json').read_text(encoding='utf-8'))
    for name,digest in hashes.items():
        path=(root/name).resolve(strict=True)
        if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError(f'Artifact hash mismatch: {name}')
    manifest=root/'inputs/labels/manifest.json'
    source=json.loads(manifest.read_text(encoding='utf-8'))
    data=json.loads((root/'run/results.json').read_text(encoding='utf-8'))
    raw=json.loads((root/'raw-ocr.json').read_text(encoding='utf-8'))
    if data['state']!='completed' or data['suite_sha256']!=hashlib.sha256(manifest.read_bytes()).hexdigest():
        raise ValueError('Incomplete run or source manifest mismatch')
    cases={c['id']:c for c in source['cases'] if c['task'] in {'clear','small_text'}}
    required={(case,recipe) for case in cases for recipe in ('original','overview','crop')}
    if len(cases)!=12 or len(data['results'])!=36 or {(r['case_id'],r['recipe']) for r in data['results']}!=required:
        raise ValueError('Missing or duplicate declared jobs')
    groups=defaultdict(lambda:dict(records=0,exact=0,correct_fields=0,errors=0))
    for row in data['results']:
        case=cases[row['case_id']];recipe=row['recipe'];item=case['images'][0]
        if row['expected']!=case['expected'] or row['source_sha256']!=item['sha256'] or row['condition']!=case['task']:
            raise ValueError('Input or ground truth mismatch')
        original=root/'inputs/labels'/item['path'];image=root/'run'/row['image']
        if hashlib.sha256(original.read_bytes()).hexdigest()!=item['sha256'] or hashlib.sha256(image.read_bytes()).hexdigest()!=row['image_sha256']:
            raise ValueError('Pixel artifact identity mismatch')
        expected_size={'original':(960,640),'overview':(320,213),'crop':(550,285)}[recipe]
        with Image.open(image) as pixels:
            if pixels.size!=expected_size or list(pixels.size)!=row['dimensions']:raise ValueError('Wrong geometry')
            with Image.open(original) as source_image:
                if recipe=='original' and ImageChops.difference(pixels,source_image).getbbox():raise ValueError('Original differs')
                if recipe=='crop' and ImageChops.difference(pixels,source_image.crop((100,160,650,445))).getbbox():
                    raise ValueError('Crop differs from declared original pixels')
        lines=parse_tsv(raw[f'{row["case_id"]}/{recipe}']['stdout']);fields=extract(lines)
        correct={key:fields[key]==value for key,value in case['expected'].items()}
        if lines!=row['lines'] or fields!=row['fields'] or correct!=row['correct_fields'] or all(correct.values())!=row['exact']:
            raise ValueError('Stored scoring does not match raw TSV')
        group=groups[f'{case["task"]}/{recipe}'];group['records']+=1
        group['exact']+=all(correct.values());group['correct_fields']+=sum(correct.values())
    if dict(groups)!=json.loads((root/'summary.json').read_text()):raise ValueError('Summary mismatch')
    return dict(hashes_verified=len(hashes),jobs_rescored=36,groups=dict(groups))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',type=Path,default=Path(__file__).resolve().parents[1]/'studies/ocr-preprocessing-2026-11-02')
    print(json.dumps(verify(parser.parse_args().study),indent=2))
