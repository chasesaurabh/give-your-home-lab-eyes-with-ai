"""Portable wrapper for the documented restricted, network-disabled OCR worker."""
import argparse
import json
import subprocess
import uuid
from pathlib import Path

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--bundle',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--image',default='homelab-vision-tools')
args=parser.parse_args()
code=Path(__file__).resolve().parents[1]
bundle=args.bundle.resolve(strict=True)
if not (bundle/'manifest.json').is_file():parser.error('Input must be a completed PDF page bundle')
output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
image_id=subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'],text=True).strip()
container_name='homelab-ocr-'+uuid.uuid4().hex[:12]
command=['docker','run','--rm','--name',container_name,'--label','homelab-vision.worker=ocr','--network','none','--read-only','--cap-drop','ALL',
    '--security-opt','no-new-privileges','--pids-limit','128','--memory','2g','--cpus','2',
    '--user','10001:10001','--tmpfs','/tmp:rw,noexec,nosuid,size=256m',
    '--mount',f'type=bind,source={code},target=/code,readonly',
    '--mount',f'type=bind,source={bundle},target=/input,readonly',
    '--mount',f'type=bind,source={output},target=/out',args.image,
    'ocr-pages','/input','--output','/out/result']
record=dict(image_id=image_id,container_name=container_name,network='none',user='10001:10001',memory_limit='2g',cpus=2,
    input_manifest_sha256=__import__('hashlib').sha256((bundle/'manifest.json').read_bytes()).hexdigest())
try:
    result=subprocess.run(command,check=True,timeout=2500)
    record['status']='completed'
except BaseException:
    record['status']='failed_or_interrupted'
    try: subprocess.run(['docker','stop','--time','5',container_name],capture_output=True,timeout=20)
    except (OSError,subprocess.TimeoutExpired): pass
    raise
finally:
    (output/'runtime.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
