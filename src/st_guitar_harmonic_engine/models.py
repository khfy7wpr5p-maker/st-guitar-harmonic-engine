"""Stable symbolic event contracts used by the harmonic engine.

Stage 0-A deliberately contains no harmony inference. It only establishes
validated, deterministic primitives that later resolver stages can trust.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction


class TieState(str, Enum):
    """Tie state carried by a symbolic note event."""

    NONE = "none"
    START = "start"
    CONTINUE = "continue"
    STOP = "stop"


@dataclass(frozen=True, slots=True)
class RationalBeat:
    """Exact musical time represented as a reduced rational number."""

    numerator: int
    denominator: int = 1

    def __post_init__(self) -> None:
        if isinstance(self.numerator, bool) or not isinstance(self.numerator, int):
            raise TypeError("numerator must be an int")
        if isinstance(self.denominator, bool) or not isinstance(self.denominator, int):
            raise TypeError("denominator must be an int")
        if self.denominator <= 0:
            raise ValueError("denominator must be greater than zero")

        reduced = Fraction(self.numerator, self.denominator)
        object.__setattr__(self, "numerator", reduced.numerator)
        object.__setattr__(self, "denominator", reduced.denominator)

    @property
    def fraction(self) -> Fraction:
        """Return the exact value as :class:`fractions.Fraction`."""

        return Fraction(self.numerator, self.denominator)

    def __add__(self, other: RationalBeat) -> RationalBeat:
        if not isinstance(other, RationalBeat):
            return NotImplemented
        value = self.fraction + other.fraction
        return RationalBeat(value.numerator, value.denominator)


@dataclass(frozen=True, slots=True)
class NoteEvent:
    """Validated symbolic note event at the engine boundary.

    MIDI pitch is intentionally used as the canonical sounding pitch for this
    first contract. Written spelling, tuplets, grace notes, and source-specific
    metadata are deferred to later versioned contracts rather than guessed here.
    """

    measure_number: int
    staff: int
    voice: int
    midi_pitch: int
    onset: RationalBeat
    duration: RationalBeat
    tie: TieState = TieState.NONE

    def __post_init__(self) -> None:
        for field_name in ("measure_number", "staff", "voice", "midi_pitch"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{field_name} must be an int")

        if self.measure_number < 1:
            raise ValueError("measure_number must be at least 1")
        if self.staff < 1:
            raise ValueError("staff must be at least 1")
        if self.voice < 1:
            raise ValueError("voice must be at least 1")
        if not 0 <= self.midi_pitch <= 127:
            raise ValueError("midi_pitch must be between 0 and 127")
        if not isinstance(self.onset, RationalBeat):
            raise TypeError("onset must be a RationalBeat")
        if not isinstance(self.duration, RationalBeat):
            raise TypeError("duration must be a RationalBeat")
        if self.onset.fraction < 0:
            raise ValueError("onset must not be negative")
        if self.duration.fraction <= 0:
            raise ValueError("duration must be greater than zero")
        if not isinstance(self.tie, TieState):
            raise TypeError("tie must be a TieState")

    @property
    def end(self) -> RationalBeat:
        """Exact exclusive end position relative to the measure."""

        return self.onset + self.duration
