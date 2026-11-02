"""Confirmed, transactional equipment-inventory mutations."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime


class ConfirmationRequired(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class InventoryProposal:
    item_id: str
    equipment_class: str
    manufacturer: str | None
    model: str | None
    serial: str | None
    source_digest: str
    uncertainty: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.item_id.strip() or not self.equipment_class.strip():
            raise ValueError("item_id and equipment_class are required")
        if not re.fullmatch(r"[0-9a-f]{64}", self.source_digest):
            raise ValueError("source_digest must be a SHA-256 hex string")


def create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS inventory (
            item_id TEXT PRIMARY KEY,
            equipment_class TEXT NOT NULL,
            manufacturer TEXT,
            model TEXT,
            serial TEXT,
            source_digest TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS change_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id TEXT NOT NULL,
            operation TEXT NOT NULL,
            before_json TEXT,
            after_json TEXT,
            approved_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )


def _current_record(connection: sqlite3.Connection, item_id: str) -> dict[str, str | None] | None:
    row = connection.execute(
        "SELECT item_id, equipment_class, manufacturer, model, serial, source_digest "
        "FROM inventory WHERE item_id = ?",
        (item_id,),
    ).fetchone()
    if row is None:
        return None
    keys = ("item_id", "equipment_class", "manufacturer", "model", "serial", "source_digest")
    return dict(zip(keys, row, strict=True))


def apply_confirmed_proposal(
    connection: sqlite3.Connection,
    proposal: InventoryProposal,
    *,
    confirmed: bool,
    approved_by: str,
    expected_revision: int | None = None,
) -> None:
    if not confirmed or not approved_by.strip():
        raise ConfirmationRequired("a named human confirmation is required")
    if proposal.uncertainty:
        raise ConfirmationRequired("uncertain proposals must be corrected before mutation")

    now = datetime.now(UTC).isoformat()
    after = asdict(proposal)
    after.pop("uncertainty")
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        if expected_revision is not None and item_revision(connection, proposal.item_id) != expected_revision:
            raise ConfirmationRequired("inventory changed after review; prepare a fresh proposal")
        before = _current_record(connection, proposal.item_id)
        connection.execute(
            """
            INSERT INTO inventory (
                item_id, equipment_class, manufacturer, model, serial,
                source_digest, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(item_id) DO UPDATE SET
                equipment_class=excluded.equipment_class,
                manufacturer=excluded.manufacturer,
                model=excluded.model,
                serial=excluded.serial,
                source_digest=excluded.source_digest,
                updated_at=excluded.updated_at
            """,
            (
                proposal.item_id,
                proposal.equipment_class,
                proposal.manufacturer,
                proposal.model,
                proposal.serial,
                proposal.source_digest,
                now,
            ),
        )
        connection.execute(
            """
            INSERT INTO change_events (
                item_id, operation, before_json, after_json, approved_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                proposal.item_id,
                "create" if before is None else "update",
                json.dumps(before, sort_keys=True) if before else None,
                json.dumps(after, sort_keys=True),
                approved_by,
                now,
            ),
        )


def item_revision(connection: sqlite3.Connection, item_id: str) -> int:
    return connection.execute("SELECT COALESCE(MAX(event_id), 0) FROM change_events WHERE item_id = ?",
                              (item_id,)).fetchone()[0]


def rollback_event(connection: sqlite3.Connection, event_id: int, *, confirmed: bool, approved_by: str) -> None:
    """Undo only the latest event for its item; append a new event in the same transaction."""
    if not confirmed or not approved_by.strip():
        raise ConfirmationRequired("a named human confirmation is required")
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT item_id, before_json FROM change_events WHERE event_id = ?", (event_id,)).fetchone()
        if row is None or item_revision(connection, row[0]) != event_id:
            raise ConfirmationRequired("event is missing or superseded; inspect current inventory")
        item_id, previous_json = row
        before = _current_record(connection, item_id)
        previous = json.loads(previous_json) if previous_json else None
        now = datetime.now(UTC).isoformat()
        if previous is None:
            connection.execute("DELETE FROM inventory WHERE item_id = ?", (item_id,))
        else:
            connection.execute("""INSERT INTO inventory VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(item_id) DO UPDATE SET equipment_class=excluded.equipment_class,
                manufacturer=excluded.manufacturer, model=excluded.model, serial=excluded.serial,
                source_digest=excluded.source_digest, updated_at=excluded.updated_at""",
                tuple(previous[key] for key in ('item_id','equipment_class','manufacturer','model','serial','source_digest')) + (now,))
        connection.execute("INSERT INTO change_events (item_id, operation, before_json, after_json, approved_by, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (item_id, f"rollback:{event_id}", json.dumps(before, sort_keys=True) if before else None,
             json.dumps(previous, sort_keys=True) if previous else None, approved_by, now))
