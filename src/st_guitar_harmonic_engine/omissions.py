"""Conservative incomplete-chord evidence for one omitted structural tone.

The legacy fifth-only generator remains stable. Stage 2-F adds a broader,
evidence-only generator for one missing root, third, fifth, or seventh in basic
major/minor triads and major/minor/dominant sevenths. Exact matches always win;
no incomplete candidate is authoritative or ranked.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .chords import ChordQuality, generate_exact_chord_candidates
from .frames import HarmonicFrame


class OmissionKind(str, Enum):
    ROOT = "root"
    THIRD = "third"
    FIFTH = "fifth"
    SEVENTH = "seventh"


_TEMPLATE_ROLES: tuple[tuple[ChordQuality, tuple[tuple[OmissionKind, int], ...]], ...] = (
    (
        ChordQuality.MAJOR,
        ((OmissionKind.ROOT, 0), (OmissionKind.THIRD, 4), (OmissionKind.FIFTH, 7)),
    ),
    (
        ChordQuality.MINOR,
        ((OmissionKind.ROOT, 0), (OmissionKind.THIRD, 3), (OmissionKind.FIFTH, 7)),
    ),
    (
        ChordQuality.DOMINANT_SEVENTH,
        (
            (OmissionKind.ROOT, 0),
            (OmissionKind.THIRD, 4),
            (OmissionKind.FIFTH, 7),
            (OmissionKind.SEVENTH, 10),
        ),
    ),
    (
        ChordQuality.MAJOR_SEVENTH,
        (
            (OmissionKind.ROOT, 0),
            (OmissionKind.THIRD, 4),
            (OmissionKind.FIFTH, 7),
            (OmissionKind.SEVENTH, 11),
        ),
    ),
    (
        ChordQuality.MINOR_SEVENTH,
        (
            (OmissionKind.ROOT, 0),
            (OmissionKind.THIRD, 3),
            (OmissionKind.FIFTH, 7),
            (OmissionKind.SEVENTH, 10),
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class IncompleteChordCandidate:
    """A basic chord candidate supported by all but one structural pitch class."""

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


def _generate_candidates(
    frame: HarmonicFrame,
    allowed_omissions: frozenset[OmissionKind],
) -> tuple[IncompleteChordCandidate, ...]:
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
        for quality, roles in _TEMPLATE_ROLES:
            if len(roles) != len(observed) + 1:
                continue
            full = frozenset((root_pc + interval) % 12 for _, interval in roles)
            for omission, interval in roles:
                if omission not in allowed_omissions:
                    continue
                omitted_pc = (root_pc + interval) % 12
                if full - {omitted_pc} != observed:
                    continue
                candidates.append(
                    IncompleteChordCandidate(
                        root_pc=root_pc,
                        quality=quality,
                        observed_pitch_classes=canonical,
                        omitted_pc=omitted_pc,
                        omission=omission,
                    )
                )

    return tuple(candidates)


def generate_fifth_omission_candidates(
    frame: HarmonicFrame,
) -> tuple[IncompleteChordCandidate, ...]:
    """Return candidates whose only missing structural tone is a perfect fifth.

    This is the Stage 1-F compatibility surface. Its behavior remains fifth-only,
    exact matches suppress inference, and candidate ordering remains deterministic.
    """

    return _generate_candidates(frame, frozenset({OmissionKind.FIFTH}))


def generate_incomplete_chord_candidates(
    frame: HarmonicFrame,
) -> tuple[IncompleteChordCandidate, ...]:
    """Return all basic candidates missing exactly one supported structural tone.

    Safety rules:
    - exact chord matches suppress all incomplete inference,
    - only major/minor triads and major/minor/dominant sevenths are considered,
    - exactly one structural pitch class may be absent,
    - root/third/fifth/seventh omissions are preserved as distinct evidence,
    - diminished, augmented, half-diminished, diminished-seventh, altered, and
      extension templates are deliberately excluded,
    - every valid candidate is returned; this layer never ranks or selects one.
    """

    return _generate_candidates(
        frame,
        frozenset(
            {
                OmissionKind.ROOT,
                OmissionKind.THIRD,
                OmissionKind.FIFTH,
                OmissionKind.SEVENTH,
            }
        ),
    )
