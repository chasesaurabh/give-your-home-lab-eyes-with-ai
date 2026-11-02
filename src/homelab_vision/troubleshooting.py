"""A source-bearing investigation packet. No command execution or automatic diagnosis."""
from __future__ import annotations
import hashlib
import html
import json
from dataclasses import asdict
from datetime import UTC,datetime
from pathlib import Path
from .document import ingest_markdown
from .retrieval import LexicalIndex
from .document_app import read_json,verified_file


def build_case(analysis: Path, manuals: list[Path], question: str, output: Path) -> dict:
    if not question.strip() or len(question)>2000 or not 1<=len(manuals)<=10:
        raise ValueError('Select 1 to 10 manuals and a question of 1 to 2000 characters')
    source=read_json(analysis/'input.json',2_000_000)
    proposal=read_json(analysis/'proposal.json',2_000_000)
    if proposal.get('task') not in {'screenshot','terminal'} or proposal.get('status')!='review_required':
        raise ValueError('A completed screenshot analysis is required')
    if proposal['source_sha256']!=source['source_sha256'] or proposal['image_sha256']!=source['normalized_sha256']:
        raise ValueError('Screenshot identities disagree')
    _,pixels=verified_file(analysis,source['image'],source['normalized_sha256'],16_000_000)
    output.mkdir(parents=True,exist_ok=False)
    record=dict(state='processing',question=question,created_utc=datetime.now(UTC).isoformat(),
        capture_time='not established by this workflow',source_sha256=source['source_sha256'],
        image_sha256=source['normalized_sha256'],observation=proposal['fields'],manuals=[],hits=[],
        notice='Model observation and retrieved excerpts require review. Retrieval is lexical, not a diagnosis. No actions are executed.')
    try:
        (output/'screenshot.png').write_bytes(pixels)
        (output/'observation.json').write_bytes((analysis/'proposal.json').read_bytes())
        record['observation_sha256']=hashlib.sha256((output/'observation.json').read_bytes()).hexdigest()
        chunks=[]
        for number,path in enumerate(manuals,1):
            # Snapshot deliberately selected UTF-8 files; the index and retained bytes agree.
            with path.open('rb') as stream:data=stream.read(2_000_001)
            if len(data)>2_000_000:raise ValueError('Manual exceeds 2 MB')
            data.decode('utf-8',errors='strict')
            name=f'manual-{number:02d}.md';target=output/name;target.write_bytes(data)
            digest=hashlib.sha256(data).hexdigest()
            record['manuals'].append(dict(id=f'manual-{number:02d}',file=name,sha256=digest))
            chunks.extend(ingest_markdown(target,f'manual-{number:02d}'))
        # Query is explicit, so a misread model identifier cannot silently define the search.
        hits=LexicalIndex(tuple(chunks)).search(question,top_k=5) if chunks else ()
        record['hits']=[dict(text=h.chunk.text,score=h.score,source=asdict(h.chunk.source),
            instruction_like=h.chunk.instruction_like) for h in hits]
        record['state']='review_required' if hits else 'not_found'
        record['review_questions']=[
            'Does the screenshot belong to the intended machine and time?',
            'Does each extracted field match the screenshot pixels?',
            'Does the selected manual apply to the installed version?',
            'Which read-only check could distinguish the remaining explanations?',
            'What result would make you stop rather than change a setting?']
        sections=''.join('<section><h2>'+html.escape(h['source']['fixture_id']+' / '+h['source']['locator'])+
            '</h2><pre>'+html.escape(h['text'])+'</pre><p>Instruction-like text warning: '+str(h['instruction_like'])+'</p></section>' for h in record['hits'])
        page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self'; style-src 'unsafe-inline'">
<title>Review a troubleshooting case</title><style>body{font:17px/1.5 system-ui;max-width:1000px;margin:2rem auto;padding:0 1rem;color:#24313a}img{max-width:100%;height:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere}section{border-top:1px solid #bbc7cc;padding:1rem 0}</style>
<h1>Review the evidence before diagnosing</h1>'''+ '<p>'+html.escape(question)+'</p><img src="screenshot.png" alt="Retained screenshot evidence"><h2>Model observation — unverified</h2><pre>'+html.escape(json.dumps(record['observation'],indent=2))+'</pre><h2>Selected documentation excerpts</h2>'+sections+'<h2>Review questions</h2><ul>'+''.join('<li>'+html.escape(q)+'</li>' for q in record['review_questions'])+'</ul><p>'+html.escape(record['notice'])+'</p></html>'
        (output/'review.html').write_text(page,encoding='utf-8')
    except BaseException:
        record['state']='failed_or_interrupted';raise
    finally:(output/'case.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    return record
