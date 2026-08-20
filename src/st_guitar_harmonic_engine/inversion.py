"""Deterministic bass and inversion analysis for chord candidates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .chords import ChordCandidate
from .frames import HarmonicFrame


class Inversion(str, Enum):
    ROOT_POSITION = "root_position"
    FIRST = "first_inversion"
    SECOND = "second_inversion"
    THIRD = "third_inversion"


@dataclass(frozen=True, slots=True)
class BassAnalysis:
    """Observed lowest pitch and its structural position in one candidate."""

    bass_midi: int
    bass_pc: int
    inversion: Inversion

    def __post_init__(self) -> None:
        if not 0 <= self.bass_midi <= 127:
            raise ValueError("bass_midi must be between 0 and 127")
        if not 0 <= self.bass_pc <= 11:
            raise ValueError("bass_pc must be between 0 and 11")
        if self.bass_midi % 12 != self.bass_pc:
            raise ValueError("bass_pc must match bass_midi")
        if not isinstance(self.inversion, Inversion):
            raise TypeError("inversion must be an Inversion")


def analyze_bass_and_inversion(
    frame: HarmonicFrame,
    candidate: ChordCandidate,
) -> BassAnalysis:
    """Resolve the literal lowest sounding pitch against ``candidate``.

    The candidate must describe exactly the frame's pitch-class set. This keeps
    bass analysis structural and prevents it from silently legitimizing a chord
    hypothesis generated for different evidence.
    """

    if not isinstance(frame, HarmonicFrame):
        raise TypeError("frame must be a HarmonicFrame")
    if not isinstance(candidate, ChordCandidate):
        raise TypeError("candidate must be a ChordCandidate")
    if candidate.pitch_classes != frame.pitch_classes:
        raise ValueError("candidate pitch classes must match frame pitch classes")

    bass_midi = min(event.midi_pitch for event in frame.events)
    bass_pc = bass_midi % 12
    interval_from_root = (bass_pc - candidate.root_pc) % 12

    chord_intervals = tuple(
        sorted((pitch_class - candidate.root_pc) % 12 for pitch_class in candidate.pitch_classes)
    )
    try:
        inversion_index = chord_intervals.index(interval_from_root)
    except ValueError as exc:
        raise ValueError("bass pitch class is not part of the candidate") from exc

    inversion_by_index = (
        Inversion.ROOT_POSITION,
        Inversion.FIRST,
        Inversion.SECOND,
        Inversion.THIRD,
    )
    if inversion_index >= len(inversion_by_index):
        raise ValueError("unsupported inversion depth")

    return BassAnalysis(
        bass_midi=bass_midi,
        bass_pc=bass_pc,
        inversion=inversion_by_index[inversion_index],
    )
