"""Read-only decision explainability and audit contract for Stage 4-H.

The authoritative resolver and confidence/ambiguity gates run before this layer.
Audit construction only reports their outputs and evidence chain; it cannot
change a harmonic decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .abstention import (
    AbstentionReason,
    FinalDecisionState,
    apply_abstention_policy,
)
from .alternatives import CandidateAlternative, build_alternative_report
from .ambiguity import AmbiguityReason, assess_ambiguity
from .confidence import ConfidenceAssessment
from .resolver import (
    EvidenceSource,
    ResolverCandidate,
    ResolverDecision,
    ResolverStatus,
    evidence_precedence_index,
)
from .sequence import SequenceResolution


DECISION_AUDIT_SCHEMA_NAME = "st_guitar_harmonic_engine.decision_audit"
DECISION_AUDIT_SCHEMA_VERSION = "1.0"


def _canonical_evidence(values: set[EvidenceSource]) -> tuple[EvidenceSource, ...]:
    return tuple(sorted(values, key=evidence_precedence_index))


def _evidence_profile(
    candidates: tuple[ResolverCandidate, ...],
) -> tuple[tuple[EvidenceSource, ...], tuple[EvidenceSource, ...]]:
    if not candidates:
        return (), ()
    sets = [set(item.evidence) for item in candidates]
    shared = set.intersection(*sets)
    union = set.union(*sets)
    return _canonical_evidence(shared), _canonical_evidence(union - shared)


@dataclass(frozen=True, slots=True)
class DecisionAudit:
    final_state: FinalDecisionState
    source_status: ResolverStatus
    primary: ResolverCandidate | None
    alternatives: tuple[CandidateAlternative, ...]
    supporting_evidence: tuple[EvidenceSource, ...]
    conflicting_evidence: tuple[EvidenceSource, ...]
    confidence: ConfidenceAssessment | None
    ambiguity_reason: AmbiguityReason | None
    abstention_reason: AbstentionReason | None

    def __post_init__(self) -> None:
        if not isinstance(self.final_state, FinalDecisionState):
            raise TypeError("final_state must be a FinalDecisionState")
        if not isinstance(self.source_status, ResolverStatus):
            raise TypeError("source_status must be a ResolverStatus")
        if self.primary is not None and not isinstance(self.primary, ResolverCandidate):
            raise TypeError("primary must be a ResolverCandidate or None")
        if not isinstance(self.alternatives, tuple) or any(
            not isinstance(item, CandidateAlternative) for item in self.alternatives
        ):
            raise TypeError("alternatives must contain CandidateAlternative values")
        for name, evidence in (
            ("supporting_evidence", self.supporting_evidence),
            ("conflicting_evidence", self.conflicting_evidence),
        ):
            if not isinstance(evidence, tuple) or any(
                not isinstance(item, EvidenceSource) for item in evidence
            ):
                raise TypeError(f"{name} must contain EvidenceSource values")
            if len(set(evidence)) != len(evidence):
                raise ValueError(f"{name} must be unique")
            if tuple(sorted(evidence, key=evidence_precedence_index)) != evidence:
                raise ValueError(f"{name} must follow canonical precedence")
        if self.confidence is not None and not isinstance(self.confidence, ConfidenceAssessment):
            raise TypeError("confidence must be a ConfidenceAssessment or None")
        if self.ambiguity_reason is not None and not isinstance(self.ambiguity_reason, AmbiguityReason):
            raise TypeError("ambiguity_reason must be an AmbiguityReason or None")
        if self.abstention_reason is not None and not isinstance(self.abstention_reason, AbstentionReason):
            raise TypeError("abstention_reason must be an AbstentionReason or None")

        if self.final_state is FinalDecisionState.RESOLVED:
            if self.source_status is not ResolverStatus.RESOLVED or self.primary is None:
                raise ValueError("resolved audit requires resolved source and primary")
            if self.confidence is None or self.ambiguity_reason is not None or self.abstention_reason is not None:
                raise ValueError("resolved audit has inconsistent gate metadata")
        elif self.final_state is FinalDecisionState.ABSTAIN:
            if self.primary is not None or self.abstention_reason is None:
                raise ValueError("abstain audit requires no primary and an abstention reason")
            if self.source_status is ResolverStatus.RESOLVED:
                if self.confidence is None or self.ambiguity_reason is not None:
                    raise ValueError("resolved-source abstain has inconsistent gate metadata")
                if self.abstention_reason not in {
                    AbstentionReason.WEAK_EVIDENCE,
                    AbstentionReason.INSUFFICIENT_EVIDENCE,
                }:
                    raise ValueError("resolved-source abstain has unsupported reason")
            elif self.source_status is ResolverStatus.AMBIGUOUS:
                if self.confidence is not None or self.ambiguity_reason is None:
                    raise ValueError("ambiguous-source abstain must preserve ambiguity without confidence")
                if self.abstention_reason is not AbstentionReason.AMBIGUOUS_WEAK_INCOMPLETE:
                    raise ValueError("ambiguous-source abstain requires weak-incomplete reason")
            else:
                raise ValueError("abstain audit requires resolved or ambiguous source")
        elif self.final_state is FinalDecisionState.AMBIGUOUS:
            if self.source_status is not ResolverStatus.AMBIGUOUS or self.primary is not None:
                raise ValueError("ambiguous audit requires ambiguous source and no primary")
            if self.confidence is not None or self.ambiguity_reason is None or self.abstention_reason is not None:
                raise ValueError("ambiguous audit has inconsistent gate metadata")
        elif self.final_state is FinalDecisionState.NO_MATCH:
            if self.source_status is not ResolverStatus.NO_MATCH or self.primary is not None:
                raise ValueError("no-match audit requires no-match source and no primary")
            if self.confidence is not None or self.ambiguity_reason is not None or self.abstention_reason is not None:
                raise ValueError("no-match audit cannot claim gate metadata")


def build_decision_audit(
    all_candidates: tuple[ResolverCandidate, ...],
    decision: ResolverDecision,
) -> DecisionAudit:
    """Build an audit record without mutating or re-resolving the decision."""

    if not isinstance(decision, ResolverDecision):
        raise TypeError("decision must be a ResolverDecision")
    gated = apply_abstention_policy(decision)
    ambiguity = assess_ambiguity(all_candidates, decision)
    alternatives = build_alternative_report(all_candidates, gated)

    supporting: tuple[EvidenceSource, ...]
    conflicting: tuple[EvidenceSource, ...]
    if gated.state is FinalDecisionState.RESOLVED:
        primary = decision.candidates[0]
        supporting = primary.evidence
        competing = tuple(item.candidate for item in alternatives.alternatives)
        competing_union = set().union(*(set(item.evidence) for item in competing)) if competing else set()
        conflicting = _canonical_evidence(competing_union - set(primary.evidence))
    elif gated.state is FinalDecisionState.ABSTAIN:
        if decision.status is ResolverStatus.RESOLVED:
            withheld = decision.candidates[0]
            supporting = withheld.evidence
            competing = tuple(
                item for item in all_candidates if item.identity != withheld.identity
            )
            competing_union = set().union(*(set(item.evidence) for item in competing)) if competing else set()
            conflicting = _canonical_evidence(competing_union - set(withheld.evidence))
        else:
            supporting, conflicting = _evidence_profile(decision.candidates)
    elif gated.state is FinalDecisionState.AMBIGUOUS:
        supporting, conflicting = _evidence_profile(decision.candidates)
    else:
        supporting, conflicting = (), ()

    return DecisionAudit(
        final_state=gated.state,
        source_status=decision.status,
        primary=alternatives.primary,
        alternatives=alternatives.alternatives,
        supporting_evidence=supporting,
        conflicting_evidence=conflicting,
        confidence=gated.confidence,
        ambiguity_reason=ambiguity.reason,
        abstention_reason=gated.abstention_reason,
    )


def audit_sequence_resolution(resolution: SequenceResolution) -> tuple[DecisionAudit, ...]:
    """Audit every Stage 3 sequence decision with its original candidate pool."""

    if not isinstance(resolution, SequenceResolution):
        raise TypeError("resolution must be a SequenceResolution")
    return tuple(
        build_decision_audit(candidates, decision)
        for candidates, decision in zip(resolution.candidates, resolution.decisions)
    )


def _serialize_candidate(candidate: ResolverCandidate) -> dict[str, Any]:
    return {
        "identity": {
            "root_pc": candidate.identity.root_pc,
            "family": candidate.identity.family.value,
            "variant": candidate.identity.variant,
        },
        "evidence": [item.value for item in candidate.evidence],
    }


def serialize_decision_audit(audit: DecisionAudit) -> dict[str, Any]:
    """Return a stable JSON-compatible v1.0 audit payload."""

    if not isinstance(audit, DecisionAudit):
        raise TypeError("audit must be a DecisionAudit")
    return {
        "schema_name": DECISION_AUDIT_SCHEMA_NAME,
        "schema_version": DECISION_AUDIT_SCHEMA_VERSION,
        "final_state": audit.final_state.value,
        "source_status": audit.source_status.value,
        "primary": _serialize_candidate(audit.primary) if audit.primary is not None else None,
        "alternatives": [
            {
                "candidate": _serialize_candidate(item.candidate),
                "confidence_state": item.confidence.state.value,
                "confidence_basis": [source.value for source in item.confidence.basis],
            }
            for item in audit.alternatives
        ],
        "supporting_evidence": [item.value for item in audit.supporting_evidence],
        "conflicting_evidence": [item.value for item in audit.conflicting_evidence],
        "confidence_state": audit.confidence.state.value if audit.confidence is not None else None,
        "confidence_basis": [item.value for item in audit.confidence.basis] if audit.confidence is not None else [],
        "ambiguity_reason": audit.ambiguity_reason.value if audit.ambiguity_reason is not None else None,
        "abstention_reason": audit.abstention_reason.value if audit.abstention_reason is not None else None,
    }


def is_decision_audit_payload_compatible(payload: object) -> bool:
    """Check the additive v1.0 audit envelope without touching older schemas."""

    if not isinstance(payload, dict):
        return False
    required = {
        "schema_name",
        "schema_version",
        "final_state",
        "source_status",
        "primary",
        "alternatives",
        "supporting_evidence",
        "conflicting_evidence",
        "confidence_state",
        "confidence_basis",
        "ambiguity_reason",
        "abstention_reason",
    }
    return (
        set(payload) == required
        and payload.get("schema_name") == DECISION_AUDIT_SCHEMA_NAME
        and payload.get("schema_version") == DECISION_AUDIT_SCHEMA_VERSION
    )
