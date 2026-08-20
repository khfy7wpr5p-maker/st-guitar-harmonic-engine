"""Conservative anticipation evidence.

Stage 2-C detects only high-confidence anticipations: one tone of the following
unique exact harmony arrives early and is demonstrably sustained or tied into
that harmony. The detector produces evidence only and does not mutate any
harmonic or structural decision path.
"""

from __future__ import annotations

from dataclasses import dataclass

from .analysis import AnalysisStatus, analyze_frame_exact
from .chords import ChordQuality
from .frames import HarmonicFrame, build_harmonic_frames
from .models import Measure, NoteEvent, RationalBeat, TieState


@dataclass(frozen=True, slots=True)
class AnticipationObservation:
    """One future chord tone that arrives early and continues into its harmony."""

    measure_number: int
    frame_index: int
    start: RationalBeat
    end: RationalBeat
    staff: int
    voice: int
    midi_pitch: int
    pitch_class: int
    source_root_pc: int
    source_quality: ChordQuality
    arrival_root_pc: int
    arrival_quality: ChordQuality

    def __post_init__(self) -> None:
        if self.measure_number < 1:
            raise ValueError("measure_number must be at least 1")
        if self.frame_index < 1:
            raise ValueError("frame_index must identify a middle frame")
        if not isinstance(self.start, RationalBeat) or not isinstance(self.end, RationalBeat):
            raise TypeError("start and end must be RationalBeat values")
        if self.start.fraction >= self.end.fraction:
            raise ValueError("observation start must be before end")
        if self.staff < 1 or self.voice < 1:
            raise ValueError("staff and voice must be at least 1")
        if not 0 <= self.midi_pitch <= 127:
            raise ValueError("midi_pitch must be between 0 and 127")
        if self.pitch_class != self.midi_pitch % 12:
            raise ValueError("pitch_class must match midi_pitch")
        for field_name in ("source_root_pc", "arrival_root_pc"):
            value = getattr(self, field_name)
            if not 0 <= value <= 11:
                raise ValueError(f"{field_name} must be between 0 and 11")
        if not isinstance(self.source_quality, ChordQuality):
            raise TypeError("source_quality must be a ChordQuality")
        if not isinstance(self.arrival_quality, ChordQuality):
            raise TypeError("arrival_quality must be a ChordQuality")


def _unique_voice_event(frame: HarmonicFrame, staff: int, voice: int) -> NoteEvent | None:
    matches = tuple(
        event for event in frame.events if event.staff == staff and event.voice == voice
    )
    return matches[0] if len(matches) == 1 else None


def _continues_into_following(
    middle_event: NoteEvent,
    following_event: NoteEvent,
    following_start: RationalBeat,
) -> bool:
    if middle_event.midi_pitch != following_event.midi_pitch:
        return False
    if middle_event is following_event:
        return middle_event.end.fraction > following_start.fraction
    if middle_event.end.fraction != following_start.fraction:
        return False
    if following_event.onset.fraction != following_start.fraction:
        return False
    return (
        middle_event.tie in (TieState.START, TieState.CONTINUE)
        and following_event.tie in (TieState.CONTINUE, TieState.STOP)
    )


def detect_anticipations(measure: Measure) -> tuple[AnticipationObservation, ...]:
    """Detect only future chord tones that arrive early with explicit continuity.

    Safety gates:
    - previous, middle, and following frames must be temporally contiguous,
    - previous and following frames must each have one exact chord candidate,
    - source and arrival harmonies must differ,
    - the middle frame must replace exactly one source-harmony pitch class with
      exactly one foreign pitch class,
    - that foreign pitch class must belong to the following harmony and not the
      source harmony,
    - exactly one event may carry the anticipated pitch class,
    - that event must begin exactly at the middle-frame boundary,
    - the same staff/voice and MIDI pitch must continue into the following frame
      via one spanning event or an explicit tie chain.
    """

    if not isinstance(measure, Measure):
        raise TypeError("measure must be a Measure")

    frames = build_harmonic_frames(measure)
    observations: list[AnticipationObservation] = []

    for index in range(1, len(frames) - 1):
        previous = frames[index - 1]
        middle = frames[index]
        following = frames[index + 1]

        if previous.end.fraction != middle.start.fraction:
            continue
        if middle.end.fraction != following.start.fraction:
            continue

        previous_analysis = analyze_frame_exact(previous)
        following_analysis = analyze_frame_exact(following)
        if previous_analysis.status is not AnalysisStatus.UNIQUE:
            continue
        if following_analysis.status is not AnalysisStatus.UNIQUE:
            continue

        source = previous_analysis.candidates[0].candidate
        arrival = following_analysis.candidates[0].candidate
        if (
            source.root_pc == arrival.root_pc
            and source.quality is arrival.quality
            and source.pitch_classes == arrival.pitch_classes
        ):
            continue

        source_pcs = frozenset(source.pitch_classes)
        arrival_pcs = frozenset(arrival.pitch_classes)
        middle_pcs = frozenset(middle.pitch_classes)
        foreign_pcs = middle_pcs - source_pcs
        missing_source_pcs = source_pcs - middle_pcs
        if len(foreign_pcs) != 1 or len(missing_source_pcs) != 1:
            continue

        anticipation_pc = next(iter(foreign_pcs))
        if anticipation_pc in source_pcs or anticipation_pc not in arrival_pcs:
            continue

        anticipation_events = tuple(
            event for event in middle.events if event.midi_pitch % 12 == anticipation_pc
        )
        if len(anticipation_events) != 1:
            continue
        middle_event = anticipation_events[0]
        if middle_event.onset.fraction != middle.start.fraction:
            continue

        following_event = _unique_voice_event(following, middle_event.staff, middle_event.voice)
        if following_event is None:
            continue
        if not _continues_into_following(middle_event, following_event, following.start):
            continue

        observations.append(
            AnticipationObservation(
                measure_number=measure.number,
                frame_index=index,
                start=middle.start,
                end=middle.end,
                staff=middle_event.staff,
                voice=middle_event.voice,
                midi_pitch=middle_event.midi_pitch,
                pitch_class=anticipation_pc,
                source_root_pc=source.root_pc,
                source_quality=source.quality,
                arrival_root_pc=arrival.root_pc,
                arrival_quality=arrival.quality,
            )
        )

    return tuple(observations)
