"""Fail-closed written-spelling support for symmetric exact sonorities.

Sounding pitch classes alone cannot identify a unique root for augmented triads
or fully diminished seventh chords. This module may contribute structural support
only when every sounding event carries pitch-class-consistent written spelling
and exactly one symmetric exact candidate matches the written tertian letter stack.

It never invents spelling, assumes a transposition, or changes non-symmetric
candidate generation.
"""

from __future__ import annotations

from .chords import ChordCandidate, ChordQuality
from .frames import HarmonicFrame
from .spelling import PitchStep, WrittenPitch


_NATURAL_PITCH_CLASS = {
    PitchStep.C: 0,
    PitchStep.D: 2,
    PitchStep.E: 4,
    PitchStep.F: 5,
    PitchStep.G: 7,
    PitchStep.A: 9,
    PitchStep.B: 11,
}
_STEP_INDEX = {
    PitchStep.C: 0,
    PitchStep.D: 1,
    PitchStep.E: 2,
    PitchStep.F: 3,
    PitchStep.G: 4,
    PitchStep.A: 5,
    PitchStep.B: 6,
}
_SUPPORTED_TERTIAN_STEPS = {
    ChordQuality.AUGMENTED: (0, 2, 4),
    ChordQuality.DIMINISHED_SEVENTH: (0, 2, 4, 6),
}


def written_pitch_class(pitch: WrittenPitch) -> int:
    """Return the written pitch class without assuming sounding transposition."""

    if not isinstance(pitch, WrittenPitch):
        raise TypeError("pitch must be a WrittenPitch")
    return (_NATURAL_PITCH_CLASS[pitch.step] + pitch.alter) % 12


def _validated_spelling_by_pitch_class(
    frame: HarmonicFrame,
) -> dict[int, tuple[PitchStep, int]] | None:
    if not isinstance(frame, HarmonicFrame):
        raise TypeError("frame must be a HarmonicFrame")

    spellings: dict[int, tuple[PitchStep, int]] = {}
    for event in frame.events:
        written = event.written_pitch
        if written is None:
            return None
        sounding_pc = event.midi_pitch % 12
        if written_pitch_class(written) != sounding_pc:
            # The source may be transposing or inconsistently normalized. Do not
            # infer a relation between written and sounding pitch classes.
            return None
        token = (written.step, written.alter)
        previous = spellings.get(sounding_pc)
        if previous is not None and previous != token:
            # Enharmonically conflicting spellings for the same sounding pitch
            # are insufficient to claim one canonical root.
            return None
        spellings[sounding_pc] = token

    if tuple(sorted(spellings)) != frame.pitch_classes:
        return None
    return spellings


def _matches_written_tertian_stack(
    candidate: ChordCandidate,
    spellings: dict[int, tuple[PitchStep, int]],
) -> bool:
    offsets = _SUPPORTED_TERTIAN_STEPS.get(candidate.quality)
    if offsets is None or len(spellings) != len(offsets):
        return False
    root_spelling = spellings.get(candidate.root_pc)
    if root_spelling is None:
        return False
    root_step = _STEP_INDEX[root_spelling[0]]
    expected_steps = {(root_step + offset) % 7 for offset in offsets}
    observed_steps = {_STEP_INDEX[step] for step, _ in spellings.values()}
    return observed_steps == expected_steps


def select_spelling_supported_symmetric_candidate(
    frame: HarmonicFrame,
    candidates: tuple[ChordCandidate, ...],
) -> ChordCandidate | None:
    """Return one spelling-supported symmetric exact candidate, or fail closed.

    Preconditions are deliberately strict:
    - at least two exact candidates must exist;
    - every candidate must share one supported symmetric quality;
    - every event must have written spelling;
    - written and sounding pitch classes must agree event-by-event;
    - duplicate sounding pitch classes must not carry conflicting spellings;
    - exactly one candidate must match the written tertian letter stack.
    """

    if not isinstance(frame, HarmonicFrame):
        raise TypeError("frame must be a HarmonicFrame")
    if not isinstance(candidates, tuple) or any(
        not isinstance(item, ChordCandidate) for item in candidates
    ):
        raise TypeError("candidates must contain ChordCandidate values")
    if len(candidates) < 2:
        return None

    qualities = {item.quality for item in candidates}
    if len(qualities) != 1:
        return None
    quality = next(iter(qualities))
    if quality not in _SUPPORTED_TERTIAN_STEPS:
        return None

    spellings = _validated_spelling_by_pitch_class(frame)
    if spellings is None:
        return None

    matches = tuple(
        item for item in candidates if _matches_written_tertian_stack(item, spellings)
    )
    return matches[0] if len(matches) == 1 else None
