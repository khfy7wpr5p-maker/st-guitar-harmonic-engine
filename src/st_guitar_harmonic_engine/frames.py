"""Deterministic polyphonic frame construction.

A harmonic frame is a maximal time interval within one measure during which the
set of sounding note events is unchanged. This layer does not name or rank
chords; it only exposes trustworthy simultaneous-note evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .models import Measure, NoteEvent, RationalBeat


@dataclass(frozen=True, slots=True)
class HarmonicFrame:
    """One non-silent interval with a constant set of active note events."""

    measure_number: int
    start: RationalBeat
    end: RationalBeat
    events: tuple[NoteEvent, ...]

    def __post_init__(self) -> None:
        if self.measure_number < 1:
            raise ValueError("measure_number must be at least 1")
        if not isinstance(self.start, RationalBeat) or not isinstance(self.end, RationalBeat):
            raise TypeError("start and end must be RationalBeat values")
        if self.start.fraction >= self.end.fraction:
            raise ValueError("frame start must be before frame end")
        if not isinstance(self.events, tuple) or not self.events:
            raise ValueError("frame must contain at least one active NoteEvent")
        for event in self.events:
            if not isinstance(event, NoteEvent):
                raise TypeError("events must contain only NoteEvent values")
            if event.measure_number != self.measure_number:
                raise ValueError("frame events must belong to the same measure")
            if event.onset.fraction > self.start.fraction:
                raise ValueError("frame contains an event that has not started")
            if event.end.fraction < self.end.fraction:
                raise ValueError("frame contains an event that ended early")

    @property
    def duration(self) -> RationalBeat:
        value = self.end.fraction - self.start.fraction
        return RationalBeat(value.numerator, value.denominator)

    @property
    def pitch_classes(self) -> tuple[int, ...]:
        """Unique active MIDI pitch classes in ascending canonical order."""

        return tuple(sorted({event.midi_pitch % 12 for event in self.events}))


def _as_beat(value: Fraction) -> RationalBeat:
    return RationalBeat(value.numerator, value.denominator)


def build_harmonic_frames(measure: Measure) -> tuple[HarmonicFrame, ...]:
    """Split a measure at every note onset/end and return non-silent frames.

    The result is deterministic because ``Measure`` already canonicalizes its
    events and all boundaries use exact fractions. Silent intervals are omitted;
    rest-aware segmentation can be layered on later without changing this core.
    """

    if not isinstance(measure, Measure):
        raise TypeError("measure must be a Measure")
    if not measure.events:
        return ()

    boundaries = sorted(
        {
            boundary
            for event in measure.events
            for boundary in (event.onset.fraction, event.end.fraction)
        }
    )

    frames: list[HarmonicFrame] = []
    for start, end in zip(boundaries, boundaries[1:]):
        if start == end:
            continue
        active = tuple(
            event
            for event in measure.events
            if event.onset.fraction <= start and event.end.fraction >= end
        )
        if not active:
            continue
        frames.append(
            HarmonicFrame(
                measure_number=measure.number,
                start=_as_beat(start),
                end=_as_beat(end),
                events=active,
            )
        )

    return tuple(frames)
