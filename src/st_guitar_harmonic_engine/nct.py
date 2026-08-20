"""Conservative stepwise non-chord-tone detection.

Only passing and neighbor tones are recognized, and only when the immediately
adjacent harmonic frames have the same unique exact chord candidate. The middle
frame must add exactly one pitch class to that anchor harmony, carried by one
unambiguous staff/voice event with stepwise melodic motion.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .chords import ChordQuality, generate_exact_chord_candidates
from .frames import HarmonicFrame, build_harmonic_frames
from .models import Measure, RationalBeat


class NCTKind(str, Enum):
    PASSING = "passing"
    NEIGHBOR = "neighbor"


@dataclass(frozen=True, slots=True)
class NCTObservation:
    """One conservatively detected non-chord tone in a harmonic-frame sequence."""

    measure_number: int
    frame_index: int
    start: RationalBeat
    end: RationalBeat
    staff: int
    voice: int
    midi_pitch: int
    pitch_class: int
    kind: NCTKind
    anchor_root_pc: int
    anchor_quality: ChordQuality

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
        if not isinstance(self.kind, NCTKind):
            raise TypeError("kind must be an NCTKind")
        if not 0 <= self.anchor_root_pc <= 11:
            raise ValueError("anchor_root_pc must be between 0 and 11")
        if not isinstance(self.anchor_quality, ChordQuality):
            raise TypeError("anchor_quality must be a ChordQuality")


def _unique_voice_event(frame: HarmonicFrame, staff: int, voice: int):
    matches = tuple(
        event for event in frame.events if event.staff == staff and event.voice == voice
    )
    return matches[0] if len(matches) == 1 else None


def _classify_stepwise(prev_pitch: int, middle_pitch: int, next_pitch: int) -> NCTKind | None:
    if prev_pitch == next_pitch and 1 <= abs(middle_pitch - prev_pitch) <= 2:
        return NCTKind.NEIGHBOR

    left = middle_pitch - prev_pitch
    right = next_pitch - middle_pitch
    if left == 0 or right == 0:
        return None
    if (left > 0) != (right > 0):
        return None
    if abs(left) not in (1, 2) or abs(right) not in (1, 2):
        return None
    return NCTKind.PASSING


def detect_stepwise_ncts(measure: Measure) -> tuple[NCTObservation, ...]:
    """Detect only high-confidence passing/neighbor tones within one measure.

    Safety gates:
    - previous and next frames must each have one exact candidate,
    - both anchor candidates must have the same root, quality, and pitch classes,
    - the middle frame may add exactly one pitch class and remove none,
    - exactly one event may carry that extra pitch class,
    - the same staff/voice must be unambiguous in both neighboring frames,
    - melodic motion must be semitone/whole-tone passing or neighbor motion.
    """

    if not isinstance(measure, Measure):
        raise TypeError("measure must be a Measure")

    frames = build_harmonic_frames(measure)
    observations: list[NCTObservation] = []
    for index in range(1, len(frames) - 1):
        previous = frames[index - 1]
        middle = frames[index]
        following = frames[index + 1]

        previous_candidates = generate_exact_chord_candidates(previous)
        following_candidates = generate_exact_chord_candidates(following)
        if len(previous_candidates) != 1 or len(following_candidates) != 1:
            continue

        anchor = previous_candidates[0]
        next_anchor = following_candidates[0]
        if (
            anchor.root_pc != next_anchor.root_pc
            or anchor.quality is not next_anchor.quality
            or anchor.pitch_classes != next_anchor.pitch_classes
        ):
            continue

        anchor_pcs = frozenset(anchor.pitch_classes)
        middle_pcs = frozenset(middle.pitch_classes)
        if not anchor_pcs.issubset(middle_pcs):
            continue
        extra_pcs = middle_pcs - anchor_pcs
        if len(extra_pcs) != 1:
            continue
        extra_pc = next(iter(extra_pcs))

        extra_events = tuple(
            event for event in middle.events if event.midi_pitch % 12 == extra_pc
        )
        if len(extra_events) != 1:
            continue
        event = extra_events[0]

        previous_event = _unique_voice_event(previous, event.staff, event.voice)
        following_event = _unique_voice_event(following, event.staff, event.voice)
        if previous_event is None or following_event is None:
            continue

        kind = _classify_stepwise(
            previous_event.midi_pitch,
            event.midi_pitch,
            following_event.midi_pitch,
        )
        if kind is None:
            continue

        observations.append(
            NCTObservation(
                measure_number=middle.measure_number,
                frame_index=index,
                start=middle.start,
                end=middle.end,
                staff=event.staff,
                voice=event.voice,
                midi_pitch=event.midi_pitch,
                pitch_class=extra_pc,
                kind=kind,
                anchor_root_pc=anchor.root_pc,
                anchor_quality=anchor.quality,
            )
        )

    return tuple(observations)
