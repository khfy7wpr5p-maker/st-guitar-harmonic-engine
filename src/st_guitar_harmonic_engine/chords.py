"""Deterministic exact-match chord candidate generation.

This module intentionally generates candidates rather than final chord labels.
Enharmonic spelling, non-chord tones, omissions, extensions, key context, and
functional interpretation belong to later resolver stages.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .frames import HarmonicFrame


class ChordQuality(str, Enum):
    MAJOR = "major"
    MINOR = "minor"
    DIMINISHED = "diminished"
    AUGMENTED = "augmented"
    DOMINANT_SEVENTH = "dominant_seventh"
    MAJOR_SEVENTH = "major_seventh"
    MINOR_SEVENTH = "minor_seventh"
    HALF_DIMINISHED_SEVENTH = "half_diminished_seventh"
    DIMINISHED_SEVENTH = "diminished_seventh"


_TEMPLATES: tuple[tuple[ChordQuality, frozenset[int]], ...] = (
    (ChordQuality.MAJOR, frozenset({0, 4, 7})),
    (ChordQuality.MINOR, frozenset({0, 3, 7})),
    (ChordQuality.DIMINISHED, frozenset({0, 3, 6})),
    (ChordQuality.AUGMENTED, frozenset({0, 4, 8})),
    (ChordQuality.DOMINANT_SEVENTH, frozenset({0, 4, 7, 10})),
    (ChordQuality.MAJOR_SEVENTH, frozenset({0, 4, 7, 11})),
    (ChordQuality.MINOR_SEVENTH, frozenset({0, 3, 7, 10})),
    (ChordQuality.HALF_DIMINISHED_SEVENTH, frozenset({0, 3, 6, 10})),
    (ChordQuality.DIMINISHED_SEVENTH, frozenset({0, 3, 6, 9})),
)


@dataclass(frozen=True, slots=True)
class ChordCandidate:
    """One structural chord candidate expressed only in pitch classes."""

    root_pc: int
    quality: ChordQuality
    pitch_classes: tuple[int, ...]

    def __post_init__(self) -> None:
        if isinstance(self.root_pc, bool) or not isinstance(self.root_pc, int):
            raise TypeError("root_pc must be an int")
        if not 0 <= self.root_pc <= 11:
            raise ValueError("root_pc must be between 0 and 11")
        if not isinstance(self.quality, ChordQuality):
            raise TypeError("quality must be a ChordQuality")
        if tuple(sorted(set(self.pitch_classes))) != self.pitch_classes:
            raise ValueError("pitch_classes must be unique and sorted")
        if any(not 0 <= pitch_class <= 11 for pitch_class in self.pitch_classes):
            raise ValueError("pitch_classes must be between 0 and 11")


def generate_exact_chord_candidates(frame: HarmonicFrame) -> tuple[ChordCandidate, ...]:
    """Return every basic triad/seventh template exactly matching ``frame``.

    Symmetric sonorities intentionally retain multiple roots. The function does
    not guess a preferred enharmonic spelling or resolve ambiguity.
    """

    if not isinstance(frame, HarmonicFrame):
        raise TypeError("frame must be a HarmonicFrame")

    observed = frozenset(frame.pitch_classes)
    if len(observed) not in (3, 4):
        return ()

    candidates: list[ChordCandidate] = []
    canonical_pitch_classes = tuple(sorted(observed))
    for root_pc in range(12):
        for quality, intervals in _TEMPLATES:
            if len(intervals) != len(observed):
                continue
            realized = frozenset((root_pc + interval) % 12 for interval in intervals)
            if realized == observed:
                candidates.append(
                    ChordCandidate(
                        root_pc=root_pc,
                        quality=quality,
                        pitch_classes=canonical_pitch_classes,
                    )
                )

    return tuple(candidates)
