"""Conservative incomplete-chord evidence for one omitted perfect fifth.

This stage deliberately supports only omissions that do not define the chord's
quality: the perfect fifth of major/minor triads and major/minor/dominant
sevenths. Root, third, seventh, altered-fifth, diminished, augmented, and
half-diminished omissions remain unresolved.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .chords import ChordQuality, generate_exact_chord_candidates
from .frames import HarmonicFrame


class OmissionKind(str, Enum):
    FIFTH = "fifth"


_TEMPLATES: tuple[tuple[ChordQuality, frozenset[int]], ...] = (
    (ChordQuality.MAJOR, frozenset({0, 4, 7})),
    (ChordQuality.MINOR, frozenset({0, 3, 7})),
    (ChordQuality.DOMINANT_SEVENTH, frozenset({0, 4, 7, 10})),
    (ChordQuality.MAJOR_SEVENTH, frozenset({0, 4, 7, 11})),
    (ChordQuality.MINOR_SEVENTH, frozenset({0, 3, 7, 10})),
)


@dataclass(frozen=True, slots=True)
class IncompleteChordCandidate:
    """A basic chord candidate supported by all tones except its perfect fifth."""

    root_pc: int
    quality: ChordQuality
    observed_pitch_classes: tuple[int, ...]
    omitted_pc: int
    omission: OmissionKind = OmissionKind.FIFTH

    def __post_init__(self) -> None:
        if isinstance(self.root_pc, bool) or not isinstance(self.root_pc, int):
            raise TypeError("root_pc must be an int")
        if not 0 <= self.root_pc <= 11:
            raise ValueError("root_pc must be between 0 and 11")
        if not isinstance(self.quality, ChordQuality):
            raise TypeError("quality must be a ChordQuality")
        if tuple(sorted(set(self.observed_pitch_classes))) != self.observed_pitch_classes:
            raise ValueError("observed_pitch_classes must be unique and sorted")
        if any(not 0 <= pc <= 11 for pc in self.observed_pitch_classes):
            raise ValueError("observed pitch classes must be between 0 and 11")
        if isinstance(self.omitted_pc, bool) or not isinstance(self.omitted_pc, int):
            raise TypeError("omitted_pc must be an int")
        if not 0 <= self.omitted_pc <= 11:
            raise ValueError("omitted_pc must be between 0 and 11")
        if self.omitted_pc in self.observed_pitch_classes:
            raise ValueError("omitted_pc cannot already be observed")
        if not isinstance(self.omission, OmissionKind):
            raise TypeError("omission must be an OmissionKind")

    @property
    def full_pitch_classes(self) -> tuple[int, ...]:
        return tuple(sorted((*self.observed_pitch_classes, self.omitted_pc)))


def generate_fifth_omission_candidates(
    frame: HarmonicFrame,
) -> tuple[IncompleteChordCandidate, ...]:
    """Return candidates whose only missing structural tone is a perfect fifth.

    Exact chord matches always take precedence and suppress incomplete inference.
    The function never infers a missing root, third, seventh, altered fifth, or
    extension, and it preserves every valid candidate rather than ranking them.
    """

    if not isinstance(frame, HarmonicFrame):
        raise TypeError("frame must be a HarmonicFrame")
    if generate_exact_chord_candidates(frame):
        return ()

    observed = frozenset(frame.pitch_classes)
    if len(observed) not in (2, 3):
        return ()

    canonical = tuple(sorted(observed))
    candidates: list[IncompleteChordCandidate] = []
    for root_pc in range(12):
        for quality, intervals in _TEMPLATES:
            if len(intervals) != len(observed) + 1:
                continue
            full = frozenset((root_pc + interval) % 12 for interval in intervals)
            omitted_pc = (root_pc + 7) % 12
            if omitted_pc not in full:
                continue
            if full - {omitted_pc} != observed:
                continue
            candidates.append(
                IncompleteChordCandidate(
                    root_pc=root_pc,
                    quality=quality,
                    observed_pitch_classes=canonical,
                    omitted_pc=omitted_pc,
                )
            )

    return tuple(candidates)
