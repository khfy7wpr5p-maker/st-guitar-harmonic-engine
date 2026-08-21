"""Explicit local tonal-context spans for Stage 3-F.

Local key changes are caller-supplied facts. This module deliberately performs
no modulation detection, key estimation, or probability-based smoothing.
"""

from __future__ import annotations

from dataclasses import dataclass

from .context import TonalContext


@dataclass(frozen=True, slots=True, order=True)
class LocalTonalContextSpan:
    start_index: int
    end_index: int
    context: TonalContext

    def __post_init__(self) -> None:
        for name, value in (("start_index", self.start_index), ("end_index", self.end_index)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an int")
        if self.start_index < 0:
            raise ValueError("start_index cannot be negative")
        if self.start_index >= self.end_index:
            raise ValueError("local tonal-context span must be non-empty")
        if not isinstance(self.context, TonalContext):
            raise TypeError("context must be a TonalContext")


@dataclass(frozen=True, slots=True)
class LocalTonalContextPlan:
    spans: tuple[LocalTonalContextSpan, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.spans, tuple) or any(
            not isinstance(item, LocalTonalContextSpan) for item in self.spans
        ):
            raise TypeError("spans must contain LocalTonalContextSpan values")
        if tuple(sorted(self.spans)) != self.spans:
            raise ValueError("spans must be in canonical order")
        for left, right in zip(self.spans, self.spans[1:]):
            if left.end_index > right.start_index:
                raise ValueError("local tonal-context spans cannot overlap")

    def context_at(self, frame_index: int) -> TonalContext | None:
        if isinstance(frame_index, bool) or not isinstance(frame_index, int):
            raise TypeError("frame_index must be an int")
        if frame_index < 0:
            raise ValueError("frame_index cannot be negative")
        for span in self.spans:
            if span.start_index <= frame_index < span.end_index:
                return span.context
        return None

    def contexts_for(self, frame_count: int) -> tuple[TonalContext | None, ...]:
        if isinstance(frame_count, bool) or not isinstance(frame_count, int):
            raise TypeError("frame_count must be an int")
        if frame_count < 0:
            raise ValueError("frame_count cannot be negative")
        if self.spans and self.spans[-1].end_index > frame_count:
            raise ValueError("local tonal-context plan extends beyond frame_count")
        return tuple(self.context_at(index) for index in range(frame_count))
