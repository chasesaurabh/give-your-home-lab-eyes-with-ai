"""Compare declared full/overview/known-template crop recipes on original fixtures."""
import argparse,csv,hashlib,io,json,re,shutil,subprocess,time,uuid
from collections import defaultdict
from pathlib import Path
from PIL import Image
from homelab_vision.image import normalize_image

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def parse_tsv(text):
    lines={}
    for row in csv.DictReader(io.StringIO(text),delimiter='\t'):
        if row.get('level')=='5' and row.get('text','').strip():
            key=tuple(row[k] for k in ['page_num','block_num','par_num','line_num'])
            lines.setdefault(key,[]).append(row['text'])
    return [' '.join(words) for words in lines.values()]

def extract(lines):
    candidates=defaultdict(list)
    for line in lines:
        match=re.fullmatch(r'\s*(asset[_ ]id|model|ports|power)\s*:\s*(.*?)\s*',line)
        if match:candidates[match[1].replace(' ','_')].append(match[2])
    fields={key:values[0] if len(values)==1 else None for key in ['asset_id','model','ports','power']
            for values in [candidates[key]]}
    value=fields['ports'];fields['ports']=int(value) if value is not None and re.fullmatch(r'[0-9]+',value) else None
    if fields['power'] is not None:fields['power']=' '.join(fields['power'].split())
    return fields

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--suite',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--image',default='homelab-vision-tools');args=p.parse_args()
    manifest=json.loads((args.suite/'manifest.json').read_text(encoding='utf-8'))
    cases=[c for c in manifest['cases'] if c['task'] in {'clear','small_text'}]
    if len(cases)!=12:raise ValueError('Expected the declared six clear and six small-text fixtures')
    image_id=subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'],text=True).strip()
    version=subprocess.run(['docker','run','--rm','--network','none','--read-only','--user','10001:10001',
        '--entrypoint','tesseract',args.image,'--version'],capture_output=True,text=True,check=True,timeout=60).stdout.splitlines()[0]
    args.output.mkdir(parents=True,exist_ok=False)
    record=dict(state='processing',engine=version,image_id=image_id,psm=6,language='eng',crop=[100,160,650,445],
        note='Known-template crop, not automatic detection.12synthetic fixtures,3recipes,one OCR job each. Elapsed time includes Docker startup.',
        suite_sha256=digest(args.suite/'manifest.json'),results=[])
    try:
        for case in cases:
            info=case['images'][0];source=(args.suite/info['path']).resolve(strict=True)
            if not source.is_relative_to(args.suite.resolve()) or digest(source)!=info['sha256']:raise ValueError('Source identity mismatch')
            directory=args.output/case['id'];directory.mkdir()
            original=directory/'original.png';shutil.copy2(source,original)
            overview=normalize_image(source,directory/'normalized',max_edge=320)
            with Image.open(original) as im:
                if im.size!=(960,640) or im.mode!='RGB' or im.getexif().get(274,1)!=1:raise ValueError('Unexpected source geometry')
                crop=directory/'crop.png';im.crop((100,160,650,445)).save(crop)
            for recipe,path in [('original',original),('overview',overview.output_path),('crop',crop)]:
                with Image.open(path) as im:dimensions=list(im.size)
                name='homelab-ocr-compare-'+uuid.uuid4().hex[:12]
                command=['docker','run','--rm','--name',name,'--network','none','--read-only','--cap-drop','ALL',
                    '--security-opt','no-new-privileges','--pids-limit','128','--memory','2g','--cpus','2',
                    '--user','10001:10001','--tmpfs','/tmp:rw,noexec,nosuid,size=256m',
                    '--mount',f'type=bind,source={path.resolve()},target=/input.png,readonly',
                    '--entrypoint','tesseract',args.image,'/input.png','stdout','-l','eng','--psm','6','tsv']
                row=dict(case_id=case['id'],condition=case['task'],recipe=recipe,source_sha256=info['sha256'],
                    image=path.relative_to(args.output).as_posix(),image_sha256=digest(path),dimensions=dimensions,expected=case['expected'])
                start=time.perf_counter()
                try:
                    result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',check=True,timeout=60)
                    (directory/f'{recipe}.tsv').write_text(result.stdout,encoding='utf-8')
                    (directory/f'{recipe}-stderr.txt').write_text(result.stderr,encoding='utf-8')
                    row['lines']=parse_tsv(result.stdout);row['fields']=extract(row['lines'])
                    row['correct_fields']={key:row['fields'][key]==value for key,value in case['expected'].items()}
                    row['exact']=all(row['correct_fields'].values())
                except (subprocess.CalledProcessError,subprocess.TimeoutExpired) as error:
                    subprocess.run(['docker','stop','--time','5',name],capture_output=True,timeout=20)
                    row['error_type']=type(error).__name__;row['exact']=False
                    row['correct_fields']={key:False for key in case['expected']}
                    for key in ['stdout','stderr']:
                        value=getattr(error,key,None) or ''
                        if isinstance(value,bytes):value=value.decode('utf-8',errors='replace')
                        (directory/f'{recipe}-failed-{key}.txt').write_text(value,encoding='utf-8')
                row['seconds_including_container']=time.perf_counter()-start
                record['results'].append(row)
                (args.output/'results.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
                print(json.dumps({k:row[k] for k in ['case_id','recipe','exact']}),flush=True)
        record['state']='completed'
    finally:(args.output/'results.json').write_text(json.dumps(record,indent=2),encoding='utf-8')

if __name__=='__main__':main()
