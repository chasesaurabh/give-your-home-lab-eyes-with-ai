"""Verify public fixture/response hashes and recompute all strict scores offline."""
import argparse
import hashlib
import json
from pathlib import Path
from evaluate import score

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--study',type=Path,default=Path(__file__).resolve().parents[1]/'studies/initial-vision-2026-11-02')
root=p.parse_args().study.resolve(strict=True)
hashes=json.loads((root/'sha256.json').read_text())
for name,digest in hashes.items():
    path=(root/name).resolve(strict=True)
    if not path.is_relative_to(root):raise ValueError('Manifest path escapes study')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError(f'Hash mismatch: {name}')
for run in sorted((root/'runs').iterdir()):
    config=json.loads((run/'configuration.json').read_text())
    manifest=root/'inputs'/config['input_suite']/'manifest.json'
    assert hashlib.sha256(manifest.read_bytes()).hexdigest()==config['suite_sha256']
    expected={case['id']:case['expected'] for case in json.loads(manifest.read_text())['cases']}
    rows=[json.loads(path.read_text()) for path in sorted(run.glob('[0-9]-*.json'))]
    assert len({(r['case_id'],r['repeat']) for r in rows})==len(rows)==len(expected)*3
    exact=0
    for row in rows:
        checked=score(row['response']['choices'][0]['message']['content'],expected[row['case_id']])
        assert checked['exact']==row['score']['exact'],row['case_id']
        exact+=checked['exact']
    summary=json.loads((run/'summary.json').read_text())
    assert exact==summary['exact'] and len(rows)==summary['requests']
    print(json.dumps(dict(run=run.name,requests=len(rows),strict_exact=exact,hashes_verified=True)))
