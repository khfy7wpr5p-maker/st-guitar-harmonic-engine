"""Deterministic tonal-context resolution for exact chord candidates.

This layer does not infer non-chord tones, omissions, extensions, modulation, or
progression probabilities. It only annotates exact structural candidates against
an explicit tonic/mode context and narrows ambiguity when that context provides
one defensible match. Otherwise ambiguity is preserved.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .analysis import AnalysisStatus, CandidateAnalysis, FrameAnalysis, analyze_measure_exact
from .chords import ChordQuality
from .models import Measure


class TonalMode(str, Enum):
    MAJOR = "major"
    MINOR = "minor"


class HarmonicRole(str, Enum):
    TONIC = "tonic"
    PREDOMINANT = "predominant"
    DOMINANT = "dominant"
    DIATONIC = "diatonic"
    CHROMATIC = "chromatic"


class ResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    NO_MATCH = "no_match"


@dataclass(frozen=True, slots=True)
class TonalContext:
    """Explicit pitch-class tonic and major/minor mode supplied by the caller."""

    tonic_pc: int
    mode: TonalMode

    def __post_init__(self) -> None:
        if isinstance(self.tonic_pc, bool) or not isinstance(self.tonic_pc, int):
            raise TypeError("tonic_pc must be an int")
        if not 0 <= self.tonic_pc <= 11:
            raise ValueError("tonic_pc must be between 0 and 11")
        if not isinstance(self.mode, TonalMode):
            raise TypeError("mode must be a TonalMode")


@dataclass(frozen=True, slots=True)
class ContextCandidate:
    """One exact candidate annotated with conservative tonal-context evidence."""

    analysis: CandidateAnalysis
    in_context: bool
    scale_degree: int | None
    role: HarmonicRole

    def __post_init__(self) -> None:
        if not isinstance(self.analysis, CandidateAnalysis):
            raise TypeError("analysis must be a CandidateAnalysis")
        if not isinstance(self.in_context, bool):
            raise TypeError("in_context must be a bool")
        if not isinstance(self.role, HarmonicRole):
            raise TypeError("role must be a HarmonicRole")
        if self.in_context:
            if self.scale_degree not in range(1, 8):
                raise ValueError("in-context candidates require scale_degree 1..7")
            if self.role is HarmonicRole.CHROMATIC:
                raise ValueError("in-context candidate cannot have chromatic role")
        else:
            if self.scale_degree is not None:
                raise ValueError("out-of-context candidate must not have scale_degree")
            if self.role is not HarmonicRole.CHROMATIC:
                raise ValueError("out-of-context candidate must have chromatic role")


@dataclass(frozen=True, slots=True)
class ContextResolution:
    """Contextual result while retaining the complete exact-analysis evidence."""

    exact: FrameAnalysis
    context: TonalContext
    status: ResolutionStatus
    candidates: tuple[ContextCandidate, ...]
    selected: tuple[ContextCandidate, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.exact, FrameAnalysis):
            raise TypeError("exact must be a FrameAnalysis")
        if not isinstance(self.context, TonalContext):
            raise TypeError("context must be a TonalContext")
        if not isinstance(self.status, ResolutionStatus):
            raise TypeError("status must be a ResolutionStatus")
        if not isinstance(self.candidates, tuple) or any(
            not isinstance(item, ContextCandidate) for item in self.candidates
        ):
            raise TypeError("candidates must contain ContextCandidate values")
        if not isinstance(self.selected, tuple) or any(
            not isinstance(item, ContextCandidate) for item in self.selected
        ):
            raise TypeError("selected must contain ContextCandidate values")
        if tuple(item.analysis for item in self.candidates) != self.exact.candidates:
            raise ValueError("context candidates must preserve exact candidate order")
        if any(item not in self.candidates for item in self.selected):
            raise ValueError("selected candidates must come from candidates")

        if self.exact.status is AnalysisStatus.NO_MATCH:
            if self.candidates or self.selected or self.status is not ResolutionStatus.NO_MATCH:
                raise ValueError("no-match exact analysis must remain no-match")
            return

        if not self.selected:
            raise ValueError("non-empty exact analysis requires selected candidates")
        expected = (
            ResolutionStatus.RESOLVED
            if len(self.selected) == 1
            else ResolutionStatus.AMBIGUOUS
        )
        if self.status is not expected:
            raise ValueError("status does not match selected candidate cardinality")


# Rules are deliberately explicit. They cover basic diatonic major/minor harmony
# plus the common major V and raised-leading-tone diminished harmony in minor.
# No probability or progression preference is encoded here.
_MAJOR_RULES = (
    (0, frozenset({ChordQuality.MAJOR, ChordQuality.MAJOR_SEVENTH}), 1, HarmonicRole.TONIC),
    (2, frozenset({ChordQuality.MINOR, ChordQuality.MINOR_SEVENTH}), 2, HarmonicRole.PREDOMINANT),
    (4, frozenset({ChordQuality.MINOR, ChordQuality.MINOR_SEVENTH}), 3, HarmonicRole.DIATONIC),
    (5, frozenset({ChordQuality.MAJOR, ChordQuality.MAJOR_SEVENTH}), 4, HarmonicRole.PREDOMINANT),
    (7, frozenset({ChordQuality.MAJOR, ChordQuality.DOMINANT_SEVENTH}), 5, HarmonicRole.DOMINANT),
    (9, frozenset({ChordQuality.MINOR, ChordQuality.MINOR_SEVENTH}), 6, HarmonicRole.DIATONIC),
    (
        11,
        frozenset(
            {
                ChordQuality.DIMINISHED,
                ChordQuality.HALF_DIMINISHED_SEVENTH,
                ChordQuality.DIMINISHED_SEVENTH,
            }
        ),
        7,
        HarmonicRole.DOMINANT,
    ),
)

_MINOR_RULES = (
    (0, frozenset({ChordQuality.MINOR, ChordQuality.MINOR_SEVENTH}), 1, HarmonicRole.TONIC),
    (2, frozenset({ChordQuality.DIMINISHED, ChordQuality.HALF_DIMINISHED_SEVENTH}), 2, HarmonicRole.PREDOMINANT),
    (3, frozenset({ChordQuality.MAJOR, ChordQuality.MAJOR_SEVENTH}), 3, HarmonicRole.DIATONIC),
    (5, frozenset({ChordQuality.MINOR, ChordQuality.MINOR_SEVENTH}), 4, HarmonicRole.PREDOMINANT),
    (7, frozenset({ChordQuality.MINOR, ChordQuality.MINOR_SEVENTH}), 5, HarmonicRole.DIATONIC),
    (7, frozenset({ChordQuality.MAJOR, ChordQuality.DOMINANT_SEVENTH}), 5, HarmonicRole.DOMINANT),
    (8, frozenset({ChordQuality.MAJOR, ChordQuality.MAJOR_SEVENTH}), 6, HarmonicRole.DIATONIC),
    (10, frozenset({ChordQuality.MAJOR, ChordQuality.DOMINANT_SEVENTH}), 7, HarmonicRole.DIATONIC),
    (11, frozenset({ChordQuality.DIMINISHED, ChordQuality.DIMINISHED_SEVENTH}), 7, HarmonicRole.DOMINANT),
)


def _annotate_candidate(
    analysis: CandidateAnalysis,
    context: TonalContext,
) -> ContextCandidate:
    offset = (analysis.candidate.root_pc - context.tonic_pc) % 12
    rules = _MAJOR_RULES if context.mode is TonalMode.MAJOR else _MINOR_RULES
    for root_offset, qualities, degree, role in rules:
        if offset == root_offset and analysis.candidate.quality in qualities:
            return ContextCandidate(
                analysis=analysis,
                in_context=True,
                scale_degree=degree,
                role=role,
            )
    return ContextCandidate(
        analysis=analysis,
        in_context=False,
        scale_degree=None,
        role=HarmonicRole.CHROMATIC,
    )


def resolve_frame_in_context(
    exact: FrameAnalysis,
    context: TonalContext,
) -> ContextResolution:
    """Resolve an exact frame using only explicit tonal-context membership.

    If an ambiguous exact result contains one or more context-compatible
    candidates, only those are selected. If context supplies no compatible
    candidate, the full exact ambiguity is retained rather than guessed away.
    """

    if not isinstance(exact, FrameAnalysis):
        raise TypeError("exact must be a FrameAnalysis")
    if not isinstance(context, TonalContext):
        raise TypeError("context must be a TonalContext")

    candidates = tuple(_annotate_candidate(item, context) for item in exact.candidates)
    if exact.status is AnalysisStatus.NO_MATCH:
        return ContextResolution(
            exact=exact,
            context=context,
            status=ResolutionStatus.NO_MATCH,
            candidates=(),
            selected=(),
        )

    contextual = tuple(item for item in candidates if item.in_context)
    selected = contextual or candidates
    status = (
        ResolutionStatus.RESOLVED
        if len(selected) == 1
        else ResolutionStatus.AMBIGUOUS
    )
    return ContextResolution(
        exact=exact,
        context=context,
        status=status,
        candidates=candidates,
        selected=selected,
    )


def analyze_measure_in_context(
    measure: Measure,
    context: TonalContext,
) -> tuple[ContextResolution, ...]:
    """Run exact measure analysis, then apply conservative tonal context."""

    if not isinstance(measure, Measure):
        raise TypeError("measure must be a Measure")
    if not isinstance(context, TonalContext):
        raise TypeError("context must be a TonalContext")
    return tuple(
        resolve_frame_in_context(exact, context)
        for exact in analyze_measure_exact(measure)
    )
