"""Deterministic ambiguity gate for Stage 4-D.

The gate classifies ambiguity already present in the authoritative resolver. It
never resolves, ranks away, or hides an ambiguous authoritative decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .ranking import rank_candidates
from .resolver import EvidenceSource, ResolverCandidate, ResolverDecision, ResolverStatus


class AmbiguityReason(str, Enum):
    EXACT_CONFLICT = "exact_conflict"
    TOP_RANK_TIE = "top_rank_tie"
    MULTIPLE_AUTHORITATIVE_CANDIDATES = "multiple_authoritative_candidates"


@dataclass(frozen=True, slots=True)
class AmbiguityAssessment:
    ambiguous: bool
    reason: AmbiguityReason | None
    candidates: tuple[ResolverCandidate, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.ambiguous, bool):
            raise TypeError("ambiguous must be bool")
        if self.reason is not None and not isinstance(self.reason, AmbiguityReason):
            raise TypeError("reason must be an AmbiguityReason or None")
        if not isinstance(self.candidates, tuple) or any(
            not isinstance(item, ResolverCandidate) for item in self.candidates
        ):
            raise TypeError("candidates must contain ResolverCandidate values")
        if tuple(sorted(self.candidates, key=lambda item: item.identity)) != self.candidates:
            raise ValueError("ambiguity candidates must use canonical identity order")
        if len({item.identity for item in self.candidates}) != len(self.candidates):
            raise ValueError("ambiguity candidate identities must be unique")
        if self.ambiguous:
            if self.reason is None or len(self.candidates) < 2:
                raise ValueError("ambiguous assessment requires a reason and at least two candidates")
        elif self.reason is not None or self.candidates:
            raise ValueError("non-ambiguous assessment cannot claim ambiguity details")


def assess_ambiguity(
    all_candidates: tuple[ResolverCandidate, ...],
    decision: ResolverDecision,
) -> AmbiguityAssessment:
    """Classify authoritative ambiguity without altering the decision."""

    if not isinstance(all_candidates, tuple) or any(
        not isinstance(item, ResolverCandidate) for item in all_candidates
    ):
        raise TypeError("all_candidates must contain ResolverCandidate values")
    if len({item.identity for item in all_candidates}) != len(all_candidates):
        raise ValueError("all candidate identities must be unique")
    if not isinstance(decision, ResolverDecision):
        raise TypeError("decision must be a ResolverDecision")

    identities = {item.identity for item in all_candidates}
    if any(item.identity not in identities for item in decision.candidates):
        raise ValueError("decision candidates must be drawn from all_candidates")

    if decision.status is not ResolverStatus.AMBIGUOUS:
        return AmbiguityAssessment(False, None, ())

    authoritative = tuple(sorted(decision.candidates, key=lambda item: item.identity))
    if all(EvidenceSource.EXACT in item.evidence for item in authoritative):
        reason = AmbiguityReason.EXACT_CONFLICT
    else:
        groups = rank_candidates(authoritative)
        reason = (
            AmbiguityReason.TOP_RANK_TIE
            if groups and len(groups[0].candidates) > 1
            else AmbiguityReason.MULTIPLE_AUTHORITATIVE_CANDIDATES
        )
    return AmbiguityAssessment(True, reason, authoritative)
