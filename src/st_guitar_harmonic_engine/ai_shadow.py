"""Stage 5 shadow-only AI adapter and disagreement audit.

This module is intentionally non-authoritative.  It executes an injected
specialist callable, validates its untrusted response through ``ai_evidence``,
and records comparison metadata.  The authoritative resolver decision is always
the caller-supplied deterministic decision and is never replaced or re-ranked.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .ai_evidence import (
    AIEvidenceEnvelope,
    AIRejectionReason,
    EvidenceScope,
    ModelCompatibilityPolicy,
    SupportState,
    serialize_ai_evidence,
    validate_ai_evidence_payload,
)
from .resolver import HarmonicIdentity, ResolverDecision


AI_SHADOW_AUDIT_SCHEMA_NAME = "st_guitar_harmonic_engine.ai_shadow_audit"
AI_SHADOW_AUDIT_SCHEMA_VERSION = "1.0"
AI_AUTHORITY_SEMANTICS = "shadow_only_bounded_evidence_never_authoritative"
AI_AUTHORITATIVE_SOURCE = "deterministic_resolver"


class AIRuntimeFailure(str, Enum):
    TIMEOUT = "timeout"
    EXCEPTION = "exception"
    EMPTY_RESPONSE = "empty_response"
    MODEL_UNAVAILABLE = "model_unavailable"


class ModelUnavailableError(RuntimeError):
    """Adapter signal for a specialist that cannot serve the request."""


@dataclass(frozen=True, slots=True)
class AIShadowAudit:
    authoritative_decision: ResolverDecision
    ai_evidence: AIEvidenceEnvelope | None
    runtime_failure: AIRuntimeFailure | None
    rejected_ai_evidence_reason: AIRejectionReason | None
    agreement: bool
    disagreement: bool
    candidate_overlap: tuple[HarmonicIdentity, ...]
    authoritative_source: str = AI_AUTHORITATIVE_SOURCE

    def __post_init__(self) -> None:
        if not isinstance(self.authoritative_decision, ResolverDecision):
            raise TypeError("authoritative_decision must be a ResolverDecision")
        if self.ai_evidence is not None and not isinstance(self.ai_evidence, AIEvidenceEnvelope):
            raise TypeError("ai_evidence must be an AIEvidenceEnvelope or None")
        if self.runtime_failure is not None and not isinstance(self.runtime_failure, AIRuntimeFailure):
            raise TypeError("runtime_failure must be an AIRuntimeFailure or None")
        if self.rejected_ai_evidence_reason is not None and not isinstance(
            self.rejected_ai_evidence_reason, AIRejectionReason
        ):
            raise TypeError("rejected_ai_evidence_reason must be an AIRejectionReason or None")
        if self.runtime_failure is not None and self.ai_evidence is not None:
            raise ValueError("runtime failure cannot carry accepted AI evidence")
        if self.rejected_ai_evidence_reason is not None and self.ai_evidence is not None:
            raise ValueError("rejected AI evidence cannot also be accepted")
        if self.runtime_failure is not None and self.rejected_ai_evidence_reason is not None:
            raise ValueError("runtime failure and validation rejection are mutually exclusive")
        if not isinstance(self.agreement, bool) or not isinstance(self.disagreement, bool):
            raise TypeError("agreement and disagreement must be bool")
        if self.agreement and self.disagreement:
            raise ValueError("agreement and disagreement cannot both be true")
        if not isinstance(self.candidate_overlap, tuple) or any(
            not isinstance(item, HarmonicIdentity) for item in self.candidate_overlap
        ):
            raise TypeError("candidate_overlap must contain HarmonicIdentity values")
        expected_overlap = tuple(sorted(set(self.candidate_overlap)))
        if self.candidate_overlap != expected_overlap:
            raise ValueError("candidate_overlap must be unique and canonically sorted")
        if self.authoritative_source != AI_AUTHORITATIVE_SOURCE:
            raise ValueError("AI shadow audit cannot change authoritative source")


def _candidate_claims(evidence: AIEvidenceEnvelope) -> tuple[HarmonicIdentity, ...]:
    claims = {
        item.candidate
        for item in evidence.evidence
        if item.scope is EvidenceScope.CANDIDATE
        and item.support is SupportState.SUPPORTED
        and item.candidate is not None
    }
    return tuple(sorted(claims))


def _audit_without_evidence(
    decision: ResolverDecision,
    *,
    runtime_failure: AIRuntimeFailure | None = None,
    rejection: AIRejectionReason | None = None,
) -> AIShadowAudit:
    return AIShadowAudit(
        authoritative_decision=decision,
        ai_evidence=None,
        runtime_failure=runtime_failure,
        rejected_ai_evidence_reason=rejection,
        agreement=False,
        disagreement=False,
        candidate_overlap=(),
    )


def run_shadow_ai_adapter(
    adapter: Callable[[object], object],
    request: object,
    *,
    deterministic_decision: ResolverDecision,
    known_candidates: tuple[HarmonicIdentity, ...],
    expected_input_identity: str,
    compatibility: ModelCompatibilityPolicy,
) -> AIShadowAudit:
    """Execute one specialist in shadow mode and compare without changing authority.

    The callable is injected by an outer adapter layer.  Network access, process
    management, retries, and timeouts are deliberately outside the core.  A
    timeout is represented by ``TimeoutError`` and model unavailability by
    ``ModelUnavailableError``.  All failures collapse to "no AI evidence".
    """

    if not callable(adapter):
        raise TypeError("adapter must be callable")
    if not isinstance(deterministic_decision, ResolverDecision):
        raise TypeError("deterministic_decision must be a ResolverDecision")

    try:
        raw_response = adapter(request)
    except TimeoutError:
        return _audit_without_evidence(
            deterministic_decision,
            runtime_failure=AIRuntimeFailure.TIMEOUT,
        )
    except ModelUnavailableError:
        return _audit_without_evidence(
            deterministic_decision,
            runtime_failure=AIRuntimeFailure.MODEL_UNAVAILABLE,
        )
    except Exception:
        return _audit_without_evidence(
            deterministic_decision,
            runtime_failure=AIRuntimeFailure.EXCEPTION,
        )

    if raw_response is None or raw_response == "" or raw_response == {} or raw_response == []:
        return _audit_without_evidence(
            deterministic_decision,
            runtime_failure=AIRuntimeFailure.EMPTY_RESPONSE,
        )

    validated = validate_ai_evidence_payload(
        raw_response,
        known_candidates=known_candidates,
        expected_input_identity=expected_input_identity,
        compatibility=compatibility,
    )
    if not validated.accepted:
        return _audit_without_evidence(
            deterministic_decision,
            rejection=validated.rejection_reason,
        )

    evidence = validated.evidence
    assert evidence is not None
    ai_candidates = set(_candidate_claims(evidence))
    deterministic_candidates = {
        item.identity for item in deterministic_decision.candidates
    }
    overlap = tuple(sorted(ai_candidates & deterministic_candidates))
    has_claim = bool(ai_candidates)
    agreement = has_claim and ai_candidates == deterministic_candidates
    disagreement = has_claim and ai_candidates != deterministic_candidates
    return AIShadowAudit(
        authoritative_decision=deterministic_decision,
        ai_evidence=evidence,
        runtime_failure=None,
        rejected_ai_evidence_reason=None,
        agreement=agreement,
        disagreement=disagreement,
        candidate_overlap=overlap,
    )


def _serialize_identity(identity: HarmonicIdentity) -> dict[str, Any]:
    return {
        "root_pc": identity.root_pc,
        "family": identity.family.value,
        "variant": identity.variant,
    }


def serialize_ai_shadow_audit(audit: AIShadowAudit) -> dict[str, Any]:
    """Return the canonical JSON-compatible Stage 5 shadow audit payload."""

    if not isinstance(audit, AIShadowAudit):
        raise TypeError("audit must be an AIShadowAudit")
    decision = audit.authoritative_decision
    return {
        "schema_name": AI_SHADOW_AUDIT_SCHEMA_NAME,
        "schema_version": AI_SHADOW_AUDIT_SCHEMA_VERSION,
        "authority_semantics": AI_AUTHORITY_SEMANTICS,
        "authoritative_source": audit.authoritative_source,
        "deterministic_result": {
            "status": decision.status.value,
            "candidates": [
                {
                    "identity": _serialize_identity(item.identity),
                    "evidence": [source.value for source in item.evidence],
                }
                for item in decision.candidates
            ],
        },
        "ai_evidence": serialize_ai_evidence(audit.ai_evidence)
        if audit.ai_evidence is not None
        else None,
        "agreement": audit.agreement,
        "disagreement": audit.disagreement,
        "candidate_overlap": [_serialize_identity(item) for item in audit.candidate_overlap],
        "runtime_failure": audit.runtime_failure.value if audit.runtime_failure is not None else None,
        "rejected_ai_evidence_reason": (
            audit.rejected_ai_evidence_reason.value
            if audit.rejected_ai_evidence_reason is not None
            else None
        ),
    }


def is_ai_shadow_audit_payload_compatible(payload: object) -> bool:
    """Check the frozen Stage 5 shadow-audit envelope."""

    if not isinstance(payload, dict):
        return False
    return (
        set(payload)
        == {
            "schema_name",
            "schema_version",
            "authority_semantics",
            "authoritative_source",
            "deterministic_result",
            "ai_evidence",
            "agreement",
            "disagreement",
            "candidate_overlap",
            "runtime_failure",
            "rejected_ai_evidence_reason",
        }
        and payload.get("schema_name") == AI_SHADOW_AUDIT_SCHEMA_NAME
        and payload.get("schema_version") == AI_SHADOW_AUDIT_SCHEMA_VERSION
        and payload.get("authority_semantics") == AI_AUTHORITY_SEMANTICS
        and payload.get("authoritative_source") == AI_AUTHORITATIVE_SOURCE
    )
