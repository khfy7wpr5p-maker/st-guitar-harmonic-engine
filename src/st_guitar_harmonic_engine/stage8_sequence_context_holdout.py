"""Untouched Stage 8 sequence/context holdout contract v0.1.

This contract isolates the final SC-HOLDOUT from training and model selection. It
contains metadata only and cannot authorize training or production authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from .stage8_feature_contract import STAGE8_FEATURE_CONTRACT_VERSION
from .stage8_sequence_context_sample_plan import canonical_stage8_sequence_context_sample_plan
from .stage8_sequence_context_target import STAGE8_SEQUENCE_CONTEXT_TARGET_ID


STAGE8_SEQUENCE_CONTEXT_HOLDOUT_VERSION = "0.1"
_HOLDOUT_CASE_RE = re.compile(r"^SCH-[0-9]{5}$")
_TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{2,127}$")
_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_EXPECTED_HOLDOUT_IDS = tuple(f"SCH-{index:05d}" for index in range(1, 201))


class Stage8HoldoutAnnotationStatus(str, Enum):
    DRAFT = "draft"
    VERIFIED = "verified"


class Stage8SequenceContextHoldoutStatus(str, Enum):
    BLOCKED_COUNT_OR_NAMESPACE = "blocked_count_or_namespace"
    BLOCKED_DUPLICATE = "blocked_duplicate"
    BLOCKED_DATA_LEAKAGE = "blocked_data_leakage"
    BLOCKED_RIGHTS = "blocked_rights"
    BLOCKED_SPLIT_LEAKAGE = "blocked_split_leakage"
    BLOCKED_SOURCE_ALLOCATION = "blocked_source_allocation"
    BLOCKED_ANNOTATION = "blocked_annotation"
    HOLDOUT_FREEZE_READY = "holdout_freeze_ready"


@dataclass(frozen=True, slots=True)
class Stage8SequenceContextHoldoutCase:
    case_id: str
    target_id: str
    source_id: str
    source_group_id: str
    source_item_sha256: str
    candidate_set_sha256: str
    candidate_ids: tuple[str, ...]
    preferred_candidate_id: str | None
    no_preference: bool
    annotation_status: Stage8HoldoutAnnotationStatus
    rights_governance_passed: bool
    teacher_gold_overlap: bool
    teacher_gold_holdout_overlap: bool
    training_corpus_overlap: bool
    derived_from_teacher_gold_or_holdout_labels: bool
    feature_contract_version: str
    deterministic_engine_sha: str

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or _HOLDOUT_CASE_RE.fullmatch(self.case_id) is None:
            raise ValueError("case_id must match SCH-00000 namespace")
        if self.target_id != STAGE8_SEQUENCE_CONTEXT_TARGET_ID:
            raise ValueError("target_id must match the approved Stage 8 target")
        for name in ("source_id", "source_group_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or _TOKEN_RE.fullmatch(value) is None:
                raise ValueError(f"{name} must be a canonical token")
        for name in ("source_item_sha256", "candidate_set_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
                raise ValueError(f"{name} must be lowercase SHA-256")
        if not isinstance(self.candidate_ids, tuple) or len(self.candidate_ids) < 2:
            raise ValueError("candidate_ids must contain at least two candidates")
        if any(not isinstance(item, str) or _TOKEN_RE.fullmatch(item) is None for item in self.candidate_ids):
            raise ValueError("candidate_ids must contain canonical tokens")
        if tuple(sorted(set(self.candidate_ids))) != self.candidate_ids:
            raise ValueError("candidate_ids must be unique canonical order")
        if self.preferred_candidate_id is not None:
            if self.preferred_candidate_id not in self.candidate_ids:
                raise ValueError("preferred_candidate_id must be inside candidate_ids")
        if not isinstance(self.annotation_status, Stage8HoldoutAnnotationStatus):
            raise TypeError("annotation_status must be Stage8HoldoutAnnotationStatus")
        for name in (
            "no_preference",
            "rights_governance_passed",
            "teacher_gold_overlap",
            "teacher_gold_holdout_overlap",
            "training_corpus_overlap",
            "derived_from_teacher_gold_or_holdout_labels",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")
        if self.annotation_status is Stage8HoldoutAnnotationStatus.VERIFIED:
            has_preference = self.preferred_candidate_id is not None
            if has_preference == self.no_preference:
                raise ValueError("VERIFIED holdout requires exactly one of preferred candidate or no_preference")
        if self.feature_contract_version != STAGE8_FEATURE_CONTRACT_VERSION:
            raise ValueError("feature_contract_version must match frozen Stage 8-B contract")
        if not isinstance(self.deterministic_engine_sha, str) or _SHA40_RE.fullmatch(
            self.deterministic_engine_sha
        ) is None:
            raise ValueError("deterministic_engine_sha must be lowercase 40-character SHA")


@dataclass(frozen=True, slots=True)
class Stage8SequenceContextHoldoutAssessment:
    status: Stage8SequenceContextHoldoutStatus
    reasons: tuple[str, ...]
    case_count: int
    verified_case_count: int
    preference_case_count: int
    no_preference_case_count: int
    model_selection_authorized: bool = False
    model_training_authorized: bool = False
    production_authority_granted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.status, Stage8SequenceContextHoldoutStatus):
            raise TypeError("status must be Stage8SequenceContextHoldoutStatus")
        if not isinstance(self.reasons, tuple) or any(
            not isinstance(item, str) or not item for item in self.reasons
        ):
            raise TypeError("reasons must contain non-empty strings")
        if tuple(sorted(set(self.reasons))) != self.reasons:
            raise ValueError("reasons must be unique canonical order")
        for name in (
            "case_count",
            "verified_case_count",
            "preference_case_count",
            "no_preference_case_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative int")
        if self.model_selection_authorized or self.model_training_authorized or self.production_authority_granted:
            raise ValueError("holdout readiness cannot authorize selection, training, or production")
        ready = self.status is Stage8SequenceContextHoldoutStatus.HOLDOUT_FREEZE_READY
        if ready and self.reasons:
            raise ValueError("ready holdout cannot contain blocking reasons")
        if not ready and not self.reasons:
            raise ValueError("blocked holdout requires reasons")


def _assessment(
    status: Stage8SequenceContextHoldoutStatus,
    reasons: tuple[str, ...],
    cases: tuple[Stage8SequenceContextHoldoutCase, ...],
) -> Stage8SequenceContextHoldoutAssessment:
    verified = tuple(
        item for item in cases if item.annotation_status is Stage8HoldoutAnnotationStatus.VERIFIED
    )
    return Stage8SequenceContextHoldoutAssessment(
        status=status,
        reasons=tuple(sorted(set(reasons))),
        case_count=len(cases),
        verified_case_count=len(verified),
        preference_case_count=sum(item.preferred_candidate_id is not None for item in verified),
        no_preference_case_count=sum(item.no_preference for item in verified),
    )


def assess_sequence_context_holdout(
    cases: tuple[Stage8SequenceContextHoldoutCase, ...],
    *,
    training_source_group_ids: frozenset[str],
    validation_source_group_ids: frozenset[str],
) -> Stage8SequenceContextHoldoutAssessment:
    """Assess whether the 200-case untouched SC-HOLDOUT is safe to freeze."""

    if not isinstance(cases, tuple) or any(
        not isinstance(item, Stage8SequenceContextHoldoutCase) for item in cases
    ):
        raise TypeError("cases must contain Stage8SequenceContextHoldoutCase values")
    for name, groups in (
        ("training_source_group_ids", training_source_group_ids),
        ("validation_source_group_ids", validation_source_group_ids),
    ):
        if not isinstance(groups, frozenset) or any(not isinstance(item, str) or not item for item in groups):
            raise TypeError(f"{name} must be frozenset[str]")

    case_ids = tuple(item.case_id for item in cases)
    if len(cases) != 200 or tuple(sorted(case_ids)) != _EXPECTED_HOLDOUT_IDS:
        return _assessment(
            Stage8SequenceContextHoldoutStatus.BLOCKED_COUNT_OR_NAMESPACE,
            ("holdout_requires_exact_sch_00001_through_sch_00200",),
            cases,
        )

    source_items = [item.source_item_sha256 for item in cases]
    if len(set(source_items)) != len(source_items):
        return _assessment(
            Stage8SequenceContextHoldoutStatus.BLOCKED_DUPLICATE,
            ("duplicate_holdout_source_item",),
            cases,
        )

    leakage: list[str] = []
    for item in cases:
        if item.teacher_gold_overlap:
            leakage.append(f"{item.case_id}:teacher_gold_overlap")
        if item.teacher_gold_holdout_overlap:
            leakage.append(f"{item.case_id}:teacher_gold_holdout_overlap")
        if item.training_corpus_overlap:
            leakage.append(f"{item.case_id}:training_corpus_overlap")
        if item.derived_from_teacher_gold_or_holdout_labels:
            leakage.append(f"{item.case_id}:derived_from_reference_labels")
    if leakage:
        return _assessment(
            Stage8SequenceContextHoldoutStatus.BLOCKED_DATA_LEAKAGE,
            tuple(leakage),
            cases,
        )

    rights = tuple(
        f"{item.case_id}:rights_governance_not_passed"
        for item in cases
        if not item.rights_governance_passed
    )
    if rights:
        return _assessment(Stage8SequenceContextHoldoutStatus.BLOCKED_RIGHTS, rights, cases)

    holdout_groups = {item.source_group_id for item in cases}
    crossed = holdout_groups & (set(training_source_group_ids) | set(validation_source_group_ids))
    if crossed:
        return _assessment(
            Stage8SequenceContextHoldoutStatus.BLOCKED_SPLIT_LEAKAGE,
            tuple(f"{group_id}:holdout_group_seen_in_train_or_validation" for group_id in sorted(crossed)),
            cases,
        )

    expected = {
        item.source_id: item.holdout_cases
        for item in canonical_stage8_sequence_context_sample_plan().sources
        if item.holdout_cases
    }
    observed = {source_id: sum(item.source_id == source_id for item in cases) for source_id in expected}
    unknown = sorted({item.source_id for item in cases} - set(expected))
    if observed != expected or unknown:
        reasons = ["holdout_source_allocation_mismatch"]
        reasons.extend(f"{source_id}:unapproved_holdout_source" for source_id in unknown)
        return _assessment(
            Stage8SequenceContextHoldoutStatus.BLOCKED_SOURCE_ALLOCATION,
            tuple(reasons),
            cases,
        )

    draft = tuple(
        f"{item.case_id}:annotation_not_verified"
        for item in cases
        if item.annotation_status is not Stage8HoldoutAnnotationStatus.VERIFIED
    )
    if draft:
        return _assessment(
            Stage8SequenceContextHoldoutStatus.BLOCKED_ANNOTATION,
            draft,
            cases,
        )

    return _assessment(Stage8SequenceContextHoldoutStatus.HOLDOUT_FREEZE_READY, (), cases)
