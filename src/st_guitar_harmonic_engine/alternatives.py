"""Candidate alternatives reporting contract for Stage 4-F.

Alternatives are descriptive output derived from an already gated decision. This
module never changes the authoritative resolver decision or abstention result.
"""

from __future__ import annotations

from dataclasses import dataclass

from .abstention import FinalDecisionState, GatedDecision
from .confidence import ConfidenceAssessment
from .ranking import rank_candidates
from .resolver import ResolverCandidate, ResolverStatus
from .strength import assess_candidate_strength


@dataclass(frozen=True, slots=True)
class CandidateAlternative:
    candidate: ResolverCandidate
    confidence: ConfidenceAssessment

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, ResolverCandidate):
            raise TypeError("candidate must be a ResolverCandidate")
        if not isinstance(self.confidence, ConfidenceAssessment):
            raise TypeError("confidence must be a ConfidenceAssessment")
        if assess_candidate_strength(self.candidate) != self.confidence:
            raise ValueError("alternative confidence must match candidate evidence")


@dataclass(frozen=True, slots=True)
class AlternativeReport:
    primary: ResolverCandidate | None
    alternatives: tuple[CandidateAlternative, ...]

    def __post_init__(self) -> None:
        if self.primary is not None and not isinstance(self.primary, ResolverCandidate):
            raise TypeError("primary must be a ResolverCandidate or None")
        if not isinstance(self.alternatives, tuple) or any(
            not isinstance(item, CandidateAlternative) for item in self.alternatives
        ):
            raise TypeError("alternatives must contain CandidateAlternative values")
        identities = [item.candidate.identity for item in self.alternatives]
        if len(set(identities)) != len(identities):
            raise ValueError("alternative identities must be unique")
        if self.primary is not None and self.primary.identity in identities:
            raise ValueError("primary cannot also appear in alternatives")


def _ordered_candidates(
    candidates: tuple[ResolverCandidate, ...],
) -> tuple[ResolverCandidate, ...]:
    return tuple(
        candidate
        for group in rank_candidates(candidates)
        for candidate in group.candidates
    )


def build_alternative_report(
    all_candidates: tuple[ResolverCandidate, ...],
    gated: GatedDecision,
) -> AlternativeReport:
    """Build deterministic primary/alternative output from a completed gate."""

    if not isinstance(all_candidates, tuple) or any(
        not isinstance(item, ResolverCandidate) for item in all_candidates
    ):
        raise TypeError("all_candidates must contain ResolverCandidate values")
    if len({item.identity for item in all_candidates}) != len(all_candidates):
        raise ValueError("candidate identities must be unique")
    if not isinstance(gated, GatedDecision):
        raise TypeError("gated must be a GatedDecision")

    pool_ids = {item.identity for item in all_candidates}
    if any(item.identity not in pool_ids for item in gated.source_decision.candidates):
        raise ValueError("source decision candidates must be drawn from all_candidates")
    if gated.source_decision.status is ResolverStatus.NO_MATCH and all_candidates:
        raise ValueError("no-match decision requires an empty candidate pool")

    ordered = _ordered_candidates(all_candidates)
    if gated.state is FinalDecisionState.RESOLVED:
        primary = gated.source_decision.candidates[0]
        alternatives = tuple(item for item in ordered if item.identity != primary.identity)
    else:
        primary = None
        alternatives = ordered

    return AlternativeReport(
        primary=primary,
        alternatives=tuple(
            CandidateAlternative(item, assess_candidate_strength(item))
            for item in alternatives
        ),
    )
