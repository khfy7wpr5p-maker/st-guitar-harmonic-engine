"""Conservative sustained-pedal evidence.

Stage 2-E detects only high-confidence pedal points carried by one physical
``NoteEvent`` across at least three consecutive harmonic frames. The detector
removes that event hypothetically, requires every reduced frame to have one
unique exact harmony, and emits evidence only when those underlying harmonies
change while the sustained pitch is structural in some frames and foreign in
others. No harmonic, contextual, or structural decision is mutated.
"""

from __future__ import annotations

from dataclasses import dataclass

from .analysis import AnalysisStatus, analyze_frame_exact
from .chords import ChordQuality
from .frames import HarmonicFrame, build_harmonic_frames
from .models import Measure, NoteEvent, RationalBeat


@dataclass(frozen=True, slots=True)
class PedalFrameEvidence:
    """Underlying unique exact harmony for one frame after removing the pedal."""

    frame_index: int
    start: RationalBeat
    end: RationalBeat
    root_pc: int
    quality: ChordQuality
    pedal_is_chord_tone: bool

    def __post_init__(self) -> None:
        if isinstance(self.frame_index, bool) or not isinstance(self.frame_index, int):
            raise TypeError("frame_index must be an int")
        if self.frame_index < 0:
            raise ValueError("frame_index must not be negative")
        if not isinstance(self.start, RationalBeat) or not isinstance(self.end, RationalBeat):
            raise TypeError("start and end must be RationalBeat values")
        if self.start.fraction >= self.end.fraction:
            raise ValueError("evidence start must be before end")
        if isinstance(self.root_pc, bool) or not isinstance(self.root_pc, int):
            raise TypeError("root_pc must be an int")
        if not 0 <= self.root_pc <= 11:
            raise ValueError("root_pc must be between 0 and 11")
        if not isinstance(self.quality, ChordQuality):
            raise TypeError("quality must be a ChordQuality")
        if not isinstance(self.pedal_is_chord_tone, bool):
            raise TypeError("pedal_is_chord_tone must be a bool")


@dataclass(frozen=True, slots=True)
class PedalObservation:
    """One sustained event with changing, uniquely identified harmony beneath it."""

    measure_number: int
    first_frame_index: int
    last_frame_index: int
    start: RationalBeat
    end: RationalBeat
    staff: int
    voice: int
    midi_pitch: int
    pitch_class: int
    frames: tuple[PedalFrameEvidence, ...]

    def __post_init__(self) -> None:
        if isinstance(self.measure_number, bool) or not isinstance(self.measure_number, int):
            raise TypeError("measure_number must be an int")
        if self.measure_number < 1:
            raise ValueError("measure_number must be at least 1")
        for name in ("first_frame_index", "last_frame_index"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an int")
        if self.first_frame_index < 0:
            raise ValueError("first_frame_index must not be negative")
        if self.last_frame_index < self.first_frame_index:
            raise ValueError("last_frame_index must not precede first_frame_index")
        if not isinstance(self.start, RationalBeat) or not isinstance(self.end, RationalBeat):
            raise TypeError("start and end must be RationalBeat values")
        if self.start.fraction >= self.end.fraction:
            raise ValueError("observation start must be before end")
        for name in ("staff", "voice", "midi_pitch", "pitch_class"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an int")
        if self.staff < 1 or self.voice < 1:
            raise ValueError("staff and voice must be at least 1")
        if not 0 <= self.midi_pitch <= 127:
            raise ValueError("midi_pitch must be between 0 and 127")
        if self.pitch_class != self.midi_pitch % 12:
            raise ValueError("pitch_class must match midi_pitch")
        if not isinstance(self.frames, tuple):
            raise TypeError("frames must be a tuple")
        if len(self.frames) < 3:
            raise ValueError("pedal evidence must span at least three frames")
        if any(not isinstance(item, PedalFrameEvidence) for item in self.frames):
            raise TypeError("frames must contain PedalFrameEvidence values")

        expected_indices = tuple(range(self.first_frame_index, self.last_frame_index + 1))
        actual_indices = tuple(item.frame_index for item in self.frames)
        if actual_indices != expected_indices:
            raise ValueError("pedal frame evidence must be consecutive and complete")
        if self.frames[0].start != self.start or self.frames[-1].end != self.end:
            raise ValueError("observation bounds must match frame evidence")
        for previous, following in zip(self.frames, self.frames[1:]):
            if previous.end != following.start:
                raise ValueError("pedal frame evidence must be temporally contiguous")

        harmony_keys = {(item.root_pc, item.quality) for item in self.frames}
        if len(harmony_keys) < 2:
            raise ValueError("pedal evidence requires changing underlying harmony")
        chord_tone_flags = {item.pedal_is_chord_tone for item in self.frames}
        if chord_tone_flags != {False, True}:
            raise ValueError("pedal must be structural in some frames and foreign in others")


def _event_is_active(frame: HarmonicFrame, event: NoteEvent) -> bool:
    return any(active is event for active in frame.events)


def _without_event(frame: HarmonicFrame, event: NoteEvent) -> HarmonicFrame | None:
    remaining = tuple(active for active in frame.events if active is not event)
    if not remaining:
        return None
    return HarmonicFrame(
        measure_number=frame.measure_number,
        start=frame.start,
        end=frame.end,
        events=remaining,
    )


def detect_pedals(measure: Measure) -> tuple[PedalObservation, ...]:
    """Return high-confidence sustained-pedal evidence without changing decisions.

    Safety gates:
    - one physical ``NoteEvent`` must remain active for at least three frames,
    - those frames must be consecutive and temporally contiguous,
    - removing only that event must leave a non-silent frame each time,
    - every reduced frame must resolve to exactly one exact chord candidate,
    - the reduced harmonies must contain at least two distinct harmonies,
    - the sustained pitch class must be a chord tone in at least one reduced
      harmony and a non-chord tone in at least one other reduced harmony.

    Explicit tie chains and rearticulated notes are deliberately not combined;
    they are separate physical events and remain unresolved at this stage.
    """

    if not isinstance(measure, Measure):
        raise TypeError("measure must be a Measure")

    frames = build_harmonic_frames(measure)
    if len(frames) < 3:
        return ()

    observations: list[PedalObservation] = []

    for event in measure.events:
        active_indices = tuple(
            index for index, frame in enumerate(frames) if _event_is_active(frame, event)
        )
        if len(active_indices) < 3:
            continue

        first = active_indices[0]
        last = active_indices[-1]
        if active_indices != tuple(range(first, last + 1)):
            continue

        active_frames = frames[first : last + 1]
        if any(
            previous.end.fraction != following.start.fraction
            for previous, following in zip(active_frames, active_frames[1:])
        ):
            continue

        frame_evidence: list[PedalFrameEvidence] = []
        failed = False
        for frame_index, frame in zip(active_indices, active_frames):
            reduced = _without_event(frame, event)
            if reduced is None:
                failed = True
                break
            analysis = analyze_frame_exact(reduced)
            if analysis.status is not AnalysisStatus.UNIQUE:
                failed = True
                break
            candidate = analysis.candidates[0].candidate
            frame_evidence.append(
                PedalFrameEvidence(
                    frame_index=frame_index,
                    start=frame.start,
                    end=frame.end,
                    root_pc=candidate.root_pc,
                    quality=candidate.quality,
                    pedal_is_chord_tone=(event.midi_pitch % 12) in candidate.pitch_classes,
                )
            )

        if failed:
            continue

        harmony_keys = {(item.root_pc, item.quality) for item in frame_evidence}
        if len(harmony_keys) < 2:
            continue
        chord_tone_flags = {item.pedal_is_chord_tone for item in frame_evidence}
        if chord_tone_flags != {False, True}:
            continue

        observations.append(
            PedalObservation(
                measure_number=measure.number,
                first_frame_index=first,
                last_frame_index=last,
                start=active_frames[0].start,
                end=active_frames[-1].end,
                staff=event.staff,
                voice=event.voice,
                midi_pitch=event.midi_pitch,
                pitch_class=event.midi_pitch % 12,
                frames=tuple(frame_evidence),
            )
        )

    return tuple(
        sorted(
            observations,
            key=lambda item: (
                item.first_frame_index,
                item.last_frame_index,
                item.staff,
                item.voice,
                item.midi_pitch,
            ),
        )
    )
