"""Verify all published diagram inputs and rescore every raw response offline."""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from evaluate import score
from score_diagrams import score_diagram


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def verify(root):
    root=root.resolve(strict=True)
    hashes=read(root/'sha256.json')
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.name!='sha256.json'}
    if actual!=set(hashes):
        raise ValueError('Missing, additional or unhashed study artifact')
    for name,digest in hashes.items():
        path=(root/name).resolve(strict=True)
        if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError('Artifact hash mismatch: '+name)
    totals=[]
    expected_runs={f'{model}-{lane}' for model in ('2b','27b','122b') for lane in ('development','evaluation')}
    if {p.name for p in (root/'runs').iterdir()}!=expected_runs:
        raise ValueError('Missing or unexpected model/lane')
    for run in sorted((root/'runs').iterdir()):
        config=read(run/'configuration.json')
        suite=root/'inputs'/config['input_suite'];manifest=read(suite/'manifest.json')
        if hashlib.sha256((suite/'manifest.json').read_bytes()).hexdigest()!=config['suite_sha256']:
            raise ValueError('Suite identity mismatch')
        if hashlib.sha256((run/'evaluator.py').read_bytes()).hexdigest()!=config['recorded_evaluator_sha256']:
            raise ValueError('Evaluator identity mismatch')
        cases={case['id']:case for case in manifest['cases']}
        if len(cases)!=len(manifest['cases']):raise ValueError('Duplicate source case')
        for case in cases.values():
            for item in case['images']:
                path=(suite/item['path']).resolve(strict=True)
                if not path.is_relative_to(suite.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:
                    raise ValueError('Input image identity mismatch')
        rows=[read(p) for p in sorted(run.glob('[0-9]*-*.json'))]
        pairs={(case,repeat) for case in cases for repeat in range(config['repeats'])}
        if len(rows)!=len(pairs) or {(r['case_id'],r['repeat']) for r in rows}!=pairs:
            raise ValueError('Missing or duplicate request')
        checked=[];groups=defaultdict(lambda:dict(requests=0,exact=0,errors=0))
        for row in rows:
            case=cases[row['case_id']]
            if row['image_hashes']!=[item['sha256'] for item in case['images']] or row['prompt']!=case['prompt']:
                raise ValueError('Recorded request input differs from declared case')
            if row['response_format']['json_schema']['schema']!=case['schema']:
                raise ValueError('Recorded request schema differs from declared case')
            content=None if 'error' in row else row['response']['choices'][0]['message']['content']
            result=score_diagram(content,cases[row['case_id']]['expected'])
            strict=False if 'error' in row else score(content,cases[row['case_id']]['expected'])['exact']
            if strict!=row['score']['exact']:raise ValueError('Stored order-sensitive score differs')
            checked.append(dict(case_id=row['case_id'],repeat=row['repeat'],seconds=row['seconds'],
                                error='error' in row,order_sensitive_exact=strict,score=result))
            group=groups[row['case_id']];group['requests']+=1;group['exact']+=result['exact'];group['errors']+='error' in row
        saved=read(run/'diagram-score.json')
        fields={key:sum(row['score']['correct_fields'].get(key,False) for row in checked)
                for key in next(iter(cases.values()))['expected']}
        if (saved['records']!=checked or saved['field_correct']!=fields or
            saved['exact']!=sum(row['score']['exact'] for row in checked) or
            saved['request_errors']!=sum(row['error'] for row in checked) or saved['requests']!=len(rows)):
            raise ValueError('Primary graph score differs from raw responses')
        summary=read(run/'summary.json')
        if summary['exact']!=sum(row['order_sensitive_exact'] for row in checked) or summary['requests']!=len(rows):
            raise ValueError('Generic summary differs')
        totals.append(dict(run=run.name,requests=len(rows),exact=saved['exact'],errors=saved['request_errors'],
                           fields=fields,by_case=dict(groups)))
    return dict(hashes_verified=len(hashes),runs=totals,
                note='Development and evaluation remain separate. Repeats and paired resolutions are not independent designs.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',type=Path,default=Path(__file__).resolve().parents[1]/'studies/diagrams-2026-11-02')
    print(json.dumps(verify(parser.parse_args().study),indent=2))
