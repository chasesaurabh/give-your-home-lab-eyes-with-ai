"""Confirmed, transactional equipment-inventory mutations."""

from __future__ import annotations

import json
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
        if len(self.source_digest) != 64:
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
) -> None:
    if not confirmed or not approved_by.strip():
        raise ConfirmationRequired("a named human confirmation is required")
    if proposal.uncertainty:
        raise ConfirmationRequired("uncertain proposals must be corrected before mutation")

    now = datetime.now(UTC).isoformat()
    after = asdict(proposal)
    after.pop("uncertainty")
    with connection:
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
