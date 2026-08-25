"""Fail-closed Stage 8-B causal feature contract v0.1.

This module defines a whitelist of metadata/features that a future shadow-ranking
experiment may consume. It performs no feature extraction, model training, model
selection, or authoritative harmonic decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .stage8_sequence_context_target import STAGE8_SEQUENCE_CONTEXT_TARGET_ID


STAGE8_FEATURE_CONTRACT_VERSION = "0.1"
_MAX_LOOKBACK = 4


class Stage8FeatureSource(str, Enum):
    CURRENT_FRAME = "current_frame"
    CURRENT_CANDIDATE = "current_candidate"
    EXPLICIT_CONTEXT = "explicit_context"
    PREVIOUS_FRAME = "previous_frame"
    PHRASE_METADATA = "phrase_metadata"


class Stage8FeatureContractStatus(str, Enum):
    BLOCKED_TARGET_MISMATCH = "blocked_target_mismatch"
    BLOCKED_SCHEMA_EMPTY = "blocked_schema_empty"
    BLOCKED_DUPLICATE_FEATURE = "blocked_duplicate_feature"
    BLOCKED_UNAPPROVED_FEATURE = "blocked_unapproved_feature"
    BLOCKED_NONCAUSAL_FEATURE = "blocked_noncausal_feature"
    FEATURE_SCHEMA_FROZEN = "feature_schema_frozen"


@dataclass(frozen=True, slots=True, order=True)
class Stage8FeatureSpec:
    feature_id: str
    source: Stage8FeatureSource
    lookback: int
    candidate_specific: bool

    def __post_init__(self) -> None:
        if not isinstance(self.feature_id, str) or not self.feature_id:
            raise TypeError("feature_id must be a non-empty string")
        if not isinstance(self.source, Stage8FeatureSource):
            raise TypeError("source must be Stage8FeatureSource")
        if isinstance(self.lookback, bool) or not isinstance(self.lookback, int):
            raise TypeError("lookback must be int")
        if self.lookback < 0 or self.lookback > _MAX_LOOKBACK:
            raise ValueError(f"lookback must be in 0..{_MAX_LOOKBACK}")
        if not isinstance(self.candidate_specific, bool):
            raise TypeError("candidate_specific must be bool")
        if self.source is Stage8FeatureSource.PREVIOUS_FRAME and self.lookback == 0:
            raise ValueError("previous-frame features require positive lookback")
        if self.source is not Stage8FeatureSource.PREVIOUS_FRAME and self.lookback != 0:
            raise ValueError("only previous-frame features may use lookback")


@dataclass(frozen=True, slots=True)
class Stage8FeatureSchema:
    target_id: str
    features: tuple[Stage8FeatureSpec, ...]
    frozen_before_training: bool

    def __post_init__(self) -> None:
        if not isinstance(self.target_id, str) or not self.target_id:
            raise TypeError("target_id must be a non-empty string")
        if not isinstance(self.features, tuple) or any(
            not isinstance(item, Stage8FeatureSpec) for item in self.features
        ):
            raise TypeError("features must contain Stage8FeatureSpec values")
        if not isinstance(self.frozen_before_training, bool):
            raise TypeError("frozen_before_training must be bool")


@dataclass(frozen=True, slots=True)
class Stage8FeatureContractAssessment:
    status: Stage8FeatureContractStatus
    reasons: tuple[str, ...]
    feature_count: int
    model_training_authorized: bool = False
    production_authority_granted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.status, Stage8FeatureContractStatus):
            raise TypeError("status must be Stage8FeatureContractStatus")
        if not isinstance(self.reasons, tuple) or any(
            not isinstance(item, str) or not item for item in self.reasons
        ):
            raise TypeError("reasons must contain non-empty strings")
        if tuple(sorted(set(self.reasons))) != self.reasons:
            raise ValueError("reasons must be unique canonical order")
        if isinstance(self.feature_count, bool) or not isinstance(self.feature_count, int) or self.feature_count < 0:
            raise ValueError("feature_count must be a non-negative int")
        if self.model_training_authorized or self.production_authority_granted:
            raise ValueError("feature contract cannot authorize training or production")
        frozen = self.status is Stage8FeatureContractStatus.FEATURE_SCHEMA_FROZEN
        if frozen and self.reasons:
            raise ValueError("frozen schema cannot contain blocking reasons")
        if not frozen and not self.reasons:
            raise ValueError("blocked schema requires reasons")


def _spec(
    feature_id: str,
    source: Stage8FeatureSource,
    *,
    lookback: int = 0,
    candidate_specific: bool = False,
) -> Stage8FeatureSpec:
    return Stage8FeatureSpec(feature_id, source, lookback, candidate_specific)


# Intentionally excludes ADJACENT_CONTEXT and VOICE_FUNCTION evidence because the
# current deterministic annotations can include next-frame information. Sequence
# context for this research target must be represented by explicit previous-frame
# features below instead.
_APPROVED_CURRENT = frozenset(
    {
        _spec("current_pitch_class_mask", Stage8FeatureSource.CURRENT_FRAME),
        _spec("current_bass_pc", Stage8FeatureSource.CURRENT_FRAME),
        _spec("current_note_count", Stage8FeatureSource.CURRENT_FRAME),
        _spec("candidate_root_pc", Stage8FeatureSource.CURRENT_CANDIDATE, candidate_specific=True),
        _spec("candidate_family", Stage8FeatureSource.CURRENT_CANDIDATE, candidate_specific=True),
        _spec("candidate_variant", Stage8FeatureSource.CURRENT_CANDIDATE, candidate_specific=True),
        _spec("candidate_has_exact", Stage8FeatureSource.CURRENT_CANDIDATE, candidate_specific=True),
        _spec("candidate_has_tonal_context", Stage8FeatureSource.CURRENT_CANDIDATE, candidate_specific=True),
        _spec("candidate_has_structural", Stage8FeatureSource.CURRENT_CANDIDATE, candidate_specific=True),
        _spec("candidate_has_bass_inversion", Stage8FeatureSource.CURRENT_CANDIDATE, candidate_specific=True),
        _spec("candidate_has_verified_nct", Stage8FeatureSource.CURRENT_CANDIDATE, candidate_specific=True),
        _spec("candidate_has_incomplete_chord", Stage8FeatureSource.CURRENT_CANDIDATE, candidate_specific=True),
        _spec("candidate_has_color_tone", Stage8FeatureSource.CURRENT_CANDIDATE, candidate_specific=True),
        _spec("explicit_tonic_pc", Stage8FeatureSource.EXPLICIT_CONTEXT),
        _spec("explicit_tonal_mode", Stage8FeatureSource.EXPLICIT_CONTEXT),
        _spec("phrase_position_index", Stage8FeatureSource.PHRASE_METADATA),
        _spec("phrase_length", Stage8FeatureSource.PHRASE_METADATA),
    }
)

_APPROVED_PREVIOUS_IDS = frozenset(
    {
        "previous_state",
        "previous_resolved_root_pc",
        "previous_resolved_family",
        "previous_resolved_variant",
        "previous_bass_pc",
    }
)

_FORBIDDEN_TOKENS = (
    "teacher_gold",
    "holdout",
    "expected_",
    "label",
    "target_answer",
    "future",
    "next_",
    "raw_text",
    "teacher_reason",
)


def canonical_stage8_feature_schema() -> Stage8FeatureSchema:
    """Return the approved causal schema shape.

    Previous-frame feature IDs are repeated at lookbacks 1..4. No future frame is
    represented. The schema is metadata only; it contains no observed values.
    """

    previous = tuple(
        _spec(feature_id, Stage8FeatureSource.PREVIOUS_FRAME, lookback=lookback)
        for lookback in range(1, _MAX_LOOKBACK + 1)
        for feature_id in sorted(_APPROVED_PREVIOUS_IDS)
    )
    current = tuple(sorted(_APPROVED_CURRENT))
    return Stage8FeatureSchema(
        target_id=STAGE8_SEQUENCE_CONTEXT_TARGET_ID,
        features=current + previous,
        frozen_before_training=True,
    )


def _is_approved(spec: Stage8FeatureSpec) -> bool:
    if spec in _APPROVED_CURRENT:
        return True
    return (
        spec.source is Stage8FeatureSource.PREVIOUS_FRAME
        and spec.feature_id in _APPROVED_PREVIOUS_IDS
        and 1 <= spec.lookback <= _MAX_LOOKBACK
        and not spec.candidate_specific
    )


def assess_stage8_feature_schema(
    schema: Stage8FeatureSchema,
) -> Stage8FeatureContractAssessment:
    """Validate the Stage 8-B feature whitelist without granting training."""

    if not isinstance(schema, Stage8FeatureSchema):
        raise TypeError("schema must be Stage8FeatureSchema")

    if schema.target_id != STAGE8_SEQUENCE_CONTEXT_TARGET_ID:
        return Stage8FeatureContractAssessment(
            Stage8FeatureContractStatus.BLOCKED_TARGET_MISMATCH,
            ("feature_schema_target_mismatch",),
            len(schema.features),
        )
    if not schema.features:
        return Stage8FeatureContractAssessment(
            Stage8FeatureContractStatus.BLOCKED_SCHEMA_EMPTY,
            ("feature_schema_is_empty",),
            0,
        )

    identities = [(item.feature_id, item.source.value, item.lookback, item.candidate_specific) for item in schema.features]
    if len(set(identities)) != len(identities):
        return Stage8FeatureContractAssessment(
            Stage8FeatureContractStatus.BLOCKED_DUPLICATE_FEATURE,
            ("duplicate_feature_spec",),
            len(schema.features),
        )

    noncausal = tuple(
        sorted(
            item.feature_id
            for item in schema.features
            if item.lookback < 0 or item.lookback > _MAX_LOOKBACK
        )
    )
    if noncausal:
        return Stage8FeatureContractAssessment(
            Stage8FeatureContractStatus.BLOCKED_NONCAUSAL_FEATURE,
            tuple(f"{item}:noncausal_or_unbounded" for item in noncausal),
            len(schema.features),
        )

    forbidden: list[str] = []
    for item in schema.features:
        lowered = item.feature_id.lower()
        if any(token in lowered for token in _FORBIDDEN_TOKENS):
            forbidden.append(f"{item.feature_id}:forbidden_leakage_surface")
        elif not _is_approved(item):
            forbidden.append(f"{item.feature_id}:not_in_approved_whitelist")
    if forbidden:
        return Stage8FeatureContractAssessment(
            Stage8FeatureContractStatus.BLOCKED_UNAPPROVED_FEATURE,
            tuple(sorted(forbidden)),
            len(schema.features),
        )

    if not schema.frozen_before_training:
        return Stage8FeatureContractAssessment(
            Stage8FeatureContractStatus.BLOCKED_UNAPPROVED_FEATURE,
            ("feature_schema_not_frozen_before_training",),
            len(schema.features),
        )

    return Stage8FeatureContractAssessment(
        Stage8FeatureContractStatus.FEATURE_SCHEMA_FROZEN,
        (),
        len(schema.features),
    )
