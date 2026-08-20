"""Conservative appoggiatura and escape-tone evidence.

Stage 2-D recognizes only single-voice ornamental substitutions between the same
unique exact harmony on both sides. The detector is evidence-only and cannot
alter exact, contextual, structural, suspension, or anticipation decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .analysis import AnalysisStatus, analyze_frame_exact
from .chords import ChordQuality
from .frames import HarmonicFrame, build_harmonic_frames
from .models import Measure, NoteEvent, RationalBeat, TieState


class OrnamentalNCTKind(str, Enum):
    APPOGGIATURA = "appoggiatura"
    ESCAPE = "escape"


@dataclass(frozen=True, slots=True)
class OrnamentalNCTObservation:
    """One conservative appoggiatura or escape-tone observation."""

    measure_number: int
    frame_index: int
    start: RationalBeat
    end: RationalBeat
    staff: int
    voice: int
    midi_pitch: int
    pitch_class: int
    kind: OrnamentalNCTKind
    anchor_root_pc: int
    anchor_quality: ChordQuality
    approach_semitones: int
    resolution_semitones: int

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
        if not isinstance(self.kind, OrnamentalNCTKind):
            raise TypeError("kind must be an OrnamentalNCTKind")
        if not 0 <= self.anchor_root_pc <= 11:
            raise ValueError("anchor_root_pc must be between 0 and 11")
        if not isinstance(self.anchor_quality, ChordQuality):
            raise TypeError("anchor_quality must be a ChordQuality")
        if self.approach_semitones == 0 or self.resolution_semitones == 0:
            raise ValueError("approach and resolution motion must be non-zero")


def _unique_voice_event(frame: HarmonicFrame, staff: int, voice: int) -> NoteEvent | None:
    matches = tuple(
        event for event in frame.events if event.staff == staff and event.voice == voice
    )
    return matches[0] if len(matches) == 1 else None


def _same_unique_anchor(previous: HarmonicFrame, following: HarmonicFrame):
    previous_analysis = analyze_frame_exact(previous)
    following_analysis = analyze_frame_exact(following)
    if previous_analysis.status is not AnalysisStatus.UNIQUE:
        return None
    if following_analysis.status is not AnalysisStatus.UNIQUE:
        return None
    left = previous_analysis.candidates[0].candidate
    right = following_analysis.candidates[0].candidate
    if (
        left.root_pc != right.root_pc
        or left.quality is not right.quality
        or left.pitch_classes != right.pitch_classes
    ):
        return None
    return left


def _classify_motion(approach: int, resolution: int) -> OrnamentalNCTKind | None:
    if (approach > 0) == (resolution > 0):
        return None
    approach_size = abs(approach)
    resolution_size = abs(resolution)
    if approach_size >= 3 and resolution_size in (1, 2):
        return OrnamentalNCTKind.APPOGGIATURA
    if approach_size in (1, 2) and resolution_size >= 3:
        return OrnamentalNCTKind.ESCAPE
    return None


def detect_ornamental_ncts(measure: Measure) -> tuple[OrnamentalNCTObservation, ...]:
    """Detect conservative appoggiatura/escape substitutions.

    Safety gates:
    - all three frames are temporally contiguous,
    - previous and following frames have the same unique exact harmony,
    - the middle frame must itself have NO exact chord interpretation,
    - the middle frame replaces exactly one anchor pitch class with one foreign
      pitch class,
    - exactly one event carries that foreign pitch class,
    - the ornament starts and ends exactly at the middle-frame boundaries,
    - the same staff/voice is unique on both neighboring frames,
    - the following voice lands on a structural pitch class of the anchor harmony,
    - appoggiatura = leap in + opposite-direction step out,
    - escape tone = step in + opposite-direction leap out.
    """

    if not isinstance(measure, Measure):
        raise TypeError("measure must be a Measure")

    frames = build_harmonic_frames(measure)
    observations: list[OrnamentalNCTObservation] = []

    for index in range(1, len(frames) - 1):
        previous = frames[index - 1]
        middle = frames[index]
        following = frames[index + 1]
        if previous.end.fraction != middle.start.fraction:
            continue
        if middle.end.fraction != following.start.fraction:
            continue

        anchor = _same_unique_anchor(previous, following)
        if anchor is None:
            continue
        if analyze_frame_exact(middle).status is not AnalysisStatus.NO_MATCH:
            continue

        anchor_pcs = frozenset(anchor.pitch_classes)
        middle_pcs = frozenset(middle.pitch_classes)
        foreign_pcs = middle_pcs - anchor_pcs
        missing_pcs = anchor_pcs - middle_pcs
        if len(foreign_pcs) != 1 or len(missing_pcs) != 1:
            continue
        foreign_pc = next(iter(foreign_pcs))

        foreign_events = tuple(
            event for event in middle.events if event.midi_pitch % 12 == foreign_pc
        )
        if len(foreign_events) != 1:
            continue
        event = foreign_events[0]
        if event.onset.fraction != middle.start.fraction:
            continue
        if event.end.fraction != middle.end.fraction:
            continue
        if event.tie is not TieState.NONE:
            continue

        previous_event = _unique_voice_event(previous, event.staff, event.voice)
        following_event = _unique_voice_event(following, event.staff, event.voice)
        if previous_event is None or following_event is None:
            continue
        if previous_event.end.fraction != middle.start.fraction:
            continue
        if following_event.onset.fraction != following.start.fraction:
            continue
        if following_event.midi_pitch % 12 not in anchor_pcs:
            continue

        approach = event.midi_pitch - previous_event.midi_pitch
        resolution = following_event.midi_pitch - event.midi_pitch
        kind = _classify_motion(approach, resolution)
        if kind is None:
            continue

        observations.append(
            OrnamentalNCTObservation(
                measure_number=measure.number,
                frame_index=index,
                start=middle.start,
                end=middle.end,
                staff=event.staff,
                voice=event.voice,
                midi_pitch=event.midi_pitch,
                pitch_class=foreign_pc,
                kind=kind,
                anchor_root_pc=anchor.root_pc,
                anchor_quality=anchor.quality,
                approach_semitones=approach,
                resolution_semitones=resolution,
            )
        )

    return tuple(observations)
