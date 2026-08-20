"""Conservative natural-extension evidence for complete basic chords.

Stage 2-G recognizes exactly one natural 9th, 11th, or 13th above a complete
supported base chord. The result is evidence only: it does not expand the
exact chord vocabulary, rank candidates, or mutate any resolver decision.
Altered tensions remain deliberately unsupported.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .chords import ChordQuality, generate_exact_chord_candidates
from .frames import HarmonicFrame


class ExtensionKind(str, Enum):
    NATURAL_NINTH = "natural_ninth"
    NATURAL_ELEVENTH = "natural_eleventh"
    NATURAL_THIRTEENTH = "natural_thirteenth"


_EXTENSION_INTERVALS: tuple[tuple[ExtensionKind, int], ...] = (
    (ExtensionKind.NATURAL_NINTH, 2),
    (ExtensionKind.NATURAL_ELEVENTH, 5),
    (ExtensionKind.NATURAL_THIRTEENTH, 9),
)

_BASE_TEMPLATES: tuple[tuple[ChordQuality, frozenset[int]], ...] = (
    (ChordQuality.MAJOR, frozenset({0, 4, 7})),
    (ChordQuality.MINOR, frozenset({0, 3, 7})),
    (ChordQuality.DOMINANT_SEVENTH, frozenset({0, 4, 7, 10})),
    (ChordQuality.MAJOR_SEVENTH, frozenset({0, 4, 7, 11})),
    (ChordQuality.MINOR_SEVENTH, frozenset({0, 3, 7, 10})),
)


@dataclass(frozen=True, slots=True)
class ExtensionCandidate:
    """One complete basic chord plus exactly one natural extension pitch class."""

    root_pc: int
    base_quality: ChordQuality
    extension: ExtensionKind
    base_pitch_classes: tuple[int, ...]
    extension_pc: int
    observed_pitch_classes: tuple[int, ...]

    def __post_init__(self) -> None:
        if isinstance(self.root_pc, bool) or not isinstance(self.root_pc, int):
            raise TypeError("root_pc must be an int")
        if not 0 <= self.root_pc <= 11:
            raise ValueError("root_pc must be between 0 and 11")
        if not isinstance(self.base_quality, ChordQuality):
            raise TypeError("base_quality must be a ChordQuality")
        if not isinstance(self.extension, ExtensionKind):
            raise TypeError("extension must be an ExtensionKind")
        for field_name in ("base_pitch_classes", "observed_pitch_classes"):
            value = getattr(self, field_name)
            if tuple(sorted(set(value))) != value:
                raise ValueError(f"{field_name} must be unique and sorted")
            if any(not 0 <= pc <= 11 for pc in value):
                raise ValueError(f"{field_name} values must be between 0 and 11")
        if isinstance(self.extension_pc, bool) or not isinstance(self.extension_pc, int):
            raise TypeError("extension_pc must be an int")
        if not 0 <= self.extension_pc <= 11:
            raise ValueError("extension_pc must be between 0 and 11")
        if self.extension_pc in self.base_pitch_classes:
            raise ValueError("extension_pc must not already belong to the base chord")
        if tuple(sorted((*self.base_pitch_classes, self.extension_pc))) != self.observed_pitch_classes:
            raise ValueError("observed_pitch_classes must equal base plus extension")


def generate_extension_candidates(frame: HarmonicFrame) -> tuple[ExtensionCandidate, ...]:
    """Return complete-base + one-natural-extension candidates for ``frame``.

    Safety rules:
    - existing exact basic chord matches always take precedence and suppress this layer,
    - the complete base chord must be present; no omission and extension are combined,
    - exactly one extra pitch class is permitted,
    - only natural 9th (2), 11th (5), and 13th (9) are supported,
    - altered tensions such as b9/#9/#11/b13 are excluded,
    - every valid interpretation is retained without ranking or selection.
    """

    if not isinstance(frame, HarmonicFrame):
        raise TypeError("frame must be a HarmonicFrame")
    if generate_exact_chord_candidates(frame):
        return ()

    observed = frozenset(frame.pitch_classes)
    if len(observed) not in (4, 5):
        return ()

    canonical_observed = tuple(sorted(observed))
    candidates: list[ExtensionCandidate] = []

    for root_pc in range(12):
        for quality, intervals in _BASE_TEMPLATES:
            if len(observed) != len(intervals) + 1:
                continue
            base = frozenset((root_pc + interval) % 12 for interval in intervals)
            if not base.issubset(observed):
                continue
            extras = observed - base
            if len(extras) != 1:
                continue
            extra_pc = next(iter(extras))
            for extension, interval in _EXTENSION_INTERVALS:
                extension_pc = (root_pc + interval) % 12
                if extension_pc != extra_pc or extension_pc in base:
                    continue
                candidates.append(
                    ExtensionCandidate(
                        root_pc=root_pc,
                        base_quality=quality,
                        extension=extension,
                        base_pitch_classes=tuple(sorted(base)),
                        extension_pc=extension_pc,
                        observed_pitch_classes=canonical_observed,
                    )
                )

    return tuple(candidates)
