"""Decode one deliberately selected local clip in a restricted CPU worker."""
import argparse
import json
import math
import subprocess
import uuid
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--interval',type=float,default=1)
p.add_argument('--image',default='homelab-vision-tools')
args=p.parse_args()
source=args.source.resolve(strict=True)
if not source.is_file() or not 0<source.stat().st_size<=256_000_000:p.error('Select one local video up to 256 MB')
if not math.isfinite(args.interval) or args.interval<.1:p.error('interval must be at least 0.1 seconds')
code=Path(__file__).resolve().parents[1]
image_id=subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'],text=True).strip()
output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
name='homelab-video-'+uuid.uuid4().hex[:12]
command=['docker','run','--rm','--name',name,'--label','homelab-vision.worker=video',
    '--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
    '--pids-limit','128','--memory','2g','--cpus','2','--user','10001:10001',
    '--tmpfs','/tmp:rw,noexec,nosuid,size=512m',
    '--mount',f'type=bind,source={code},target=/code,readonly',
    '--mount',f'type=bind,source={source},target=/input/clip,readonly',
    '--mount',f'type=bind,source={output},target=/out',args.image,
    'prepare-video','/input/clip','--interval',str(args.interval),'--output','/out/result']
record=dict(image_id=image_id,container_name=name,network='none',user='10001:10001',
    memory_limit='2g',cpus=2,interval_seconds=args.interval)
try:
    subprocess.run(command,check=True,timeout=420)
    record['status']='completed'
except BaseException:
    record['status']='failed_or_interrupted'
    try:subprocess.run(['docker','stop','--time','5',name],capture_output=True,timeout=20)
    except (OSError,subprocess.TimeoutExpired):pass
    raise
finally:
    (output/'runtime.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
