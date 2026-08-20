"""Written pitch spelling contracts.

Written pitch is kept separate from sounding MIDI pitch. The engine deliberately
makes no equality assumption between them because transposing notation (including
standard guitar notation sounding an octave below written pitch) is source-level
information that must be normalized explicitly rather than guessed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PitchStep(str, Enum):
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"
    A = "A"
    B = "B"


@dataclass(frozen=True, slots=True)
class WrittenPitch:
    """Exact written spelling from a symbolic score source.

    ``alter`` is measured in semitones relative to the natural step. The bounded
    -2..2 range covers double-flat through double-sharp without inventing
    microtonal semantics in the initial contract.
    """

    step: PitchStep
    alter: int
    octave: int

    def __post_init__(self) -> None:
        if not isinstance(self.step, PitchStep):
            raise TypeError("step must be a PitchStep")
        if isinstance(self.alter, bool) or not isinstance(self.alter, int):
            raise TypeError("alter must be an int")
        if not -2 <= self.alter <= 2:
            raise ValueError("alter must be between -2 and 2")
        if isinstance(self.octave, bool) or not isinstance(self.octave, int):
            raise TypeError("octave must be an int")
        if not -1 <= self.octave <= 9:
            raise ValueError("octave must be between -1 and 9")

    @property
    def accidental(self) -> str:
        """Canonical ASCII accidental token for serialization/debugging."""

        return {
            -2: "bb",
            -1: "b",
            0: "",
            1: "#",
            2: "##",
        }[self.alter]

    @property
    def name(self) -> str:
        """Canonical written-pitch name, for example ``C#4`` or ``Bbb3``."""

        return f"{self.step.value}{self.accidental}{self.octave}"
