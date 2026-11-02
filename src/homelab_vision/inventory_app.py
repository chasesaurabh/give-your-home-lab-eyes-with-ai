"""Single-user review files for inventory; no model has database write access."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path

from .inventory import (InventoryProposal, apply_confirmed_proposal, create_schema,
                        item_revision, rollback_event)


def read_json(path: Path) -> dict:
    if path.stat().st_size > 2_000_000:
        raise ValueError('JSON exceeds 2 MB')
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def initialize(database: Path) -> None:
    if database.exists():
        raise FileExistsError(database)
    database.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database)) as connection:
        create_schema(connection)


def connect(database: Path) -> sqlite3.Connection:
    if not database.is_file():
        raise FileNotFoundError('Initialize the inventory database first')
    return sqlite3.connect(database.resolve().as_uri() + '?mode=rw', uri=True)


def prepare(analysis: Path, database: Path, output: Path, item_id: str, equipment_class: str) -> dict:
    """Keep original observation immutable; proposed fields may be corrected before inspection."""
    result = read_json(analysis / 'proposal.json')
    source = read_json(analysis / 'input.json')
    if result.get('task') != 'label' or result.get('status') != 'review_required':
        raise ValueError('A completed label analysis is required')
    image = (analysis / source['image']).resolve()
    if not image.is_relative_to(analysis.resolve()) or not image.is_file():
        raise ValueError('Image must be inside the analysis bundle')
    image_bytes = image.read_bytes()
    image_hash = hashlib.sha256(image_bytes).hexdigest()
    if image_hash != source['normalized_sha256'] or image_hash != result['image_sha256']:
        raise ValueError('Label evidence changed')
    if result['source_sha256'] != source['source_sha256']:
        raise ValueError('Source identities disagree')
    proposal = InventoryProposal(item_id, equipment_class, None, result['fields'].get('model'),
                                 None, source['source_sha256'])
    with closing(connect(database)) as connection:
        revision = item_revision(connection, item_id)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'evidence.png').write_bytes(image_bytes)
    (output / 'observation.json').write_bytes((analysis / 'proposal.json').read_bytes())
    review = dict(schema_version=1, expected_revision=revision,
        image_sha256=image_hash, observation_sha256=digest(output / 'observation.json'),
        source_sha256=source['source_sha256'],
        fields=dict(item_id=proposal.item_id, equipment_class=proposal.equipment_class,
                    manufacturer=None, model=proposal.model, serial=None),
        note='Review every field against evidence.png. Edit fields only; unknown is null. Then inspect and confirm the new digest.')
    (output / 'review.json').write_text(json.dumps(review, indent=2), encoding='utf-8')
    return inspect_review(output, database)


def inspect_review(review_dir: Path, database: Path) -> dict:
    review = read_json(review_dir / 'review.json')
    if review['schema_version'] != 1 or type(review['expected_revision']) is not int or review['expected_revision'] < 0:
        raise ValueError('Invalid review version')
    for filename, key in [('evidence.png','image_sha256'), ('observation.json','observation_sha256')]:
        if digest(review_dir / filename) != review[key]:
            raise ValueError(f'{filename} changed after preparation')
    original = read_json(review_dir / 'observation.json')
    if original['source_sha256'] != review['source_sha256'] or original['image_sha256'] != review['image_sha256']:
        raise ValueError('Observation and review identities disagree')
    fields = review['fields']
    if set(fields) != {'item_id','equipment_class','manufacturer','model','serial'}:
        raise ValueError('Unexpected inventory fields')
    for key, value in fields.items():
        if value is None and key in {'manufacturer','model','serial'}:
            continue
        if not isinstance(value, str) or not value.strip() or len(value) > 200:
            raise ValueError('Fields must be nonempty text up to 200 characters, or null where allowed')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', fields['item_id']):
        raise ValueError('item_id must be a short stable identifier')
    InventoryProposal(**fields, source_digest=review['source_sha256'])
    with closing(connect(database)) as connection:
        current = item_revision(connection, fields['item_id'])
        names = ['item_id','equipment_class','manufacturer','model','serial','source_digest']
        row = connection.execute('SELECT ' + ','.join(names) + ' FROM inventory WHERE item_id=?', (fields['item_id'],)).fetchone()
        matches = connection.execute('SELECT item_id,model,serial FROM inventory WHERE item_id != ? AND ((serial IS NOT NULL AND serial=?) OR (model IS NOT NULL AND model=?))',
            (fields['item_id'], fields['serial'], fields['model'])).fetchall()
    return dict(review_sha256=digest(review_dir / 'review.json'), proposed_fields=fields,
                before=dict(zip(names,row)) if row else None, expected_revision=review['expected_revision'],
                current_revision=current, stale=current != review['expected_revision'],
                possible_matches=[dict(zip(['item_id','model','serial'], r)) for r in matches],
                notice='Matches are suggestions; identical models can be different devices. No automatic merge. Local confirmation is not authentication.')


def commit_review(review_dir: Path, database: Path, confirm_digest: str, reviewer: str) -> dict:
    checked = inspect_review(review_dir, database)
    raw = (review_dir / 'review.json').read_bytes()
    if checked['review_sha256'] != confirm_digest or hashlib.sha256(raw).hexdigest() != confirm_digest:
        raise ValueError('Review digest changed; inspect again')
    review = json.loads(raw)
    with closing(connect(database)) as connection:
        apply_confirmed_proposal(connection, InventoryProposal(**review['fields'], source_digest=review['source_sha256']),
            confirmed=True, approved_by=reviewer, expected_revision=review['expected_revision'])
        return dict(state='committed', item_id=review['fields']['item_id'], event_id=item_revision(connection, review['fields']['item_id']))


def export_inventory(database: Path) -> dict:
    with closing(connect(database)) as connection:
        connection.row_factory = sqlite3.Row
        items = [dict(row) for row in connection.execute('SELECT * FROM inventory ORDER BY item_id')]
        events = [dict(row) for row in connection.execute('SELECT * FROM change_events ORDER BY event_id')]
    return dict(items=items, events=events, notice='This export includes accepted values and review history; protect it as inventory data.')


def undo(database: Path, event_id: int, reviewer: str, confirmed: bool) -> dict:
    with closing(connect(database)) as connection:
        rollback_event(connection, event_id, confirmed=confirmed, approved_by=reviewer)
    return dict(state='rolled_back', event_id=event_id)


def backup(database: Path, output: Path) -> dict:
    # Reserve the exact destination to avoid overwriting an earlier snapshot.
    with output.open('xb'):
        pass
    with closing(connect(database)) as source, closing(sqlite3.connect(output)) as target:
        source.backup(target)
        check = target.execute('PRAGMA integrity_check').fetchone()[0]
        if check != 'ok':
            raise RuntimeError('Backup integrity check failed')
    return dict(state='copied', sha256=digest(output), note='Database only. Copy review/evidence bundles separately. Same-disk copies are not disaster recovery.')
