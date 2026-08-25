"""Fail-closed Stage 8 sequence/context research-corpus contract v0.1.

The contract governs aggregate metadata and human-adjudication state for a future
research corpus. It does not contain raw score/audio material, perform musical
adjudication, train a model, or grant production authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from .stage8_feature_contract import STAGE8_FEATURE_CONTRACT_VERSION
from .stage8_sequence_context_target import STAGE8_SEQUENCE_CONTEXT_TARGET_ID


STAGE8_SEQUENCE_CONTEXT_CORPUS_VERSION = "0.1"
_CASE_ID_RE = re.compile(r"^SC-[0-9]{5}$")
_TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{2,127}$")
_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class Stage8CorpusSplit(str, Enum):
    TRAIN = "train"
    VALIDATION = "validation"


class Stage8CorpusAnnotationStatus(str, Enum):
    DRAFT = "draft"
    VERIFIED = "verified"


class Stage8SequenceContextCorpusStatus(str, Enum):
    BLOCKED_EMPTY = "blocked_empty"
    BLOCKED_DUPLICATE = "blocked_duplicate"
    BLOCKED_DATA_LEAKAGE = "blocked_data_leakage"
    BLOCKED_RIGHTS = "blocked_rights"
    BLOCKED_SPLIT_LEAKAGE = "blocked_split_leakage"
    BLOCKED_ANNOTATION = "blocked_annotation"
    CORPUS_DESIGN_READY = "corpus_design_ready"


@dataclass(frozen=True, slots=True)
class Stage8SequenceContextCorpusCase:
    """Metadata-only record for one independently sourced ambiguity case."""

    case_id: str
    target_id: str
    split: Stage8CorpusSplit
    source_id: str
    source_group_id: str
    source_item_sha256: str
    candidate_set_sha256: str
    candidate_ids: tuple[str, ...]
    preferred_candidate_id: str | None
    no_preference: bool
    annotation_status: Stage8CorpusAnnotationStatus
    rights_governance_passed: bool
    teacher_gold_overlap: bool
    holdout_overlap: bool
    derived_from_holdout_labels: bool
    feature_contract_version: str
    deterministic_engine_sha: str

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or _CASE_ID_RE.fullmatch(self.case_id) is None:
            raise ValueError("case_id must match SC-00000 namespace")
        if self.target_id != STAGE8_SEQUENCE_CONTEXT_TARGET_ID:
            raise ValueError("target_id must match the approved Stage 8 target")
        if not isinstance(self.split, Stage8CorpusSplit):
            raise TypeError("split must be Stage8CorpusSplit")
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
            if not isinstance(self.preferred_candidate_id, str):
                raise TypeError("preferred_candidate_id must be str or None")
            if self.preferred_candidate_id not in self.candidate_ids:
                raise ValueError("preferred_candidate_id must be inside candidate_ids")
        for name in (
            "no_preference",
            "rights_governance_passed",
            "teacher_gold_overlap",
            "holdout_overlap",
            "derived_from_holdout_labels",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")
        if not isinstance(self.annotation_status, Stage8CorpusAnnotationStatus):
            raise TypeError("annotation_status must be Stage8CorpusAnnotationStatus")
        if self.annotation_status is Stage8CorpusAnnotationStatus.VERIFIED:
            has_preference = self.preferred_candidate_id is not None
            if has_preference == self.no_preference:
                raise ValueError("VERIFIED case requires exactly one of preferred candidate or no_preference")
        if self.feature_contract_version != STAGE8_FEATURE_CONTRACT_VERSION:
            raise ValueError("feature_contract_version must match frozen Stage 8-B contract")
        if not isinstance(self.deterministic_engine_sha, str) or _SHA40_RE.fullmatch(
            self.deterministic_engine_sha
        ) is None:
            raise ValueError("deterministic_engine_sha must be lowercase 40-character SHA")


@dataclass(frozen=True, slots=True)
class Stage8SequenceContextCorpusAssessment:
    status: Stage8SequenceContextCorpusStatus
    reasons: tuple[str, ...]
    case_count: int
    train_case_count: int
    validation_case_count: int
    verified_case_count: int
    preference_case_count: int
    no_preference_case_count: int
    model_training_authorized: bool = False
    production_authority_granted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.status, Stage8SequenceContextCorpusStatus):
            raise TypeError("status must be Stage8SequenceContextCorpusStatus")
        if not isinstance(self.reasons, tuple) or any(
            not isinstance(item, str) or not item for item in self.reasons
        ):
            raise TypeError("reasons must contain non-empty strings")
        if tuple(sorted(set(self.reasons))) != self.reasons:
            raise ValueError("reasons must be unique canonical order")
        for name in (
            "case_count",
            "train_case_count",
            "validation_case_count",
            "verified_case_count",
            "preference_case_count",
            "no_preference_case_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative int")
        if self.train_case_count + self.validation_case_count != self.case_count:
            raise ValueError("split counts must sum to case_count")
        if self.preference_case_count + self.no_preference_case_count > self.verified_case_count:
            raise ValueError("verified label counts cannot exceed verified_case_count")
        if self.model_training_authorized or self.production_authority_granted:
            raise ValueError("corpus readiness cannot authorize training or production")
        ready = self.status is Stage8SequenceContextCorpusStatus.CORPUS_DESIGN_READY
        if ready and self.reasons:
            raise ValueError("ready assessment cannot contain blocking reasons")
        if not ready and not self.reasons:
            raise ValueError("blocked assessment requires reasons")


def _assessment(
    status: Stage8SequenceContextCorpusStatus,
    reasons: tuple[str, ...],
    cases: tuple[Stage8SequenceContextCorpusCase, ...],
) -> Stage8SequenceContextCorpusAssessment:
    verified = tuple(
        item for item in cases if item.annotation_status is Stage8CorpusAnnotationStatus.VERIFIED
    )
    return Stage8SequenceContextCorpusAssessment(
        status=status,
        reasons=tuple(sorted(set(reasons))),
        case_count=len(cases),
        train_case_count=sum(item.split is Stage8CorpusSplit.TRAIN for item in cases),
        validation_case_count=sum(item.split is Stage8CorpusSplit.VALIDATION for item in cases),
        verified_case_count=len(verified),
        preference_case_count=sum(item.preferred_candidate_id is not None for item in verified),
        no_preference_case_count=sum(item.no_preference for item in verified),
    )


def assess_sequence_context_corpus(
    cases: tuple[Stage8SequenceContextCorpusCase, ...],
) -> Stage8SequenceContextCorpusAssessment:
    """Assess metadata readiness of a future human-adjudicated research corpus."""

    if not isinstance(cases, tuple) or any(
        not isinstance(item, Stage8SequenceContextCorpusCase) for item in cases
    ):
        raise TypeError("cases must contain Stage8SequenceContextCorpusCase values")
    if not cases:
        return _assessment(
            Stage8SequenceContextCorpusStatus.BLOCKED_EMPTY,
            ("research_corpus_is_empty",),
            cases,
        )

    case_ids = [item.case_id for item in cases]
    source_items = [item.source_item_sha256 for item in cases]
    if len(set(case_ids)) != len(case_ids) or len(set(source_items)) != len(source_items):
        return _assessment(
            Stage8SequenceContextCorpusStatus.BLOCKED_DUPLICATE,
            ("duplicate_case_id_or_source_item",),
            cases,
        )

    leakage: list[str] = []
    for item in cases:
        if item.teacher_gold_overlap:
            leakage.append(f"{item.case_id}:teacher_gold_overlap")
        if item.holdout_overlap:
            leakage.append(f"{item.case_id}:holdout_overlap")
        if item.derived_from_holdout_labels:
            leakage.append(f"{item.case_id}:derived_from_holdout_labels")
    if leakage:
        return _assessment(
            Stage8SequenceContextCorpusStatus.BLOCKED_DATA_LEAKAGE,
            tuple(leakage),
            cases,
        )

    rights = tuple(
        f"{item.case_id}:rights_governance_not_passed"
        for item in cases
        if not item.rights_governance_passed
    )
    if rights:
        return _assessment(
            Stage8SequenceContextCorpusStatus.BLOCKED_RIGHTS,
            rights,
            cases,
        )

    group_splits: dict[str, set[Stage8CorpusSplit]] = {}
    for item in cases:
        group_splits.setdefault(item.source_group_id, set()).add(item.split)
    crossed = tuple(
        f"{group_id}:source_group_crosses_train_validation"
        for group_id, splits in sorted(group_splits.items())
        if len(splits) > 1
    )
    if crossed:
        return _assessment(
            Stage8SequenceContextCorpusStatus.BLOCKED_SPLIT_LEAKAGE,
            crossed,
            cases,
        )

    if not any(item.split is Stage8CorpusSplit.TRAIN for item in cases) or not any(
        item.split is Stage8CorpusSplit.VALIDATION for item in cases
    ):
        return _assessment(
            Stage8SequenceContextCorpusStatus.BLOCKED_SPLIT_LEAKAGE,
            ("both_train_and_validation_partitions_are_required",),
            cases,
        )

    annotation: list[str] = []
    for item in cases:
        if item.annotation_status is not Stage8CorpusAnnotationStatus.VERIFIED:
            annotation.append(f"{item.case_id}:annotation_not_verified")
    if annotation:
        return _assessment(
            Stage8SequenceContextCorpusStatus.BLOCKED_ANNOTATION,
            tuple(annotation),
            cases,
        )

    return _assessment(
        Stage8SequenceContextCorpusStatus.CORPUS_DESIGN_READY,
        (),
        cases,
    )
