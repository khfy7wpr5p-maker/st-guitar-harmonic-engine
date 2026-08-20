"""Conservative prepared-suspension evidence.

Stage 2-B detects only high-confidence prepared suspensions. It produces evidence
only and does not alter exact analysis, tonal-context resolution, or Stage 2-A
structural segmentation.
"""

from __future__ import annotations

from dataclasses import dataclass

from .analysis import AnalysisStatus, analyze_frame_exact
from .chords import ChordQuality
from .frames import HarmonicFrame, build_harmonic_frames
from .models import Measure, NoteEvent, RationalBeat, TieState


@dataclass(frozen=True, slots=True)
class SuspensionObservation:
    """One prepared dissonance held into a new harmony and resolved downward."""

    measure_number: int
    frame_index: int
    start: RationalBeat
    end: RationalBeat
    staff: int
    voice: int
    midi_pitch: int
    pitch_class: int
    resolution_midi_pitch: int
    resolution_pitch_class: int
    preparation_root_pc: int
    preparation_quality: ChordQuality
    resolution_root_pc: int
    resolution_quality: ChordQuality

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
        for field_name in ("midi_pitch", "resolution_midi_pitch"):
            value = getattr(self, field_name)
            if not 0 <= value <= 127:
                raise ValueError(f"{field_name} must be between 0 and 127")
        if self.pitch_class != self.midi_pitch % 12:
            raise ValueError("pitch_class must match midi_pitch")
        if self.resolution_pitch_class != self.resolution_midi_pitch % 12:
            raise ValueError("resolution_pitch_class must match resolution_midi_pitch")
        if self.midi_pitch - self.resolution_midi_pitch not in (1, 2):
            raise ValueError("suspension must resolve downward by semitone or whole tone")
        for field_name in ("preparation_root_pc", "resolution_root_pc"):
            value = getattr(self, field_name)
            if not 0 <= value <= 11:
                raise ValueError(f"{field_name} must be between 0 and 11")
        if not isinstance(self.preparation_quality, ChordQuality):
            raise TypeError("preparation_quality must be a ChordQuality")
        if not isinstance(self.resolution_quality, ChordQuality):
            raise TypeError("resolution_quality must be a ChordQuality")


def _unique_voice_event(frame: HarmonicFrame, staff: int, voice: int) -> NoteEvent | None:
    matches = tuple(
        event for event in frame.events if event.staff == staff and event.voice == voice
    )
    return matches[0] if len(matches) == 1 else None


def _is_prepared_hold(previous: NoteEvent, middle: NoteEvent) -> bool:
    if previous.midi_pitch != middle.midi_pitch:
        return False
    if previous is middle:
        return True
    if previous.end.fraction != middle.onset.fraction:
        return False
    return (
        previous.tie in (TieState.START, TieState.CONTINUE)
        and middle.tie in (TieState.CONTINUE, TieState.STOP)
    )


def detect_suspensions(measure: Measure) -> tuple[SuspensionObservation, ...]:
    """Detect only prepared, downward-step suspensions across three frames.

    Safety gates:
    - frames must be temporally contiguous (no silent gaps),
    - preparation and resolution frames must each have one exact chord candidate,
    - those exact harmonies must differ,
    - the middle frame must replace exactly one resolution-harmony pitch class with
      exactly one foreign pitch class,
    - exactly one event may carry that foreign pitch class,
    - the same staff/voice must prepare the same pitch in the previous frame,
    - the preparation must be a sustained event or an explicit tie chain,
    - the same staff/voice must resolve downward by semitone/whole tone to the
      missing pitch class in the following frame.
    """

    if not isinstance(measure, Measure):
        raise TypeError("measure must be a Measure")

    frames = build_harmonic_frames(measure)
    observations: list[SuspensionObservation] = []

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

        preparation = previous_analysis.candidates[0].candidate
        resolution = following_analysis.candidates[0].candidate
        if (
            preparation.root_pc == resolution.root_pc
            and preparation.quality is resolution.quality
            and preparation.pitch_classes == resolution.pitch_classes
        ):
            continue

        target_pcs = frozenset(resolution.pitch_classes)
        middle_pcs = frozenset(middle.pitch_classes)
        foreign_pcs = middle_pcs - target_pcs
        missing_pcs = target_pcs - middle_pcs
        if len(foreign_pcs) != 1 or len(missing_pcs) != 1:
            continue

        foreign_pc = next(iter(foreign_pcs))
        resolution_pc = next(iter(missing_pcs))
        if foreign_pc not in preparation.pitch_classes:
            continue

        foreign_events = tuple(
            event for event in middle.events if event.midi_pitch % 12 == foreign_pc
        )
        if len(foreign_events) != 1:
            continue
        middle_event = foreign_events[0]

        previous_event = _unique_voice_event(previous, middle_event.staff, middle_event.voice)
        following_event = _unique_voice_event(following, middle_event.staff, middle_event.voice)
        if previous_event is None or following_event is None:
            continue
        if not _is_prepared_hold(previous_event, middle_event):
            continue
        if following_event.midi_pitch % 12 != resolution_pc:
            continue
        if middle_event.midi_pitch - following_event.midi_pitch not in (1, 2):
            continue

        observations.append(
            SuspensionObservation(
                measure_number=measure.number,
                frame_index=index,
                start=middle.start,
                end=middle.end,
                staff=middle_event.staff,
                voice=middle_event.voice,
                midi_pitch=middle_event.midi_pitch,
                pitch_class=foreign_pc,
                resolution_midi_pitch=following_event.midi_pitch,
                resolution_pitch_class=resolution_pc,
                preparation_root_pc=preparation.root_pc,
                preparation_quality=preparation.quality,
                resolution_root_pc=resolution.root_pc,
                resolution_quality=resolution.quality,
            )
        )

    return tuple(observations)
