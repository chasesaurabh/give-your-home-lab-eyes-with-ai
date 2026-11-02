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
    video = commands.add_parser("prepare-video", help="Decode bounded video samples with source timestamps")
    video.add_argument("source", type=Path)
    video.add_argument("--output", type=Path, required=True)
    video.add_argument("--interval", type=float, default=1.0)
    avideo = commands.add_parser("analyze-video", help="Describe each verified sampled frame as a review proposal")
    avideo.add_argument("bundle", type=Path)
    avideo.add_argument("--output", type=Path, required=True)
    avideo.add_argument("--model", required=True)
    avideo.add_argument("--base", default="http://127.0.0.1:18104")
    svideo = commands.add_parser("search-video", help="Search frame proposals with source timestamps")
    svideo.add_argument("query")
    svideo.add_argument("analysis",type=Path)
    summary = commands.add_parser("summarize-video",help="Group observed frame transcriptions without inferring continuity")
    summary.add_argument("analysis",type=Path)
    idoc = commands.add_parser("index-document", help="Create page-cited text/OCR search evidence")
    idoc.add_argument("bundle",type=Path)
    idoc.add_argument("--ocr",type=Path)
    idoc.add_argument("--output",type=Path,required=True)
    sdoc = commands.add_parser("search-document",help="Retrieve PDF excerpts with page citations")
    sdoc.add_argument("query")
    sdoc.add_argument("index",type=Path)
    sdoc.add_argument("--top-k",type=int,default=5)
    adoc = commands.add_parser("ask-document",help="Retrieve up to two PDF pages and save a cited answer proposal")
    adoc.add_argument("question")
    adoc.add_argument("index",type=Path)
    adoc.add_argument("--output",type=Path,required=True)
    adoc.add_argument("--model",required=True)
    adoc.add_argument("--base",default="http://127.0.0.1:18104")
    inventory = commands.add_parser('inventory', help='Review, commit, export and roll back local inventory')
    inventory.add_argument('--database',type=Path,required=True)
    actions = inventory.add_subparsers(dest='action',required=True)
    actions.add_parser('init')
    draft = actions.add_parser('prepare')
    draft.add_argument('analysis',type=Path)
    draft.add_argument('--output',type=Path,required=True)
    draft.add_argument('--item-id',required=True)
    draft.add_argument('--class',dest='equipment_class',required=True)
    inspect = actions.add_parser('inspect')
    inspect.add_argument('review',type=Path)
    commit = actions.add_parser('commit')
    commit.add_argument('review',type=Path)
    commit.add_argument('--confirm-digest',required=True)
    commit.add_argument('--reviewer',required=True)
    actions.add_parser('export')
    undo = actions.add_parser('rollback')
    undo.add_argument('--event-id',type=int,required=True)
    undo.add_argument('--reviewer',required=True)
    undo.add_argument('--confirm',action='store_true')
    backup = actions.add_parser('backup')
    backup.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(argv)
    if args.command == 'inventory':
        from . import inventory_app as app
        if args.action == 'init':
            app.initialize(args.database)
            result = dict(state='initialized')
        elif args.action == 'prepare':
            result = app.prepare(args.analysis,args.database,args.output,args.item_id,args.equipment_class)
        elif args.action == 'inspect':
            result = app.inspect_review(args.review,args.database)
        elif args.action == 'commit':
            result = app.commit_review(args.review,args.database,args.confirm_digest,args.reviewer)
        elif args.action == 'export':
            result = app.export_inventory(args.database)
        elif args.action == 'rollback':
            result = app.undo(args.database,args.event_id,args.reviewer,args.confirm)
        else:
            result = app.backup(args.database,args.output)
        print(json.dumps(result,indent=2))
    elif args.command == "analyze":
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
        try:
            reply = LocalVisionClient(args.model, args.base).analyze([normalized.output_path], prompt, schema)
        except Exception as error:
            write_new(args.output / 'failure.json',dict(state='failed',model=args.model,prompt=prompt,schema=schema,
                error_type=type(error).__name__,message=str(error),details=getattr(error,'details',{})))
            raise
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
    elif args.command == "prepare-video":
        from .video_decode import decode_video
        result = decode_video(args.source, args.output, interval=args.interval)
        print(json.dumps(dict(state=result['state'],frames=len(result['frames']))))
    elif args.command == "analyze-video":
        from .video_analysis import analyze_frames
        result = analyze_frames(args.bundle,args.output,args.model,args.base)
        print(json.dumps(dict(state=result['state'],frames=len(result['frames']))))
    elif args.command == "search-video":
        from .video_analysis import search_frames
        print(json.dumps(search_frames(args.analysis,args.query),indent=2))
    elif args.command == "summarize-video":
        from .video_analysis import summarize_frames
        print(json.dumps(summarize_frames(args.analysis),indent=2))
    elif args.command == "index-document":
        from .document_app import index_document
        result=index_document(args.bundle,args.output,args.ocr)
        print(json.dumps(dict(state=result['state'],pages=len(result['pages']))))
    elif args.command == "search-document":
        from .document_app import search_document
        print(json.dumps(search_document(args.index,args.query,args.top_k),indent=2))
    elif args.command == "ask-document":
        from .document_app import ask_document
        result=ask_document(args.index,args.question,args.output,args.model,args.base)
        print(json.dumps({key:result[key] for key in ['state','answer','cited_pages']},indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
