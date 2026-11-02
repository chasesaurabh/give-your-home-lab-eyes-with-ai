"""Order-independent, exact-character diagram scoring; no graph repair."""
import argparse,json
from collections import Counter
from pathlib import Path

ARRAY_FIELDS=('nodes','directed_edges','undirected_edges','dashed_edges','group_membership')


def score_diagram(content, expected):
    try:value=json.loads(content)
    except (ValueError,TypeError):return dict(json_valid=False,exact=False,correct_fields={},differences={})
    if not isinstance(value,dict):return dict(json_valid=True,exact=False,correct_fields={},differences={})
    correct={};differences={}
    for key,target in expected.items():
        actual=value.get(key)
        if key in ARRAY_FIELDS:
            valid=isinstance(actual,list) and all(type(item) is str for item in actual)
            correct[key]=valid and len(actual)==len(set(actual)) and set(actual)==set(target)
            if valid:
                a,t=Counter(actual),Counter(target)
                differences[key]=dict(missing=sorted((t-a).elements()),extra=sorted((a-t).elements()))
            else:differences[key]=dict(invalid_type=True)
        else:correct[key]=type(actual) is type(target) and actual==target
    extra_keys=sorted(set(value)-set(expected))
    return dict(json_valid=True,exact=all(correct.values()) and not extra_keys,
                correct_fields=correct,differences=differences,extra_keys=extra_keys)


def summarize(suite,run):
    manifest=json.loads((suite/'manifest.json').read_text(encoding='utf-8'))
    cases={case['id']:case for case in manifest['cases']}
    environment=json.loads((run/'environment.json').read_text(encoding='utf-8'))
    expected={(case,repeat) for case in cases for repeat in range(environment['repeats'])}
    records=[json.loads(path.read_text(encoding='utf-8')) for path in sorted(run.glob('[0-9]*-*.json'))]
    if len(records)!=len(expected) or {(row['case_id'],row['repeat']) for row in records}!=expected:
        raise ValueError('Run incomplete or duplicated; do not summarize as a complete study')
    result=[]
    for row in records:
        value=score_diagram(None if 'error' in row else row['response']['choices'][0]['message']['content'],cases[row['case_id']]['expected'])
        result.append(dict(case_id=row['case_id'],repeat=row['repeat'],seconds=row['seconds'],
                           error='error' in row,order_sensitive_exact=row['score']['exact'],score=value))
    return dict(model=environment['model'],requests=len(result),exact=sum(row['score']['exact'] for row in result),
                request_errors=sum(row['error'] for row in result),
                field_correct={key:sum(row['score']['correct_fields'].get(key,False) for row in result) for key in cases[next(iter(cases))]['expected']},
                records=result,note='Array order ignored; duplicates, changed characters and extra keys are not repaired. Paired resolutions and repeated pixels are not independent cases.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--suite',type=Path,required=True)
    parser.add_argument('--run',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=summarize(args.suite,args.run)
    with args.output.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2)
    print(json.dumps({key:report[key] for key in ['model','requests','exact','request_errors','field_correct']}))
