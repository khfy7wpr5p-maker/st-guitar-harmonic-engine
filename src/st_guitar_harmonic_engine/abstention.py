"""Deterministic abstention policy for Stage 4-E.

Stage 3 remains authoritative about harmonic identity. This gate may withhold a
resolved identity when its evidence strength is too weak, but it never invents a
replacement candidate.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .confidence import ConfidenceAssessment, ConfidenceState
from .resolver import ResolverDecision, ResolverStatus
from .strength import assess_candidate_strength


class FinalDecisionState(str, Enum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    ABSTAIN = "abstain"
    NO_MATCH = "no_match"


class AbstentionReason(str, Enum):
    WEAK_EVIDENCE = "weak_evidence"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True, slots=True)
class GatedDecision:
    state: FinalDecisionState
    source_decision: ResolverDecision
    confidence: ConfidenceAssessment | None
    abstention_reason: AbstentionReason | None

    def __post_init__(self) -> None:
        if not isinstance(self.state, FinalDecisionState):
            raise TypeError("state must be a FinalDecisionState")
        if not isinstance(self.source_decision, ResolverDecision):
            raise TypeError("source_decision must be a ResolverDecision")
        if self.confidence is not None and not isinstance(self.confidence, ConfidenceAssessment):
            raise TypeError("confidence must be a ConfidenceAssessment or None")
        if self.abstention_reason is not None and not isinstance(self.abstention_reason, AbstentionReason):
            raise TypeError("abstention_reason must be an AbstentionReason or None")

        if self.state is FinalDecisionState.RESOLVED:
            if self.source_decision.status is not ResolverStatus.RESOLVED or self.confidence is None:
                raise ValueError("resolved gate result requires resolved source and confidence")
            if self.confidence.state not in {ConfidenceState.STRONG, ConfidenceState.BOUNDED}:
                raise ValueError("resolved gate result requires strong or bounded confidence")
            if self.abstention_reason is not None:
                raise ValueError("resolved gate result cannot have abstention reason")
        elif self.state is FinalDecisionState.ABSTAIN:
            if self.source_decision.status is not ResolverStatus.RESOLVED or self.confidence is None:
                raise ValueError("abstain requires a resolved source candidate and confidence")
            if self.confidence.state not in {ConfidenceState.WEAK, ConfidenceState.INSUFFICIENT}:
                raise ValueError("abstain requires weak or insufficient confidence")
            if self.abstention_reason is None:
                raise ValueError("abstain requires a reason")
        elif self.state is FinalDecisionState.AMBIGUOUS:
            if self.source_decision.status is not ResolverStatus.AMBIGUOUS:
                raise ValueError("ambiguous gate result requires ambiguous source")
            if self.confidence is not None or self.abstention_reason is not None:
                raise ValueError("ambiguous gate result does not claim single-candidate confidence")
        elif self.state is FinalDecisionState.NO_MATCH:
            if self.source_decision.status is not ResolverStatus.NO_MATCH:
                raise ValueError("no-match gate result requires no-match source")
            if self.confidence is not None or self.abstention_reason is not None:
                raise ValueError("no-match gate result cannot claim confidence or abstention reason")


def apply_abstention_policy(decision: ResolverDecision) -> GatedDecision:
    """Apply the deterministic confidence gate to one authoritative decision."""

    if not isinstance(decision, ResolverDecision):
        raise TypeError("decision must be a ResolverDecision")
    if decision.status is ResolverStatus.NO_MATCH:
        return GatedDecision(FinalDecisionState.NO_MATCH, decision, None, None)
    if decision.status is ResolverStatus.AMBIGUOUS:
        return GatedDecision(FinalDecisionState.AMBIGUOUS, decision, None, None)

    confidence = assess_candidate_strength(decision.candidates[0])
    if confidence.state in {ConfidenceState.STRONG, ConfidenceState.BOUNDED}:
        return GatedDecision(FinalDecisionState.RESOLVED, decision, confidence, None)
    reason = (
        AbstentionReason.WEAK_EVIDENCE
        if confidence.state is ConfidenceState.WEAK
        else AbstentionReason.INSUFFICIENT_EVIDENCE
    )
    return GatedDecision(FinalDecisionState.ABSTAIN, decision, confidence, reason)
