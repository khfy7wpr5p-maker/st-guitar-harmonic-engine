"""Stage 5 bounded AI specialist evidence contract and fail-closed validator.

AI evidence is advisory only.  This module deliberately has no import from the
resolver policy or mutation path beyond stable candidate identity types.  A
validated AI payload can be audited or translated by an explicit future adapter,
but it is never an authoritative :class:`ResolverDecision`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
import re
from typing import Any

from .resolver import CandidateFamily, HarmonicIdentity


AI_EVIDENCE_SCHEMA_NAME = "st_guitar_harmonic_engine.ai_evidence"
AI_EVIDENCE_SCHEMA_VERSION = "1.0"
AI_TASK_CONTRACT_VERSION = "1.0"
AI_SUPPORTED_DOMAIN = "guitar_harmony"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class SpecialistType(str, Enum):
    LOCAL_TONAL_CONTEXT = "local_tonal_context"
    HARMONIC_BOUNDARY = "harmonic_boundary"
    NCT = "nct"
    INCOMPLETE_CHORD = "incomplete_chord"
    EXTENSION = "extension"
    SUSPENSION = "suspension"
    CADENCE_FUNCTION = "cadence_function"
    PHRASE_CONTEXT = "phrase_context"
    ALTERED_HARMONY = "altered_harmony"
    CANDIDATE_RERANKER = "candidate_reranker"
    ABSTENTION_RISK = "abstention_risk"


class SpecialistEvidenceStrength(str, Enum):
    STRONG = "strong"
    BOUNDED = "bounded"
    WEAK = "weak"
    UNKNOWN = "unknown"


class SupportState(str, Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class EvidenceScope(str, Enum):
    INPUT = "input"
    CANDIDATE = "candidate"


class AIRejectionReason(str, Enum):
    MALFORMED_SCHEMA = "malformed_schema"
    UNSUPPORTED_SCHEMA_VERSION = "unsupported_schema_version"
    UNKNOWN_SPECIALIST = "unknown_specialist"
    UNKNOWN_CANDIDATE = "unknown_candidate_identity"
    INVALID_ENUM = "invalid_enum"
    MISSING_PROVENANCE = "missing_provenance"
    MISSING_MODEL_IDENTITY = "missing_model_identity"
    INVALID_HASH = "invalid_hash"
    NON_FINITE_VALUE = "nan_or_infinity"
    IMPOSSIBLE_VALUE = "impossible_value"
    EMPTY_REQUIRED_FIELD = "empty_required_field"
    MALFORMED_EVIDENCE = "malformed_evidence"
    UNSUPPORTED_DOMAIN = "unsupported_domain"
    INCOMPATIBLE_MODEL_VERSION = "incompatible_model_version"
    INPUT_IDENTITY_MISMATCH = "input_identity_mismatch"
    DUPLICATE_RESPONSE = "duplicate_response"
    CONFLICTING_EVIDENCE = "conflicting_ai_evidence"


def _require_text(value: object, name: str, *, max_length: int = 256) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str")
    if not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty trimmed string")
    if len(value) > max_length or any(ord(char) < 32 for char in value):
        raise ValueError(f"{name} contains unsupported characters or is too long")
    return value


def _contains_non_finite(value: object) -> bool:
    if isinstance(value, float):
        return not math.isfinite(value)
    if isinstance(value, dict):
        return any(_contains_non_finite(key) or _contains_non_finite(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_non_finite(item) for item in value)
    return False


@dataclass(frozen=True, slots=True)
class ModelProvenance:
    model_id: str
    model_version: str
    checkpoint_sha256: str
    training_dataset_manifest_id: str
    training_dataset_version: str
    task_contract_version: str
    inference_schema_version: str

    def __post_init__(self) -> None:
        for name in (
            "model_id",
            "model_version",
            "training_dataset_manifest_id",
            "training_dataset_version",
            "task_contract_version",
            "inference_schema_version",
        ):
            _require_text(getattr(self, name), name)
        if not isinstance(self.checkpoint_sha256, str) or not _SHA256_RE.fullmatch(
            self.checkpoint_sha256
        ):
            raise ValueError("checkpoint_sha256 must be 64 lowercase hexadecimal characters")


@dataclass(frozen=True, slots=True)
class SpecialistEvidence:
    scope: EvidenceScope
    label: str
    strength: SpecialistEvidenceStrength
    support: SupportState
    candidate: HarmonicIdentity | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.scope, EvidenceScope):
            raise TypeError("scope must be an EvidenceScope")
        _require_text(self.label, "label", max_length=128)
        if not isinstance(self.strength, SpecialistEvidenceStrength):
            raise TypeError("strength must be a SpecialistEvidenceStrength")
        if not isinstance(self.support, SupportState):
            raise TypeError("support must be a SupportState")
        if self.candidate is not None and not isinstance(self.candidate, HarmonicIdentity):
            raise TypeError("candidate must be a HarmonicIdentity or None")
        if self.scope is EvidenceScope.CANDIDATE and self.candidate is None:
            raise ValueError("candidate-scoped evidence requires a candidate identity")
        if self.scope is EvidenceScope.INPUT and self.candidate is not None:
            raise ValueError("input-scoped evidence cannot carry a candidate identity")


@dataclass(frozen=True, slots=True)
class AIEvidenceEnvelope:
    specialist_type: SpecialistType
    provenance: ModelProvenance
    source: str
    input_identity: str
    supported_domain: str
    evidence: tuple[SpecialistEvidence, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.specialist_type, SpecialistType):
            raise TypeError("specialist_type must be a SpecialistType")
        if not isinstance(self.provenance, ModelProvenance):
            raise TypeError("provenance must be a ModelProvenance")
        _require_text(self.source, "source")
        _require_text(self.input_identity, "input_identity")
        _require_text(self.supported_domain, "supported_domain")
        if self.supported_domain != AI_SUPPORTED_DOMAIN:
            raise ValueError("unsupported AI evidence domain")
        if not isinstance(self.evidence, tuple) or not self.evidence:
            raise ValueError("evidence must be a non-empty tuple")
        if any(not isinstance(item, SpecialistEvidence) for item in self.evidence):
            raise TypeError("evidence must contain SpecialistEvidence values")
        expected = tuple(sorted(self.evidence, key=_evidence_sort_key))
        if self.evidence != expected:
            raise ValueError("evidence must use canonical ordering")


@dataclass(frozen=True, slots=True)
class ModelCompatibilityPolicy:
    model_id: str
    allowed_versions: tuple[str, ...]
    task_contract_version: str = AI_TASK_CONTRACT_VERSION
    inference_schema_version: str = AI_EVIDENCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_text(self.model_id, "model_id")
        _require_text(self.task_contract_version, "task_contract_version")
        _require_text(self.inference_schema_version, "inference_schema_version")
        if not isinstance(self.allowed_versions, tuple) or not self.allowed_versions:
            raise ValueError("allowed_versions must be a non-empty tuple")
        for version in self.allowed_versions:
            _require_text(version, "allowed model version")
        canonical = tuple(sorted(set(self.allowed_versions)))
        if self.allowed_versions != canonical:
            raise ValueError("allowed_versions must be unique and sorted")

    def accepts(self, provenance: ModelProvenance) -> bool:
        return (
            provenance.model_id == self.model_id
            and provenance.model_version in self.allowed_versions
            and provenance.task_contract_version == self.task_contract_version
            and provenance.inference_schema_version == self.inference_schema_version
        )


@dataclass(frozen=True, slots=True)
class AIValidationResult:
    evidence: AIEvidenceEnvelope | None
    rejection_reason: AIRejectionReason | None
    detail: str | None = None

    def __post_init__(self) -> None:
        if (self.evidence is None) == (self.rejection_reason is None):
            raise ValueError("validation result must be either accepted or rejected")
        if self.evidence is not None and not isinstance(self.evidence, AIEvidenceEnvelope):
            raise TypeError("evidence must be an AIEvidenceEnvelope or None")
        if self.rejection_reason is not None and not isinstance(
            self.rejection_reason, AIRejectionReason
        ):
            raise TypeError("rejection_reason must be an AIRejectionReason or None")
        if self.detail is not None:
            _require_text(self.detail, "detail", max_length=512)

    @property
    def accepted(self) -> bool:
        return self.evidence is not None


def _evidence_sort_key(item: SpecialistEvidence) -> tuple[object, ...]:
    candidate = item.candidate
    candidate_key = (
        -1,
        "",
        "",
    ) if candidate is None else (candidate.root_pc, candidate.family.value, candidate.variant)
    return (
        item.scope.value,
        *candidate_key,
        item.label,
        item.strength.value,
        item.support.value,
    )


def _reject(reason: AIRejectionReason, detail: str) -> AIValidationResult:
    return AIValidationResult(None, reason, detail)


def _parse_candidate(value: object) -> HarmonicIdentity:
    if not isinstance(value, dict) or set(value) != {"root_pc", "family", "variant"}:
        raise TypeError("candidate must use root_pc/family/variant")
    family = CandidateFamily(value["family"])
    return HarmonicIdentity(value["root_pc"], family, value["variant"])


def validate_ai_evidence_payload(
    payload: object,
    *,
    known_candidates: tuple[HarmonicIdentity, ...],
    expected_input_identity: str,
    compatibility: ModelCompatibilityPolicy,
) -> AIValidationResult:
    """Validate one untrusted AI payload without exposing it to resolver policy.

    Validation is strict and fail-closed.  Rejection always means "no AI
    evidence"; callers may continue with the deterministic engine unchanged.
    """

    if not isinstance(known_candidates, tuple) or any(
        not isinstance(item, HarmonicIdentity) for item in known_candidates
    ):
        raise TypeError("known_candidates must contain HarmonicIdentity values")
    if len(set(known_candidates)) != len(known_candidates):
        raise ValueError("known_candidates must be unique")
    _require_text(expected_input_identity, "expected_input_identity")
    if not isinstance(compatibility, ModelCompatibilityPolicy):
        raise TypeError("compatibility must be a ModelCompatibilityPolicy")

    if _contains_non_finite(payload):
        return _reject(AIRejectionReason.NON_FINITE_VALUE, "payload contains NaN or Infinity")
    if not isinstance(payload, dict):
        return _reject(AIRejectionReason.MALFORMED_SCHEMA, "payload must be an object")

    required = {
        "schema_name",
        "schema_version",
        "specialist_type",
        "provenance",
        "source",
        "input_identity",
        "supported_domain",
        "evidence",
    }
    if set(payload) != required:
        return _reject(AIRejectionReason.MALFORMED_SCHEMA, "payload fields do not match schema")
    if payload.get("schema_name") != AI_EVIDENCE_SCHEMA_NAME:
        return _reject(AIRejectionReason.MALFORMED_SCHEMA, "unknown schema name")
    if payload.get("schema_version") != AI_EVIDENCE_SCHEMA_VERSION:
        return _reject(
            AIRejectionReason.UNSUPPORTED_SCHEMA_VERSION,
            "unsupported AI evidence schema version",
        )

    try:
        specialist = SpecialistType(payload["specialist_type"])
    except (TypeError, ValueError):
        return _reject(AIRejectionReason.UNKNOWN_SPECIALIST, "unknown specialist type")

    for field in ("source", "input_identity", "supported_domain"):
        try:
            _require_text(payload[field], field)
        except TypeError:
            return _reject(AIRejectionReason.MALFORMED_SCHEMA, f"{field} has invalid type")
        except ValueError:
            return _reject(AIRejectionReason.EMPTY_REQUIRED_FIELD, f"{field} is empty or invalid")
    if payload["input_identity"] != expected_input_identity:
        return _reject(AIRejectionReason.INPUT_IDENTITY_MISMATCH, "input identity does not match request")
    if payload["supported_domain"] != AI_SUPPORTED_DOMAIN:
        return _reject(AIRejectionReason.UNSUPPORTED_DOMAIN, "specialist domain is not supported")

    raw_provenance = payload.get("provenance")
    if raw_provenance is None:
        return _reject(AIRejectionReason.MISSING_PROVENANCE, "provenance is required")
    provenance_fields = {
        "model_id",
        "model_version",
        "checkpoint_sha256",
        "training_dataset_manifest_id",
        "training_dataset_version",
        "task_contract_version",
        "inference_schema_version",
    }
    if not isinstance(raw_provenance, dict) or set(raw_provenance) != provenance_fields:
        return _reject(AIRejectionReason.MISSING_PROVENANCE, "provenance fields are incomplete")
    if not raw_provenance.get("model_id") or not raw_provenance.get("model_version"):
        return _reject(AIRejectionReason.MISSING_MODEL_IDENTITY, "model identity is required")
    checkpoint = raw_provenance.get("checkpoint_sha256")
    if not isinstance(checkpoint, str) or not _SHA256_RE.fullmatch(checkpoint):
        return _reject(AIRejectionReason.INVALID_HASH, "checkpoint hash is not canonical sha256")
    try:
        provenance = ModelProvenance(**raw_provenance)
    except TypeError:
        return _reject(AIRejectionReason.MALFORMED_SCHEMA, "provenance contains invalid types")
    except ValueError:
        return _reject(AIRejectionReason.EMPTY_REQUIRED_FIELD, "provenance contains empty or invalid fields")
    if not compatibility.accepts(provenance):
        return _reject(AIRejectionReason.INCOMPATIBLE_MODEL_VERSION, "model contract/version is not allowed")

    raw_evidence = payload.get("evidence")
    if not isinstance(raw_evidence, list) or not raw_evidence:
        return _reject(AIRejectionReason.MALFORMED_EVIDENCE, "evidence must be a non-empty list")
    known = set(known_candidates)
    parsed: list[SpecialistEvidence] = []
    seen: dict[tuple[object, ...], tuple[SpecialistEvidenceStrength, SupportState]] = {}
    fact_fields = {"scope", "label", "strength", "support", "candidate"}
    for raw_fact in raw_evidence:
        if not isinstance(raw_fact, dict) or set(raw_fact) != fact_fields:
            return _reject(AIRejectionReason.MALFORMED_EVIDENCE, "evidence fact fields are invalid")
        try:
            scope = EvidenceScope(raw_fact["scope"])
            strength = SpecialistEvidenceStrength(raw_fact["strength"])
            support = SupportState(raw_fact["support"])
        except (TypeError, ValueError):
            return _reject(AIRejectionReason.INVALID_ENUM, "evidence contains an invalid enum")
        try:
            label = _require_text(raw_fact["label"], "label", max_length=128)
        except TypeError:
            return _reject(AIRejectionReason.MALFORMED_EVIDENCE, "evidence label has invalid type")
        except ValueError:
            return _reject(AIRejectionReason.EMPTY_REQUIRED_FIELD, "evidence label is empty or invalid")

        raw_candidate = raw_fact["candidate"]
        candidate: HarmonicIdentity | None
        if raw_candidate is None:
            candidate = None
        else:
            try:
                candidate = _parse_candidate(raw_candidate)
            except ValueError as exc:
                if "CandidateFamily" in type(exc).__name__:
                    return _reject(AIRejectionReason.INVALID_ENUM, "candidate family is invalid")
                return _reject(AIRejectionReason.IMPOSSIBLE_VALUE, "candidate contains impossible values")
            except (TypeError, KeyError):
                return _reject(AIRejectionReason.MALFORMED_EVIDENCE, "candidate identity is malformed")
            if candidate not in known:
                return _reject(AIRejectionReason.UNKNOWN_CANDIDATE, "candidate is outside validated candidate set")

        try:
            fact = SpecialistEvidence(scope, label, strength, support, candidate)
        except (TypeError, ValueError):
            return _reject(AIRejectionReason.MALFORMED_EVIDENCE, "evidence scope/candidate relationship is invalid")

        identity_key = None if candidate is None else (
            candidate.root_pc,
            candidate.family.value,
            candidate.variant,
        )
        fact_key = (scope.value, identity_key, label)
        state = (strength, support)
        previous = seen.get(fact_key)
        if previous is not None:
            reason = (
                AIRejectionReason.DUPLICATE_RESPONSE
                if previous == state
                else AIRejectionReason.CONFLICTING_EVIDENCE
            )
            return _reject(reason, "duplicate or conflicting evidence fact")
        seen[fact_key] = state
        parsed.append(fact)

    evidence = tuple(sorted(parsed, key=_evidence_sort_key))
    return AIValidationResult(
        AIEvidenceEnvelope(
            specialist,
            provenance,
            payload["source"],
            payload["input_identity"],
            payload["supported_domain"],
            evidence,
        ),
        None,
        None,
    )


def _serialize_candidate(candidate: HarmonicIdentity | None) -> dict[str, Any] | None:
    if candidate is None:
        return None
    return {
        "root_pc": candidate.root_pc,
        "family": candidate.family.value,
        "variant": candidate.variant,
    }


def serialize_ai_evidence(evidence: AIEvidenceEnvelope) -> dict[str, Any]:
    """Return the canonical, versioned JSON-compatible Stage 5 payload."""

    if not isinstance(evidence, AIEvidenceEnvelope):
        raise TypeError("evidence must be an AIEvidenceEnvelope")
    provenance = evidence.provenance
    return {
        "schema_name": AI_EVIDENCE_SCHEMA_NAME,
        "schema_version": AI_EVIDENCE_SCHEMA_VERSION,
        "specialist_type": evidence.specialist_type.value,
        "provenance": {
            "model_id": provenance.model_id,
            "model_version": provenance.model_version,
            "checkpoint_sha256": provenance.checkpoint_sha256,
            "training_dataset_manifest_id": provenance.training_dataset_manifest_id,
            "training_dataset_version": provenance.training_dataset_version,
            "task_contract_version": provenance.task_contract_version,
            "inference_schema_version": provenance.inference_schema_version,
        },
        "source": evidence.source,
        "input_identity": evidence.input_identity,
        "supported_domain": evidence.supported_domain,
        "evidence": [
            {
                "scope": item.scope.value,
                "label": item.label,
                "strength": item.strength.value,
                "support": item.support.value,
                "candidate": _serialize_candidate(item.candidate),
            }
            for item in evidence.evidence
        ],
    }


def is_ai_evidence_payload_compatible(payload: object) -> bool:
    """Check only the frozen Stage 5 schema envelope, not model authorization."""

    if not isinstance(payload, dict):
        return False
    return (
        set(payload)
        == {
            "schema_name",
            "schema_version",
            "specialist_type",
            "provenance",
            "source",
            "input_identity",
            "supported_domain",
            "evidence",
        }
        and payload.get("schema_name") == AI_EVIDENCE_SCHEMA_NAME
        and payload.get("schema_version") == AI_EVIDENCE_SCHEMA_VERSION
    )
