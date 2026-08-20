"""Conservative suspended-chord and altered-dominant evidence.

Stage 2-H keeps these colors outside the authoritative exact chord vocabulary.
Suspended triads are represented as root/kind candidates. Altered tensions are
accepted only over a complete dominant-seventh base with exactly one canonical
altered tension. No ranking, resolver mutation, or omission+alteration inference
is performed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .chords import ChordQuality, generate_exact_chord_candidates
from .frames import HarmonicFrame


class SuspendedChordKind(str, Enum):
    SUS2 = "sus2"
    SUS4 = "sus4"


_SUSPENDED_INTERVALS: tuple[tuple[SuspendedChordKind, frozenset[int]], ...] = (
    (SuspendedChordKind.SUS2, frozenset({0, 2, 7})),
    (SuspendedChordKind.SUS4, frozenset({0, 5, 7})),
)


class AlterationKind(str, Enum):
    FLAT_NINTH = "flat_ninth"
    SHARP_NINTH = "sharp_ninth"
    SHARP_ELEVENTH = "sharp_eleventh"
    FLAT_THIRTEENTH = "flat_thirteenth"


_ALTERED_INTERVALS: tuple[tuple[AlterationKind, int], ...] = (
    (AlterationKind.FLAT_NINTH, 1),
    (AlterationKind.SHARP_NINTH, 3),
    (AlterationKind.SHARP_ELEVENTH, 6),
    (AlterationKind.FLAT_THIRTEENTH, 8),
)
_DOMINANT_SEVENTH_INTERVALS = frozenset({0, 4, 7, 10})


@dataclass(frozen=True, slots=True)
class SuspendedChordCandidate:
    root_pc: int
    kind: SuspendedChordKind
    observed_pitch_classes: tuple[int, ...]

    def __post_init__(self) -> None:
        if isinstance(self.root_pc, bool) or not isinstance(self.root_pc, int):
            raise TypeError("root_pc must be an int")
        if not 0 <= self.root_pc <= 11:
            raise ValueError("root_pc must be between 0 and 11")
        if not isinstance(self.kind, SuspendedChordKind):
            raise TypeError("kind must be a SuspendedChordKind")
        if tuple(sorted(set(self.observed_pitch_classes))) != self.observed_pitch_classes:
            raise ValueError("observed_pitch_classes must be unique and sorted")
        if len(self.observed_pitch_classes) != 3:
            raise ValueError("suspended chord evidence must contain three pitch classes")


@dataclass(frozen=True, slots=True)
class AlteredTensionCandidate:
    root_pc: int
    base_quality: ChordQuality
    alteration: AlterationKind
    base_pitch_classes: tuple[int, ...]
    alteration_pc: int
    observed_pitch_classes: tuple[int, ...]

    def __post_init__(self) -> None:
        if isinstance(self.root_pc, bool) or not isinstance(self.root_pc, int):
            raise TypeError("root_pc must be an int")
        if not 0 <= self.root_pc <= 11:
            raise ValueError("root_pc must be between 0 and 11")
        if self.base_quality is not ChordQuality.DOMINANT_SEVENTH:
            raise ValueError("altered tension evidence requires a dominant-seventh base")
        if not isinstance(self.alteration, AlterationKind):
            raise TypeError("alteration must be an AlterationKind")
        for field_name in ("base_pitch_classes", "observed_pitch_classes"):
            value = getattr(self, field_name)
            if tuple(sorted(set(value))) != value:
                raise ValueError(f"{field_name} must be unique and sorted")
            if any(not 0 <= pc <= 11 for pc in value):
                raise ValueError(f"{field_name} values must be between 0 and 11")
        if len(self.base_pitch_classes) != 4 or len(self.observed_pitch_classes) != 5:
            raise ValueError("altered tension evidence requires four base plus one altered pitch")
        if isinstance(self.alteration_pc, bool) or not isinstance(self.alteration_pc, int):
            raise TypeError("alteration_pc must be an int")
        if not 0 <= self.alteration_pc <= 11:
            raise ValueError("alteration_pc must be between 0 and 11")
        if self.alteration_pc in self.base_pitch_classes:
            raise ValueError("alteration_pc must not already belong to the base chord")
        if tuple(sorted((*self.base_pitch_classes, self.alteration_pc))) != self.observed_pitch_classes:
            raise ValueError("observed_pitch_classes must equal base plus alteration")


def generate_suspended_chord_candidates(
    frame: HarmonicFrame,
) -> tuple[SuspendedChordCandidate, ...]:
    """Return exact sus2/sus4 pitch-set evidence without changing exact vocabulary."""

    if not isinstance(frame, HarmonicFrame):
        raise TypeError("frame must be a HarmonicFrame")
    if generate_exact_chord_candidates(frame):
        return ()

    observed = frozenset(frame.pitch_classes)
    if len(observed) != 3:
        return ()

    canonical = tuple(sorted(observed))
    candidates: list[SuspendedChordCandidate] = []
    for root_pc in range(12):
        for kind, intervals in _SUSPENDED_INTERVALS:
            target = frozenset((root_pc + interval) % 12 for interval in intervals)
            if target == observed:
                candidates.append(
                    SuspendedChordCandidate(
                        root_pc=root_pc,
                        kind=kind,
                        observed_pitch_classes=canonical,
                    )
                )
    return tuple(candidates)


def generate_altered_tension_candidates(
    frame: HarmonicFrame,
) -> tuple[AlteredTensionCandidate, ...]:
    """Return one altered tension over a complete dominant-seventh base.

    Only b9, #9, #11, and b13 are supported. Natural extensions, omissions,
    multiple alterations, and non-dominant bases are intentionally excluded.
    """

    if not isinstance(frame, HarmonicFrame):
        raise TypeError("frame must be a HarmonicFrame")
    if generate_exact_chord_candidates(frame):
        return ()

    observed = frozenset(frame.pitch_classes)
    if len(observed) != 5:
        return ()

    canonical_observed = tuple(sorted(observed))
    candidates: list[AlteredTensionCandidate] = []
    for root_pc in range(12):
        base = frozenset((root_pc + interval) % 12 for interval in _DOMINANT_SEVENTH_INTERVALS)
        if not base.issubset(observed):
            continue
        extras = observed - base
        if len(extras) != 1:
            continue
        extra_pc = next(iter(extras))
        for alteration, interval in _ALTERED_INTERVALS:
            alteration_pc = (root_pc + interval) % 12
            if alteration_pc != extra_pc or alteration_pc in base:
                continue
            candidates.append(
                AlteredTensionCandidate(
                    root_pc=root_pc,
                    base_quality=ChordQuality.DOMINANT_SEVENTH,
                    alteration=alteration,
                    base_pitch_classes=tuple(sorted(base)),
                    alteration_pc=alteration_pc,
                    observed_pitch_classes=canonical_observed,
                )
            )
    return tuple(candidates)
