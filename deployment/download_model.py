"""Acquire the pinned public small model; no weights or credentials belong in Git."""
import argparse
from pathlib import Path
from huggingface_hub import snapshot_download

p=argparse.ArgumentParser()
p.add_argument('--output',type=Path,required=True)
args=p.parse_args()
snapshot_download('Qwen/Qwen3.5-2B',revision='15852e8c16360a2fea060d615a32b45270f8a8fc',
    local_dir=args.output,token=False,max_workers=4,
    allow_patterns=['*.json','*.safetensors','*.txt','*.jinja','*.model','README.md','LICENSE*'])
