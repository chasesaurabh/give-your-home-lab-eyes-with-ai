"""Bounded text-document ingestion that preserves line-level provenance."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .contracts import SourceReference
from .lineage import sha256_file


INSTRUCTION_PATTERNS = (
    re.compile(r"\bignore\s+(?:all\s+)?(?:prior|previous)\s+instructions?\b", re.IGNORECASE),
    re.compile(r"\b(?:reveal|print|return)\s+(?:the\s+)?system\s+prompt\b", re.IGNORECASE),
    re.compile(r"\b(?:upload|send|exfiltrate)\b.{0,80}\b(?:outside|external|remote)\b", re.IGNORECASE),
)


class DocumentValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    chunk_id: str
    text: str
    source: SourceReference
    instruction_like: bool


def contains_instruction_like_text(text: str) -> bool:
    """A warning heuristic, never a complete prompt-injection defense."""

    return any(pattern.search(text) for pattern in INSTRUCTION_PATTERNS)


def ingest_markdown(
    path: Path,
    fixture_id: str,
    *,
    max_bytes: int = 2_000_000,
) -> tuple[DocumentChunk, ...]:
    path = path.resolve(strict=True)
    if path.stat().st_size > max_bytes:
        raise DocumentValidationError("document exceeds the configured byte limit")
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise DocumentValidationError("document is not valid UTF-8") from error

    digest = sha256_file(path)
    lines = text.splitlines()
    chunks: list[DocumentChunk] = []
    block: list[str] = []
    block_start = 1

    def emit(end_line: int) -> None:
        nonlocal block
        content = "\n".join(block).strip()
        if not content:
            block = []
            return
        line_start = block_start
        chunk_id = f"{fixture_id}:{line_start}-{end_line}:{digest[:12]}"
        chunks.append(
            DocumentChunk(
                chunk_id=chunk_id,
                text=content,
                source=SourceReference(
                    fixture_id=fixture_id,
                    sha256=digest,
                    locator=f"lines:{line_start}-{end_line}",
                    media_type="text/markdown",
                ),
                instruction_like=contains_instruction_like_text(content),
            )
        )
        block = []

    for line_number, line in enumerate(lines, start=1):
        if line.strip():
            if not block:
                block_start = line_number
            block.append(line)
        elif block:
            emit(line_number - 1)
    if block:
        emit(len(lines))

    if not chunks:
        raise DocumentValidationError("document contains no ingestible text")
    return tuple(chunks)
