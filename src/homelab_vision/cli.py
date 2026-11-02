"""Reader-facing commands. All model output is a proposal requiring review."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from .document import ingest_markdown
from .image import normalize_image
from .provider import LocalVisionClient
from .retrieval import LexicalIndex
from .tasks import TASKS


def write_new(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, default=str, ensure_ascii=False)
        stream.write("\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    analyze = commands.add_parser("analyze", help="Normalize one image and save a model proposal")
    analyze.add_argument("image", type=Path)
    analyze.add_argument("--task", choices=TASKS, required=True)
    analyze.add_argument("--model", required=True)
    analyze.add_argument("--base", default="http://127.0.0.1:18104")
    analyze.add_argument("--output", type=Path, required=True, help="New directory; existing results never overwritten")
    analyze.add_argument("--max-edge", type=int, default=1600)
    search = commands.add_parser("search-text", help="Search deliberately selected UTF-8 Markdown files")
    search.add_argument("query")
    search.add_argument("files", nargs="+", type=Path)
    search.add_argument("--top-k", type=int, default=5)
    pdf = commands.add_parser("prepare-pdf", help="Render page evidence and propose text/OCR routes")
    pdf.add_argument("source", type=Path)
    pdf.add_argument("--output", type=Path, required=True)
    ocr = commands.add_parser("ocr-pages", help="Run local Tesseract on a verified page bundle")
    ocr.add_argument("bundle", type=Path)
    ocr.add_argument("--output", type=Path, required=True)
    ocr.add_argument("--tesseract", default="tesseract")
    ocr.add_argument("--psm", type=int, choices=[3,6,11], default=3)
    args = parser.parse_args(argv)
    if args.command == "analyze":
        if not 64 <= args.max_edge <= 4096:
            parser.error("max-edge must be between 64 and 4096")
        args.output.mkdir(parents=True, exist_ok=False)
        normalized = normalize_image(args.image, args.output / "images", max_edge=args.max_edge)
        # The persisted evidence uses only the generated derivative name, not a private input path.
        transform = asdict(normalized.transform)
        write_new(args.output / "input.json", dict(source_sha256=normalized.source_sha256,
            normalized_sha256=normalized.output_sha256,
            image="images/" + normalized.output_path.name, transform=transform, task=args.task))
        prompt, schema = TASKS[args.task]
        reply = LocalVisionClient(args.model, args.base).analyze([normalized.output_path], prompt, schema)
        write_new(args.output / "proposal.json", dict(status="review_required", task=args.task,
            model=args.model, seconds=reply.seconds, fields=reply.value,
            source_sha256=normalized.source_sha256, image_sha256=normalized.output_sha256,
            prompt=prompt, schema=schema, provider_response=reply.raw,
            notice="Schema validation checks structure, not factual correctness. Compare every field with the image."))
        print(json.dumps(dict(status="review_required", fields=reply.value), indent=2))
    elif args.command == "search-text":
        if len(args.files) > 100:
            parser.error("Select at most 100 files")
        chunks = tuple(chunk for n, path in enumerate(args.files)
                       for chunk in ingest_markdown(path, f"document-{n+1}"))
        hits = LexicalIndex(chunks).search(args.query, top_k=args.top_k)
        print(json.dumps(dict(status="found" if hits else "not_found", hits=[
            dict(score=hit.score, text=hit.chunk.text, source=asdict(hit.chunk.source),
                 instruction_like=hit.chunk.instruction_like) for hit in hits]), indent=2))
    elif args.command == "prepare-pdf":
        # Process timeout bounds normal hangs. This is not an OS security sandbox.
        subprocess.run([sys.executable, "-m", "homelab_vision.pdf", str(args.source), str(args.output)],
                       check=True, timeout=120)
    elif args.command == "ocr-pages":
        from .ocr import ocr_bundle
        result = ocr_bundle(args.bundle,args.output,executable=args.tesseract,psm=args.psm)
        print(json.dumps(dict(state=result['state'],pages=len(result['pages']),engine=result['engine'])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
