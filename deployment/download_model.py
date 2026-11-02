"""Acquire an explicitly selected pinned public model; weights stay outside Git."""
import argparse
from pathlib import Path
from huggingface_hub import snapshot_download
from model_profiles import PROFILES

p=argparse.ArgumentParser()
p.add_argument('--output',type=Path,required=True)
p.add_argument('--profile',choices=PROFILES,default='2b')
args=p.parse_args()
profile=PROFILES[args.profile]
snapshot_download(profile['repo'],revision=profile['revision'],
    local_dir=args.output,token=False,max_workers=4,
    allow_patterns=['*.json','*.safetensors','*.txt','*.jinja','*.model','README.md','LICENSE*'])
