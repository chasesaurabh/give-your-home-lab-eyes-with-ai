"""Collect five labeled invoice fields with separate text/OCR evidence for review.

This is a deliberately narrow, single-column labeled-line parser. It does not
infer tables, accept accounting records, redact documents or call a model.
"""
from __future__ import annotations

import hashlib
import html
import io
import json
import re
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from PIL import Image
from .document_app import read_json, verified_file

LABELS = {'Invoice': 'invoice_id', 'Asset': 'asset_id', 'Quantity': 'quantity',
          'Unit price': 'unit_price', 'Total': 'total'}


def normalize(field, raw):
    if field in {'invoice_id', 'asset_id'}:
        return raw if re.fullmatch(r'[A-Z0-9][A-Z0-9-]{0,79}', raw) else None
    if field == 'quantity':
        return int(raw) if re.fullmatch(r'[1-9][0-9]{0,5}', raw) else None
    match = re.fullmatch(r'([A-Z]{3}) ([0-9]{1,9}\.[0-9]{2})', raw)
    return dict(currency=match[1], amount=match[2]) if match else None


def candidate(line, method, box=None):
    label, separator, raw = line.partition(':')
    if not separator or label not in LABELS:
        return None
    raw = raw.strip()
    field = LABELS[label]
    value = normalize(field, raw)
    return dict(field=field, label=label, raw_text=raw, line_text=line,
                normalized=value, format_ok=value is not None, method=method, box=box)


def ocr_lines(page):
    """Retain engine line membership; union boxes include label and value."""
    groups = defaultdict(list)
    words = page['words']
    if not isinstance(words, list) or len(words) > 100_000:
        raise ValueError('OCR word limit')
    for word in words:
        box = word['box']
        if (len(box) != 4 or any(type(v) is not int or v < 0 for v in box)
                or box[2] == 0 or box[3] == 0
                or box[0] + box[2] > page['width'] or box[1] + box[3] > page['height']):
            raise ValueError('OCR box outside page')
        if not isinstance(word['text'], str) or len(word['text']) > 10000:
            raise ValueError('Invalid OCR text')
        groups[(word['block'], word['paragraph'], word['line'])].append(word)
    result = []
    for group in groups.values():
        left = min(w['box'][0] for w in group)
        top = min(w['box'][1] for w in group)
        right = max(w['box'][0] + w['box'][2] for w in group)
        bottom = max(w['box'][1] + w['box'][3] for w in group)
        result.append((' '.join(w['text'] for w in group), [left, top, right-left, bottom-top]))
    return result


def check_candidates(candidates):
    checks = {}
    selected = {}
    for method in ('direct_text', 'ocr'):
        grouped = {field: [c for c in candidates if c['method'] == method and c['field'] == field]
                   for field in LABELS.values()}
        selected[method] = {field: values[0]['normalized'] if len(values) == 1 else None
                            for field, values in grouped.items()}
        present = [c for c in candidates if c['method'] == method]
        checks[method] = dict(counts={key: len(values) for key, values in grouped.items()},
                              formats_ok=all(c['format_ok'] for c in present) if present else None)
        values = selected[method]
        quantity, unit, total = (values[key] for key in ('quantity', 'unit_price', 'total'))
        arithmetic = 'not_checkable'
        if quantity is not None and unit is not None and total is not None:
            arithmetic = 'pass' if (unit['currency'] == total['currency']
                and Decimal(unit['amount']) * quantity == Decimal(total['amount'])) else 'fail'
        checks[method]['arithmetic'] = arithmetic
    checks['path_agreement'] = {
        field: ('not_comparable' if selected['direct_text'][field] is None or selected['ocr'][field] is None
                else 'agree' if selected['direct_text'][field] == selected['ocr'][field] else 'disagree')
        for field in LABELS.values()}
    return checks


def collect_invoice_fields(bundle: Path, ocr_path: Path, output: Path):
    bundle = bundle.resolve(strict=True)
    source = read_json(bundle/'manifest.json', 2_000_000)
    ocr = read_json(ocr_path, 20_000_000)
    if source.get('state') != 'review_required' or not 1 <= len(source.get('pages', [])) <= 40:
        raise ValueError('Complete bounded page bundle required')
    if ocr.get('state') != 'review_required' or ocr.get('source_sha256') != source['source_sha256']:
        raise ValueError('OCR incomplete or from another PDF')
    ocr_pages = {page['page']: page for page in ocr['pages']}
    numbers = [page['page'] for page in source['pages']]
    if (len(ocr_pages) != len(ocr['pages']) or len(set(numbers)) != len(numbers)
            or set(ocr_pages) != set(numbers)
            or any(type(number) is not int or not 1 <= number <= 40 for number in numbers)):
        raise ValueError('Duplicate or mismatched page identifiers')
    record = dict(state='processing', source_sha256=source['source_sha256'],
                  ocr_record_sha256=hashlib.sha256(ocr_path.read_bytes()).hexdigest(),
                  parser='labeled-invoice-v1', pages=[],
                  notice='All candidates require human review. Agreement and arithmetic do not prove identity or correctness.')
    output.mkdir(parents=True, exist_ok=False)
    try:
        for page in source['pages']:
            _, pixels = verified_file(bundle, page['image'], page['image_sha256'], 20_000_000)
            _, text = verified_file(bundle, page['text'], page['text_sha256'], 2_000_000)
            with Image.open(io.BytesIO(pixels)) as image:
                if (image.format != 'PNG' or image.size != (page['width'], page['height'])
                        or image.width*image.height > 20_000_000):
                    raise ValueError('Invalid page geometry')
                image.verify()
            opage = ocr_pages[page['page']]
            if any(opage[key] != page[key] for key in ('image_sha256', 'width', 'height')):
                raise ValueError('OCR page identity or geometry mismatch')
            candidates = [value for line in text.decode('utf-8').splitlines()
                          if (value := candidate(line, 'direct_text')) is not None]
            candidates.extend(value for line, box in ocr_lines(opage)
                              if (value := candidate(line, 'ocr', box)) is not None)
            name = f'page-{page["page"]:03d}.png'
            (output/name).write_bytes(pixels)
            record['pages'].append(dict(page=page['page'], image=name,
                image_sha256=page['image_sha256'], width=page['width'], height=page['height'],
                candidates=candidates, checks=check_candidates(candidates)))
        record['state'] = 'review_required'
        write_review(record, output)
    except BaseException:
        record['state'] = 'failed_or_interrupted'
        raise
    finally:
        (output/'fields.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    return record


def write_review(record, output):
    escape = html.escape
    sections = []
    for page in record['pages']:
        rows, boxes = [], []
        for number, c in enumerate(page['candidates'], 1):
            if c['box']:
                x, y, w, h = c['box']
                boxes.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}"/>'
                             f'<text x="{max(0,x-26)}" y="{y+h}">{number}</text>')
            rows.append('<tr>'+''.join(f'<td>{escape(str(v))}</td>' for v in
                (number, c['field'], c['method'], c['raw_text'], c['normalized'], c['format_ok']))+'</tr>')
        sections.append(f'<section><h2>Page {page["page"]}</h2>'
            f'<a href="{page["image"]}">Open full retained page</a>'
            f'<svg role="img" aria-label="Source page with numbered OCR line boxes" '
            f'viewBox="0 0 {page["width"]} {page["height"]}">'
            f'<image href="{page["image"]}" width="{page["width"]}" height="{page["height"]}"/>'
            +''.join(boxes)+'</svg><div class="scroll"><table><thead><tr>'
            '<th>#</th><th>Field</th><th>Method</th><th>Raw text</th><th>Normalized</th><th>Format valid</th>'
            '</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'
            '<h3>Checks, not acceptance</h3><pre>'+escape(json.dumps(page['checks'], indent=2))+'</pre></section>')
    document = ('<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Invoice field evidence</title><style>'
        'body{font:17px/1.5 system-ui;max-width:1000px;margin:2rem auto;padding:1rem;color:#17242e}'
        'svg{display:block;width:100%;max-width:600px;border:1px solid #aaa;margin:1rem 0}'
        'rect{fill:none;stroke:#17475f;stroke-width:3}svg text{fill:#17475f;font:24px monospace}'
        'table{border-collapse:collapse}td,th{padding:.5rem;border:1px solid #888;text-align:left}'
        '.scroll{overflow:auto}pre{white-space:pre-wrap}section{border-top:2px solid #aaa;margin-top:2rem}'
        '</style><h1>Compare fields with their page</h1><p>'+escape(record['notice'])+'</p>'
        '<p>Numbered boxes include OCR labels and values. Direct text has no claimed region. '
        'This report has no accept button and makes no database changes.</p>'+''.join(sections)+'</html>')
    (output/'review.html').write_text(document, encoding='utf-8')
