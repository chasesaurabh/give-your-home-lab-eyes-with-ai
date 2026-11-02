"""Prepare/review or launch a loopback-only server using a selected pinned profile.

No model is downloaded or unrelated container stopped. --dry-run prints the
argument list without launching. A Docker launch is not server readiness.
"""
import argparse
import json
import math
import re
import subprocess
from pathlib import Path
from model_profiles import PROFILES

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--profile',choices=PROFILES,required=True)
p.add_argument('--model-path',type=Path,required=True)
p.add_argument('--gpu-fraction',type=float,required=True)
p.add_argument('--context',type=int,default=8192)
p.add_argument('--name',default='homelab-vision-server')
p.add_argument('--alias',default='vision-model')
p.add_argument('--image',default='vllm/vllm-openai:v0.30.0')
p.add_argument('--dry-run',action='store_true')
args=p.parse_args()
if not math.isfinite(args.gpu_fraction) or not .01<=args.gpu_fraction<=.95:p.error('gpu-fraction must be0.01through0.95')
if not 512<=args.context<=131072:p.error('context must be512through131072; only8192is in the initial measured matrix')
if not re.fullmatch(r'homelab-vision-[a-zA-Z0-9_-]+',args.name):p.error('use a homelab-vision- prefixed container name')
if not re.fullmatch(r'[a-zA-Z0-9_.-]{1,80}',args.alias):p.error('alias must be a short local model identifier')
model=args.model_path.resolve(strict=True)
if not model.is_dir() or not (model/'config.json').is_file():p.error('model-path must contain the selected downloaded checkpoint')
profile=PROFILES[args.profile]
command=['docker','run','-d','--name',args.name,'--label','homelab-vision.worker=model','--gpus','all',
    '-p','127.0.0.1:18104:8000','--mount',f'type=bind,source={model},target=/model,readonly',
    '-e','HF_HUB_OFFLINE=1','-e','TRANSFORMERS_OFFLINE=1',args.image,'/model',
    '--served-model-name',args.alias,'--max-model-len',str(args.context),
    '--gpu-memory-utilization',str(args.gpu_fraction),'--max-num-seqs','1','--enforce-eager',*profile['extra']]
print(json.dumps(dict(profile=profile,command=command,
    notice='Verify the mounted checkpoint identity. Memory fraction is device-relative, not a minimum GPU claim.'),indent=2))
if not args.dry_run:
    if subprocess.run(['docker','inspect',args.name],capture_output=True).returncode==0:
        p.error('named container already exists; inspect it rather than recreating')
    subprocess.run(command,check=True)
    print('Container launched. Inspect docker logs and the advertised model endpoint before inference.')
