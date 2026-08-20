"""Exact deterministic orchestration across frames, candidates, and bass."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .chords import ChordCandidate, generate_exact_chord_candidates
from .frames import HarmonicFrame, build_harmonic_frames
from .inversion import BassAnalysis, analyze_bass_and_inversion
from .models import Measure, RationalBeat


class AnalysisStatus(str, Enum):
    UNIQUE = "unique"
    AMBIGUOUS = "ambiguous"
    NO_MATCH = "no_match"


@dataclass(frozen=True, slots=True)
class CandidateAnalysis:
    candidate: ChordCandidate
    bass: BassAnalysis

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, ChordCandidate):
            raise TypeError("candidate must be a ChordCandidate")
        if not isinstance(self.bass, BassAnalysis):
            raise TypeError("bass must be a BassAnalysis")


@dataclass(frozen=True, slots=True)
class FrameAnalysis:
    """Exact-analysis result for one harmonic frame."""

    measure_number: int
    start: RationalBeat
    end: RationalBeat
    status: AnalysisStatus
    candidates: tuple[CandidateAnalysis, ...]

    def __post_init__(self) -> None:
        if self.measure_number < 1:
            raise ValueError("measure_number must be at least 1")
        if not isinstance(self.start, RationalBeat) or not isinstance(self.end, RationalBeat):
            raise TypeError("start and end must be RationalBeat values")
        if self.start.fraction >= self.end.fraction:
            raise ValueError("analysis start must be before end")
        if not isinstance(self.status, AnalysisStatus):
            raise TypeError("status must be an AnalysisStatus")
        if not isinstance(self.candidates, tuple):
            raise TypeError("candidates must be a tuple")
        if any(not isinstance(item, CandidateAnalysis) for item in self.candidates):
            raise TypeError("candidates must contain CandidateAnalysis values")

        expected = (
            AnalysisStatus.NO_MATCH
            if len(self.candidates) == 0
            else AnalysisStatus.UNIQUE
            if len(self.candidates) == 1
            else AnalysisStatus.AMBIGUOUS
        )
        if self.status is not expected:
            raise ValueError("status does not match candidate cardinality")


def analyze_frame_exact(frame: HarmonicFrame) -> FrameAnalysis:
    """Run only exact deterministic analysis for one frame."""

    if not isinstance(frame, HarmonicFrame):
        raise TypeError("frame must be a HarmonicFrame")

    chord_candidates = generate_exact_chord_candidates(frame)
    analyses = tuple(
        CandidateAnalysis(
            candidate=candidate,
            bass=analyze_bass_and_inversion(frame, candidate),
        )
        for candidate in chord_candidates
    )
    status = (
        AnalysisStatus.NO_MATCH
        if not analyses
        else AnalysisStatus.UNIQUE
        if len(analyses) == 1
        else AnalysisStatus.AMBIGUOUS
    )
    return FrameAnalysis(
        measure_number=frame.measure_number,
        start=frame.start,
        end=frame.end,
        status=status,
        candidates=analyses,
    )


def analyze_measure_exact(measure: Measure) -> tuple[FrameAnalysis, ...]:
    """Analyze every non-silent harmonic frame in one measure exactly."""

    if not isinstance(measure, Measure):
        raise TypeError("measure must be a Measure")
    return tuple(analyze_frame_exact(frame) for frame in build_harmonic_frames(measure))
