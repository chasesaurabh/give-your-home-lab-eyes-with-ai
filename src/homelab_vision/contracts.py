"""Typed, model-agnostic contracts used by every companion project."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping


class Modality(StrEnum):
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    TEXT = "text"


class OutcomeStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    ABSTAINED = "abstained"
    DENIED = "denied"
    FAILED = "failed"


def _require_text(value: str, field_name: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{field_name} must not be blank")


@dataclass(frozen=True, slots=True)
class SourceReference:
    """An inspectable pointer back to source evidence."""

    fixture_id: str
    sha256: str
    locator: str
    media_type: str

    def __post_init__(self) -> None:
        _require_text(self.fixture_id, "fixture_id")
        _require_text(self.locator, "locator")
        _require_text(self.media_type, "media_type")
        digest = self.sha256.lower()
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError("sha256 must contain exactly 64 hexadecimal characters")
        object.__setattr__(self, "sha256", digest)


@dataclass(frozen=True, slots=True)
class MediaAsset:
    """A source or derivative known to the application."""

    asset_id: str
    modality: Modality
    relative_path: str
    sha256: str
    media_type: str
    derived_from: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.asset_id, "asset_id")
        _require_text(self.relative_path, "relative_path")
        if Path(self.relative_path).is_absolute() or ".." in Path(self.relative_path).parts:
            raise ValueError("relative_path must stay within the fixture root")
        SourceReference(self.asset_id, self.sha256, self.relative_path, self.media_type)
        if self.asset_id in self.derived_from:
            raise ValueError("an asset cannot derive from itself")


@dataclass(frozen=True, slots=True)
class Observation:
    """A bounded claim with inspectable evidence, separate from explanation."""

    kind: str
    value: Any
    evidence: tuple[SourceReference, ...]
    confidence_label: str = "unrated"

    def __post_init__(self) -> None:
        _require_text(self.kind, "kind")
        if not self.evidence:
            raise ValueError("an observation must include at least one source reference")


@dataclass(frozen=True, slots=True)
class ActionRequest:
    """A requested action; construction never implies authorization or execution."""

    tool: str
    operation: str
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.tool, "tool")
        _require_text(self.operation, "operation")


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    """A complete stage result with explicit non-success states."""

    status: OutcomeStatus
    observations: tuple[Observation, ...] = ()
    requested_actions: tuple[ActionRequest, ...] = ()
    warnings: tuple[str, ...] = ()
    error_code: str | None = None

    def __post_init__(self) -> None:
        if self.status is OutcomeStatus.FAILED and not self.error_code:
            raise ValueError("failed results require an error_code")
        if self.status is OutcomeStatus.SUCCESS and self.error_code:
            raise ValueError("successful results cannot include an error_code")
