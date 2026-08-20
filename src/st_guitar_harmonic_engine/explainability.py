"""Read-only explainability aggregation for conservative harmony evidence.

This module exposes NCT and incomplete-chord evidence without participating in
exact analysis or tonal-context resolution. It must not select, rank, replace, or
mutate authoritative harmonic decisions.
"""

from __future__ import annotations

from dataclasses import dataclass

from .frames import build_harmonic_frames
from .models import Measure, RationalBeat
from .nct import NCTObservation, detect_stepwise_ncts
from .omissions import IncompleteChordCandidate, generate_fifth_omission_candidates


@dataclass(frozen=True, slots=True)
class FrameExplainability:
    """Non-authoritative evidence attached to one harmonic-frame position."""

    measure_number: int
    frame_index: int
    start: RationalBeat
    end: RationalBeat
    ncts: tuple[NCTObservation, ...]
    omissions: tuple[IncompleteChordCandidate, ...]

    def __post_init__(self) -> None:
        if self.measure_number < 1:
            raise ValueError("measure_number must be at least 1")
        if self.frame_index < 0:
            raise ValueError("frame_index must be non-negative")
        if not isinstance(self.start, RationalBeat) or not isinstance(self.end, RationalBeat):
            raise TypeError("start and end must be RationalBeat values")
        if self.start.fraction >= self.end.fraction:
            raise ValueError("frame start must be before end")
        if not isinstance(self.ncts, tuple) or any(
            not isinstance(item, NCTObservation) for item in self.ncts
        ):
            raise TypeError("ncts must contain NCTObservation values")
        if not isinstance(self.omissions, tuple) or any(
            not isinstance(item, IncompleteChordCandidate) for item in self.omissions
        ):
            raise TypeError("omissions must contain IncompleteChordCandidate values")
        if any(item.measure_number != self.measure_number for item in self.ncts):
            raise ValueError("NCT evidence must belong to the same measure")
        if any(item.frame_index != self.frame_index for item in self.ncts):
            raise ValueError("NCT evidence must belong to this frame index")


@dataclass(frozen=True, slots=True)
class MeasureExplainability:
    """Read-only evidence report for one measure.

    The report intentionally contains no UNIQUE/AMBIGUOUS/NO_MATCH or contextual
    selection field. Authoritative decisions remain owned by analysis/context.
    """

    measure_number: int
    frames: tuple[FrameExplainability, ...]

    def __post_init__(self) -> None:
        if self.measure_number < 1:
            raise ValueError("measure_number must be at least 1")
        if not isinstance(self.frames, tuple) or any(
            not isinstance(item, FrameExplainability) for item in self.frames
        ):
            raise TypeError("frames must contain FrameExplainability values")
        if any(item.measure_number != self.measure_number for item in self.frames):
            raise ValueError("all frame evidence must belong to the same measure")
        if tuple(item.frame_index for item in self.frames) != tuple(range(len(self.frames))):
            raise ValueError("frame evidence must preserve canonical frame ordering")


def build_measure_explainability(measure: Measure) -> MeasureExplainability:
    """Aggregate NCT and omission evidence without altering harmonic decisions."""

    if not isinstance(measure, Measure):
        raise TypeError("measure must be a Measure")

    frames = build_harmonic_frames(measure)
    ncts_by_frame: dict[int, list[NCTObservation]] = {}
    for observation in detect_stepwise_ncts(measure):
        ncts_by_frame.setdefault(observation.frame_index, []).append(observation)

    evidence = tuple(
        FrameExplainability(
            measure_number=frame.measure_number,
            frame_index=index,
            start=frame.start,
            end=frame.end,
            ncts=tuple(ncts_by_frame.get(index, ())),
            omissions=generate_fifth_omission_candidates(frame),
        )
        for index, frame in enumerate(frames)
    )
    return MeasureExplainability(measure_number=measure.number, frames=evidence)
