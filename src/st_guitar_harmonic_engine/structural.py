"""Deterministic harmonic-boundary and structural-segmentation resolver.

Stage 2-A groups canonical harmonic frames without changing exact or tonal-context
harmony decisions. Frame boundaries are treated only as candidate transition
points. Unresolved evidence always cuts a segment rather than being hidden as a
continuation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .analysis import AnalysisStatus, FrameAnalysis, analyze_frame_exact
from .chords import ChordCandidate
from .frames import HarmonicFrame, build_harmonic_frames
from .models import Measure, RationalBeat
from .nct import NCTObservation, detect_stepwise_ncts
from .omissions import generate_fifth_omission_candidates


class BoundaryDisposition(str, Enum):
    BOUNDARY = "boundary"
    CONTINUATION = "continuation"
    UNRESOLVED = "unresolved"


class BoundaryReason(str, Enum):
    SILENCE_GAP = "silence_gap"
    SAME_EXACT_HARMONY = "same_exact_harmony"
    EXACT_HARMONY_CHANGE = "exact_harmony_change"
    NCT_BRIDGE = "nct_bridge"
    MATCHING_FIFTH_OMISSION = "matching_fifth_omission"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


_REASON_DISPOSITION = {
    BoundaryReason.SILENCE_GAP: BoundaryDisposition.BOUNDARY,
    BoundaryReason.SAME_EXACT_HARMONY: BoundaryDisposition.CONTINUATION,
    BoundaryReason.EXACT_HARMONY_CHANGE: BoundaryDisposition.BOUNDARY,
    BoundaryReason.NCT_BRIDGE: BoundaryDisposition.CONTINUATION,
    BoundaryReason.MATCHING_FIFTH_OMISSION: BoundaryDisposition.CONTINUATION,
    BoundaryReason.INSUFFICIENT_EVIDENCE: BoundaryDisposition.UNRESOLVED,
}


@dataclass(frozen=True, slots=True)
class StructuralTransition:
    """Deterministic relation between two adjacent canonical harmonic frames."""

    measure_number: int
    left_frame_index: int
    right_frame_index: int
    position: RationalBeat
    disposition: BoundaryDisposition
    reason: BoundaryReason

    def __post_init__(self) -> None:
        if self.measure_number < 1:
            raise ValueError("measure_number must be at least 1")
        if self.left_frame_index < 0:
            raise ValueError("left_frame_index must be non-negative")
        if self.right_frame_index != self.left_frame_index + 1:
            raise ValueError("transition frames must be adjacent")
        if not isinstance(self.position, RationalBeat):
            raise TypeError("position must be a RationalBeat")
        if not isinstance(self.disposition, BoundaryDisposition):
            raise TypeError("disposition must be a BoundaryDisposition")
        if not isinstance(self.reason, BoundaryReason):
            raise TypeError("reason must be a BoundaryReason")
        if self.disposition is not _REASON_DISPOSITION[self.reason]:
            raise ValueError("disposition must match the deterministic reason policy")


@dataclass(frozen=True, slots=True)
class StructuralSegment:
    """A maximal run of frames connected only by CONTINUATION transitions."""

    measure_number: int
    segment_index: int
    first_frame_index: int
    last_frame_index: int
    start: RationalBeat
    end: RationalBeat

    def __post_init__(self) -> None:
        if self.measure_number < 1:
            raise ValueError("measure_number must be at least 1")
        if self.segment_index < 0:
            raise ValueError("segment_index must be non-negative")
        if self.first_frame_index < 0:
            raise ValueError("first_frame_index must be non-negative")
        if self.last_frame_index < self.first_frame_index:
            raise ValueError("last_frame_index must not precede first_frame_index")
        if not isinstance(self.start, RationalBeat) or not isinstance(self.end, RationalBeat):
            raise TypeError("start and end must be RationalBeat values")
        if self.start.fraction >= self.end.fraction:
            raise ValueError("segment start must be before end")


@dataclass(frozen=True, slots=True)
class StructuralSegmentation:
    """Stage 2-A structural result for one measure."""

    measure_number: int
    transitions: tuple[StructuralTransition, ...]
    segments: tuple[StructuralSegment, ...]

    def __post_init__(self) -> None:
        if self.measure_number < 1:
            raise ValueError("measure_number must be at least 1")
        if not isinstance(self.transitions, tuple) or any(
            not isinstance(item, StructuralTransition) for item in self.transitions
        ):
            raise TypeError("transitions must contain StructuralTransition values")
        if not isinstance(self.segments, tuple) or any(
            not isinstance(item, StructuralSegment) for item in self.segments
        ):
            raise TypeError("segments must contain StructuralSegment values")
        if any(item.measure_number != self.measure_number for item in self.transitions):
            raise ValueError("all transitions must belong to the same measure")
        if any(item.measure_number != self.measure_number for item in self.segments):
            raise ValueError("all segments must belong to the same measure")
        if tuple(item.segment_index for item in self.segments) != tuple(range(len(self.segments))):
            raise ValueError("segment indexes must be canonical and contiguous")
        for previous, current in zip(self.segments, self.segments[1:]):
            if previous.last_frame_index >= current.first_frame_index:
                raise ValueError("segments must not overlap")


def _candidate_identity(candidate: ChordCandidate) -> tuple[int, object, tuple[int, ...]]:
    return candidate.root_pc, candidate.quality, candidate.pitch_classes


def _unique_candidate(analysis: FrameAnalysis) -> ChordCandidate | None:
    if analysis.status is not AnalysisStatus.UNIQUE:
        return None
    return analysis.candidates[0].candidate


def _has_nct_bridge(
    left_index: int,
    right_index: int,
    observations: tuple[NCTObservation, ...],
) -> bool:
    return any(
        observation.frame_index in (left_index, right_index)
        for observation in observations
    )


def _matches_unique_fifth_omission(
    exact_analysis: FrameAnalysis,
    other_frame: HarmonicFrame,
) -> bool:
    exact = _unique_candidate(exact_analysis)
    if exact is None:
        return False
    omissions = generate_fifth_omission_candidates(other_frame)
    if len(omissions) != 1:
        return False
    omission = omissions[0]
    return (
        omission.root_pc == exact.root_pc
        and omission.quality is exact.quality
        and omission.full_pitch_classes == exact.pitch_classes
    )


def _resolve_transition_reason(
    left_index: int,
    right_index: int,
    left_frame: HarmonicFrame,
    right_frame: HarmonicFrame,
    left_analysis: FrameAnalysis,
    right_analysis: FrameAnalysis,
    observations: tuple[NCTObservation, ...],
) -> BoundaryReason:
    # Rule 1: a real silent gap is always a structural boundary.
    if left_frame.end.fraction < right_frame.start.fraction:
        return BoundaryReason.SILENCE_GAP

    # Rule 2: a conservatively verified passing/neighbor frame bridges its anchors.
    if _has_nct_bridge(left_index, right_index, observations):
        return BoundaryReason.NCT_BRIDGE

    # Rules 3-4: unique exact harmony is the strongest direct harmonic evidence.
    left_exact = _unique_candidate(left_analysis)
    right_exact = _unique_candidate(right_analysis)
    if left_exact is not None and right_exact is not None:
        if _candidate_identity(left_exact) == _candidate_identity(right_exact):
            return BoundaryReason.SAME_EXACT_HARMONY
        return BoundaryReason.EXACT_HARMONY_CHANGE

    # Rule 5: one exact anchor may bridge one uniquely matching missing-fifth frame.
    if _matches_unique_fifth_omission(left_analysis, right_frame) or _matches_unique_fifth_omission(
        right_analysis, left_frame
    ):
        return BoundaryReason.MATCHING_FIFTH_OMISSION

    # Rule 6: ambiguity or insufficient evidence is never silently merged.
    return BoundaryReason.INSUFFICIENT_EVIDENCE


def segment_measure_structurally(measure: Measure) -> StructuralSegmentation:
    """Return deterministic harmonic segments without mutating harmony decisions.

    Rule priority is fixed:
    1. silence gap -> BOUNDARY
    2. verified passing/neighbor bridge -> CONTINUATION
    3. same unique exact harmony -> CONTINUATION
    4. different unique exact harmony -> BOUNDARY
    5. unique exact anchor + uniquely matching fifth omission -> CONTINUATION
    6. all other evidence -> UNRESOLVED

    Both BOUNDARY and UNRESOLVED cut structural segments.
    """

    if not isinstance(measure, Measure):
        raise TypeError("measure must be a Measure")

    frames = build_harmonic_frames(measure)
    if not frames:
        return StructuralSegmentation(measure.number, (), ())

    analyses = tuple(analyze_frame_exact(frame) for frame in frames)
    observations = detect_stepwise_ncts(measure)

    transitions: list[StructuralTransition] = []
    for left_index in range(len(frames) - 1):
        right_index = left_index + 1
        reason = _resolve_transition_reason(
            left_index,
            right_index,
            frames[left_index],
            frames[right_index],
            analyses[left_index],
            analyses[right_index],
            observations,
        )
        transitions.append(
            StructuralTransition(
                measure_number=measure.number,
                left_frame_index=left_index,
                right_frame_index=right_index,
                position=frames[right_index].start,
                disposition=_REASON_DISPOSITION[reason],
                reason=reason,
            )
        )

    segments: list[StructuralSegment] = []
    first_frame_index = 0
    for transition in transitions:
        if transition.disposition is BoundaryDisposition.CONTINUATION:
            continue
        last_frame_index = transition.left_frame_index
        segments.append(
            StructuralSegment(
                measure_number=measure.number,
                segment_index=len(segments),
                first_frame_index=first_frame_index,
                last_frame_index=last_frame_index,
                start=frames[first_frame_index].start,
                end=frames[last_frame_index].end,
            )
        )
        first_frame_index = transition.right_frame_index

    segments.append(
        StructuralSegment(
            measure_number=measure.number,
            segment_index=len(segments),
            first_frame_index=first_frame_index,
            last_frame_index=len(frames) - 1,
            start=frames[first_frame_index].start,
            end=frames[-1].end,
        )
    )

    return StructuralSegmentation(
        measure_number=measure.number,
        transitions=tuple(transitions),
        segments=tuple(segments),
    )
