"""Explicit multi-frame / phrase context boundaries for Stage 3-G.

Phrase membership is supplied by a validated plan. Context consumers may use
neighbors only within the same phrase; no evidence is allowed to leak across a
phrase boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

from .resolver import ResolverCandidate


@dataclass(frozen=True, slots=True, order=True)
class PhraseSpan:
    start_index: int
    end_index: int

    def __post_init__(self) -> None:
        for name, value in (("start_index", self.start_index), ("end_index", self.end_index)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an int")
        if self.start_index < 0:
            raise ValueError("start_index cannot be negative")
        if self.start_index >= self.end_index:
            raise ValueError("phrase span must be non-empty")


@dataclass(frozen=True, slots=True)
class PhrasePlan:
    spans: tuple[PhraseSpan, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.spans, tuple) or any(not isinstance(item, PhraseSpan) for item in self.spans):
            raise TypeError("spans must contain PhraseSpan values")
        if tuple(sorted(self.spans)) != self.spans:
            raise ValueError("phrase spans must be in canonical order")
        for left, right in zip(self.spans, self.spans[1:]):
            if left.end_index > right.start_index:
                raise ValueError("phrase spans cannot overlap")

    def phrase_for(self, frame_index: int) -> PhraseSpan | None:
        if isinstance(frame_index, bool) or not isinstance(frame_index, int):
            raise TypeError("frame_index must be an int")
        if frame_index < 0:
            raise ValueError("frame_index cannot be negative")
        for span in self.spans:
            if span.start_index <= frame_index < span.end_index:
                return span
        return None

    def same_phrase(self, left_index: int, right_index: int) -> bool:
        left = self.phrase_for(left_index)
        return left is not None and left == self.phrase_for(right_index)

    def validate_frame_count(self, frame_count: int) -> None:
        if isinstance(frame_count, bool) or not isinstance(frame_count, int):
            raise TypeError("frame_count must be an int")
        if frame_count < 0:
            raise ValueError("frame_count cannot be negative")
        if self.spans and self.spans[-1].end_index > frame_count:
            raise ValueError("phrase plan extends beyond frame_count")


def phrase_bounded_neighbors(
    sequence: tuple[tuple[ResolverCandidate, ...], ...],
    frame_index: int,
    plan: PhrasePlan,
) -> tuple[tuple[ResolverCandidate, ...], tuple[ResolverCandidate, ...]]:
    """Return previous/next candidate sets only when they share the phrase."""

    if not isinstance(sequence, tuple) or any(
        not isinstance(frame, tuple) or any(not isinstance(item, ResolverCandidate) for item in frame)
        for frame in sequence
    ):
        raise TypeError("sequence must contain tuples of ResolverCandidate values")
    if not isinstance(plan, PhrasePlan):
        raise TypeError("plan must be a PhrasePlan")
    plan.validate_frame_count(len(sequence))
    if isinstance(frame_index, bool) or not isinstance(frame_index, int):
        raise TypeError("frame_index must be an int")
    if not 0 <= frame_index < len(sequence):
        raise IndexError("frame_index is outside sequence")

    previous = sequence[frame_index - 1] if frame_index > 0 and plan.same_phrase(frame_index, frame_index - 1) else ()
    next_ = sequence[frame_index + 1] if frame_index + 1 < len(sequence) and plan.same_phrase(frame_index, frame_index + 1) else ()
    return previous, next_
