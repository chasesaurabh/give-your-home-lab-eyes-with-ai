"""Timestamp-bearing video-frame records and bounded sampling helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FrameRecord:
    source_digest: str
    timestamp_seconds: float
    requested_timestamp_seconds: float
    selection_reason: str
    frame_digest: str

    def __post_init__(self) -> None:
        if self.timestamp_seconds < 0 or self.requested_timestamp_seconds < 0:
            raise ValueError("timestamps must not be negative")
        for digest in (self.source_digest, self.frame_digest):
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise ValueError("digests must be lowercase SHA-256 hex strings")
        if not self.selection_reason.strip():
            raise ValueError("selection_reason is required")


def constant_rate_timestamps(duration_seconds: float, interval_seconds: float) -> tuple[float, ...]:
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive")
    times: list[float] = []
    current = 0.0
    while current < duration_seconds:
        times.append(round(current, 6))
        current += interval_seconds
    return tuple(times)


def event_is_represented(
    frame_times: tuple[float, ...],
    event_start: float,
    event_end: float,
) -> bool:
    if event_start < 0 or event_end < event_start:
        raise ValueError("event window is invalid")
    return any(event_start <= timestamp <= event_end for timestamp in frame_times)
