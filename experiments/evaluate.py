"""Record actual local model responses; strict field scoring is not semantic truth."""
import argparse
import base64
import hashlib
import json
import random
import time
import urllib.request
import atexit
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

def score(content, expected):
    try: value=json.loads(content)
    except (ValueError,TypeError): return dict(json_valid=False,correct_fields=0,total_fields=len(expected),exact=False)
    if not isinstance(value,dict): return dict(json_valid=True,correct_fields=0,total_fields=len(expected),exact=False)
    def matches(actual, target):
        # JSON numeric values such as 72 and 72.0 have the same value.
        # Booleans must never pass as integers despite Python equality rules.
        if type(target) in (int,float):
            return type(actual) in (int,float) and actual==target
        return type(actual) is type(target) and actual==target
    count=sum(matches(value.get(k),v) for k,v in expected.items())
    return dict(json_valid=True,correct_fields=count,total_fields=len(expected),exact=count==len(expected) and set(value)==set(expected),
                abstained_fields=sum(value.get(k) is None for k in expected),extra_keys=sorted(set(value)-set(expected)))

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise ValueError('Research endpoint redirects are disabled')

def request(base,path,payload=None):
    req=urllib.request.Request(base+path,data=None if payload is None else json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    with opener.open(req,timeout=240) as r:
        body=r.read(2_000_001)
        if len(body)>2_000_000: raise ValueError('Response exceeded byte limit')
        return json.loads(body)

def field_schema(expected):
    """Use field names/types only; no target values are sent in the schema."""
    kinds={str:'string',int:'integer',float:'number',bool:'boolean'}
    return dict(type='object',properties={key:dict(type=[kinds[type(value)],'null'])
        for key,value in expected.items()},required=list(expected),additionalProperties=False)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--suite',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--base',default='http://127.0.0.1:18104')
    p.add_argument('--model',required=True)
    p.add_argument('--repeats',type=int,default=3)
    p.add_argument('--wait-ready',type=int,default=0,help='Seconds to wait for the existing endpoint; never starts or restarts it')
    p.add_argument('--structured',action='store_true',help='Separate schema-constrained lane; never mix with prompt-only results')
    p.add_argument('--sample-gpu',action='store_true',help='Sample total-device memory at 200 ms; not exact allocation or minimum GPU requirement')
    args=p.parse_args()
    endpoint=urlsplit(args.base)
    if (endpoint.scheme!='http' or endpoint.hostname not in ['127.0.0.1','::1'] or endpoint.username or endpoint.password
            or endpoint.query or endpoint.fragment or endpoint.path not in ['', '/']):
        p.error('This harness requires an HTTP loopback literal with no credentials, path, query or fragment')
    args.base=args.base.rstrip('/')
    if args.repeats<1: p.error('repeats must be positive')
    manifest_path=args.suite/'manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    for case in manifest['cases']:
        for image in case['images']:
            path=(args.suite/image['path']).resolve()
            if not path.is_relative_to(args.suite.resolve()): raise ValueError('Fixture path escapes suite')
            if hashlib.sha256(path.read_bytes()).hexdigest()!=image['sha256']: raise ValueError('Fixture hash mismatch')
    deadline=time.monotonic()+args.wait_ready
    while True:
        try:
            provider=request(args.base,'/v1/models')
            if args.model not in [m['id'] for m in provider.get('data',[])]:
                raise ValueError('Endpoint does not advertise requested model identity')
            break
        except (OSError,ValueError):
            if time.monotonic()>=deadline: raise
            print('Waiting for requested model endpoint',flush=True)
            time.sleep(10)
    args.output.mkdir(parents=True,exist_ok=False)
    metadata=dict(timestamp=datetime.now(timezone.utc).isoformat(),suite_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        evaluator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),provider=provider,
        model=args.model,repeats=args.repeats,temperature=0,max_tokens=256,
        output_mode='json-schema' if args.structured else 'prompt-only',
        cache_policy='Server defaults; record server configuration. Repeated input may use prefix/multimodal caching.')
    (args.output/'environment.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    sampler=None
    if args.sample_gpu:
        sample_file=(args.output/'gpu-samples.csv').open('w',encoding='utf-8')
        sample_error=(args.output/'gpu-sampler-errors.txt').open('w',encoding='utf-8')
        sampler=subprocess.Popen(['nvidia-smi','--query-gpu=timestamp,index,memory.total,memory.used,utilization.gpu,temperature.gpu',
            '--format=csv,nounits','-lms','200'],stdout=sample_file,stderr=sample_error)
        def stop_sampler():
            if sampler.poll() is None:
                sampler.terminate(); sampler.wait(timeout=10)
            sample_file.close(); sample_error.close()
        atexit.register(stop_sampler)
    records=[]
    for repeat in range(args.repeats):
        cases=list(manifest['cases']); random.Random(739+repeat).shuffle(cases)
        for case in cases:
            content=[{'type':'text','text':case['prompt']}]
            for image in case['images']:
                data=base64.b64encode((args.suite/image['path']).read_bytes()).decode()
                content.append({'type':'image_url','image_url':{'url':'data:image/png;base64,'+data}})
            payload=dict(model=args.model,messages=[{'role':'user','content':content}],temperature=0,max_tokens=256)
            if args.structured:
                schema=case.get('schema') or field_schema(case['expected'])
                payload['response_format']={'type':'json_schema','json_schema':{'name':'fields','strict':True,'schema':schema}}
            start=time.perf_counter()
            result=dict(case_id=case['id'],task=case['task'],repeat=repeat,prompt=case['prompt'],image_hashes=[im['sha256'] for im in case['images']],
                started_utc=datetime.now(timezone.utc).isoformat(),response_format=payload.get('response_format'))
            try:
                response=request(args.base,'/v1/chat/completions',payload)
                result.update(response=response,score=score(response['choices'][0]['message']['content'],case['expected']))
            except Exception as exc: result.update(error=str(exc),score=dict(exact=False,correct_fields=0,total_fields=len(case['expected'])))
            result['seconds']=time.perf_counter()-start
            (args.output/f'{repeat}-{case["id"]}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
            records.append(result)
            print(json.dumps({k:result[k] for k in ['case_id','repeat','seconds','score']}),flush=True)
    summary=dict(requests=len(records),exact=sum(r['score']['exact'] for r in records),errors=sum('error' in r for r in records),
        split=manifest['split'],note='Controlled synthetic task results, not general accuracy. Strict JSON/field score; inspect raw outputs and failure types.')
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    if sampler is not None:
        sample_status=sampler.poll()
        stop_sampler(); atexit.unregister(stop_sampler)
        (args.output/'gpu-sampler-status.json').write_text(json.dumps(dict(interval_ms=200,
            unexpected_exit_code=sample_status,note='Total device including other processes; sampling can miss brief peaks. Reservation is not minimum memory.')))
    print(json.dumps(summary))

if __name__=='__main__': main()
