"""Summarize actual request records without discarding failures or changing strict scores."""
import argparse
import csv
import hashlib
import json
import re
import statistics
from collections import Counter,defaultdict
from pathlib import Path
from evaluate import score


def normalize_power(value):
    if not isinstance(value,str):return value
    match=re.fullmatch(r'([0-9]+)[ \t\r\n\f\v]*V[ \t\r\n\f\v]*DC',value.strip(' \t\r\n\f\v'))
    return f'{int(match[1])} V DC' if match else value


def summarize(run: Path,suite: Path):
    manifest=json.loads((suite/'manifest.json').read_text(encoding='utf-8'))
    targets={c['id']:c['expected'] for c in manifest['cases']}
    paths=sorted(run.glob('[0-9]-*.json'))
    rows=[json.loads(path.read_text(encoding='utf-8')) for path in paths]
    if not rows or len({(r['case_id'],r['repeat']) for r in rows})!=len(rows):raise ValueError('missing or duplicate request records')
    summary=json.loads((run/'summary.json').read_text(encoding='utf-8'))
    if len(rows)!=summary['requests']:raise ValueError('incomplete run')
    tasks=defaultdict(Counter);failures=[];token_counts=[]
    for row in rows:
        task=tasks[row['task']];task['requests']+=1
        task['request_errors']+=int('error' in row)
        content=row.get('response',{}).get('choices',[{'message':{}}])[0]['message'].get('content')
        strict=score(content,targets[row['case_id']])
        if strict['exact']!=row['score']['exact']:raise ValueError('stored score differs from recomputed strict score')
        task['strict_exact']+=strict['exact'];task['invalid_json']+=not strict['json_valid'] and 'error' not in row
        normalized=False
        try:
            actual=json.loads(content);target=dict(targets[row['case_id']])
            if isinstance(actual,dict):
                if 'power' in actual:actual['power']=normalize_power(actual['power'])
                if 'power' in target:target['power']=normalize_power(target['power'])
                normalized=score(json.dumps(actual),target)['exact']
        except (ValueError,TypeError):pass
        task['power_format_normalized']+=normalized
        if not strict['exact']:
            failures.append(dict(case_id=row['case_id'],repeat=row['repeat'],content=content,
                expected=targets[row['case_id']],power_format_only=normalized,
                error=row.get('error'),http_status=row.get('http_status'),error_body=row.get('error_body')))
        usage=row.get('response',{}).get('usage',{})
        if 'prompt_tokens' in usage:token_counts.append(dict(case_id=row['case_id'],repeat=row['repeat'],**usage))
    totals=Counter()
    for task in tasks.values():totals.update(task)
    if totals['strict_exact']!=summary['exact'] or totals['request_errors']!=summary['errors']:
        raise ValueError('summary differs from records')
    successful_times=sorted(row['seconds'] for row in rows if 'error' not in row)
    report=dict(run=run.name,unique_cases=len({r['case_id'] for r in rows}),totals=dict(totals),
        tasks={k:dict(v) for k,v in tasks.items()},failures=failures,token_counts=token_counts,
        hashes={path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
        caveat='Strict score unchanged. Power-only normalization was prespecified before27B/122B, post hoc for earlier8B/2B. Repeated cases are not independent. Timings may include repeated-input caches.')
    if successful_times:report['successful_request_seconds']=dict(median=statistics.median(successful_times),
        p95_order_statistic=successful_times[int(.95*(len(successful_times)-1))],count=len(successful_times))
    samples=run/'gpu-samples.csv'
    if samples.exists():
        with samples.open() as stream:values=[int(r[' memory.used [MiB]']) for r in csv.DictReader(stream)]
        report['sampled_total_device_mib']=dict(min=min(values),max=max(values),samples=len(values),
            note='200ms sampling can miss peaks; includes reservations and other activity, not a minimum GPU size.')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--suite',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();report=summarize(args.run,args.suite)
    with args.output.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2)
    print(json.dumps(dict(run=report['run'],totals=report['totals'],memory=report.get('sampled_total_device_mib')),indent=2))
