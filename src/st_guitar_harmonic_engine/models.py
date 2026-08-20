"""Stable symbolic contracts used by the harmonic engine.

These primitives deliberately contain no harmony inference. They establish
validated, deterministic data boundaries that later resolver stages can trust.
All temporal values are expressed in exact quarter-note units.
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
    """Exact musical duration/position in quarter-note units."""

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
class TimeSignature:
    """Simple meter contract with exact nominal measure length."""

    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        for field_name in ("numerator", "denominator"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{field_name} must be an int")
        if self.numerator <= 0:
            raise ValueError("numerator must be greater than zero")
        if self.denominator <= 0:
            raise ValueError("denominator must be greater than zero")

    @property
    def quarter_length(self) -> RationalBeat:
        """Nominal measure duration expressed in quarter-note units."""

        return RationalBeat(self.numerator * 4, self.denominator)


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


@dataclass(frozen=True, slots=True)
class Measure:
    """Validated measure boundary for deterministic downstream analysis.

    ``actual_duration`` separates the notated meter from the realized measure
    span, allowing pickups and other irregular measures without weakening the
    timing contract.
    """

    number: int
    time_signature: TimeSignature
    events: tuple[NoteEvent, ...] = ()
    actual_duration: RationalBeat | None = None

    def __post_init__(self) -> None:
        if isinstance(self.number, bool) or not isinstance(self.number, int):
            raise TypeError("number must be an int")
        if self.number < 1:
            raise ValueError("number must be at least 1")
        if not isinstance(self.time_signature, TimeSignature):
            raise TypeError("time_signature must be a TimeSignature")
        if not isinstance(self.events, tuple):
            raise TypeError("events must be a tuple")
        if self.actual_duration is not None:
            if not isinstance(self.actual_duration, RationalBeat):
                raise TypeError("actual_duration must be a RationalBeat or None")
            if self.actual_duration.fraction <= 0:
                raise ValueError("actual_duration must be greater than zero")

        for event in self.events:
            if not isinstance(event, NoteEvent):
                raise TypeError("events must contain only NoteEvent values")
            if event.measure_number != self.number:
                raise ValueError("event measure_number must match measure number")
            if event.end.fraction > self.duration.fraction:
                raise ValueError("event extends beyond the measure duration")

        canonical = tuple(
            sorted(
                self.events,
                key=lambda event: (
                    event.onset.fraction,
                    event.staff,
                    event.voice,
                    event.midi_pitch,
                    event.duration.fraction,
                    event.tie.value,
                ),
            )
        )
        object.__setattr__(self, "events", canonical)

    @property
    def duration(self) -> RationalBeat:
        """Realized measure span in quarter-note units."""

        return self.actual_duration or self.time_signature.quarter_length
