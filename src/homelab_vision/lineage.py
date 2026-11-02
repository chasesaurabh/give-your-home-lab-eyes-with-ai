"""Checksum, fixture-manifest, and derivative-lineage helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _inside_root(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def verify_fixture_manifest(manifest_path: Path) -> list[str]:
    """Return every manifest violation; an empty list means the set is intact."""

    manifest_path = manifest_path.resolve()
    root = manifest_path.parent.resolve()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []

    if data.get("schema_version") != 1:
        errors.append("unsupported schema_version")

    seen_ids: set[str] = set()
    for entry in data.get("fixtures", []):
        fixture_id = entry.get("id", "")
        if not fixture_id or fixture_id in seen_ids:
            errors.append(f"invalid or duplicate fixture id: {fixture_id!r}")
            continue
        seen_ids.add(fixture_id)

        relative_path = Path(entry.get("path", ""))
        candidate = (root / relative_path).resolve()
        if relative_path.is_absolute() or not _inside_root(root, candidate):
            errors.append(f"{fixture_id}: path escapes fixture root")
            continue
        if not candidate.is_file():
            errors.append(f"{fixture_id}: file is missing")
            continue

        expected_size = entry.get("bytes")
        if candidate.stat().st_size != expected_size:
            errors.append(f"{fixture_id}: byte count differs")
        if sha256_file(candidate) != entry.get("sha256", "").lower():
            errors.append(f"{fixture_id}: checksum differs")

    return errors


class LineageGraph:
    """Track source-to-derivative edges and compute safe deletion order."""

    def __init__(self) -> None:
        self._children: dict[str, set[str]] = {}

    def add_relation(self, parent: str, child: str) -> None:
        if not parent or not child:
            raise ValueError("lineage identifiers must not be blank")
        if parent == child:
            raise ValueError("an asset cannot derive from itself")
        parent_existed = parent in self._children
        child_existed = child in self._children
        children = self._children.setdefault(parent, set())
        edge_existed = child in children
        children.add(child)
        self._children.setdefault(child, set())
        try:
            self._assert_acyclic()
        except ValueError:
            if not edge_existed:
                children.remove(child)
            if not parent_existed and not children:
                self._children.pop(parent, None)
            if not child_existed and not self._children.get(child):
                self._children.pop(child, None)
            raise

    def descendants(self, asset_id: str) -> set[str]:
        found: set[str] = set()
        pending = list(self._children.get(asset_id, set()))
        while pending:
            current = pending.pop()
            if current in found:
                continue
            found.add(current)
            pending.extend(self._children.get(current, set()))
        return found

    def deletion_order(self, asset_id: str) -> tuple[str, ...]:
        """Return derivatives before their parents, ending with the requested asset."""

        ordered: list[str] = []
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visited:
                return
            visited.add(node)
            for child in sorted(self._children.get(node, set())):
                visit(child)
            ordered.append(node)

        visit(asset_id)
        return tuple(ordered)

    def _assert_acyclic(self) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise ValueError("lineage graph contains a cycle")
            if node in visited:
                return
            visiting.add(node)
            for child in self._children.get(node, set()):
                visit(child)
            visiting.remove(node)
            visited.add(node)

        for node in self._children:
            visit(node)
