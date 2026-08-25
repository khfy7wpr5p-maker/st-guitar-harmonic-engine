"""Fail-closed Stage 8 research preregistration contract v0.1.

This contract binds a future shadow-research design to a frozen objective, metric,
data-manifest fingerprint, and deterministic engine baseline before any training
plan can be proposed. It does not authorize model training or production use.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re


STAGE8_RESEARCH_PREREGISTRATION_VERSION = "0.1"
_TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class Stage8PrimaryMetric(str, Enum):
    FALSE_RESOLUTION_RATE = "false_resolution_rate"
    CANDIDATE_TOP1 = "candidate_top1"
    AMBIGUITY_RECALL = "ambiguity_recall"
    ABSTENTION_F1 = "abstention_f1"
    OOD_REJECTION_RATE = "ood_rejection_rate"


class Stage8PreregistrationStatus(str, Enum):
    BLOCKED_INCOMPLETE = "blocked_incomplete"
    BLOCKED_DATA_LEAKAGE = "blocked_data_leakage"
    BLOCKED_GOVERNANCE = "blocked_governance"
    BLOCKED_NOT_FROZEN = "blocked_not_frozen"
    RESEARCH_DESIGN_PREREGISTERED = "research_design_preregistered"


@dataclass(frozen=True, slots=True)
class Stage8ResearchPreregistration:
    target_id: str
    objective_id: str
    primary_metric: Stage8PrimaryMetric
    dataset_manifest_sha256: str
    deterministic_engine_sha: str
    train_case_count: int
    validation_case_count: int
    teacher_gold_overlap_count: int
    holdout_overlap_count: int
    uses_holdout_for_model_selection: bool
    derived_from_holdout_labels: bool
    data_governance_passed: bool
    target_authorized: bool
    frozen_before_training: bool

    def __post_init__(self) -> None:
        for name in ("target_id", "objective_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or _TOKEN_RE.fullmatch(value) is None:
                raise ValueError(f"{name} must be a canonical 3..64 character token")
        if not isinstance(self.primary_metric, Stage8PrimaryMetric):
            raise TypeError("primary_metric must be Stage8PrimaryMetric")
        if not isinstance(self.dataset_manifest_sha256, str) or _SHA256_RE.fullmatch(
            self.dataset_manifest_sha256
        ) is None:
            raise ValueError("dataset_manifest_sha256 must be lowercase SHA-256")
        if not isinstance(self.deterministic_engine_sha, str) or _SHA40_RE.fullmatch(
            self.deterministic_engine_sha
        ) is None:
            raise ValueError("deterministic_engine_sha must be lowercase 40-character SHA")
        for name in (
            "train_case_count",
            "validation_case_count",
            "teacher_gold_overlap_count",
            "holdout_overlap_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative int")
        total = self.train_case_count + self.validation_case_count
        if self.teacher_gold_overlap_count > total:
            raise ValueError("teacher_gold_overlap_count cannot exceed corpus size")
        if self.holdout_overlap_count > total:
            raise ValueError("holdout_overlap_count cannot exceed corpus size")
        for name in (
            "uses_holdout_for_model_selection",
            "derived_from_holdout_labels",
            "data_governance_passed",
            "target_authorized",
            "frozen_before_training",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")

    @property
    def corpus_case_count(self) -> int:
        return self.train_case_count + self.validation_case_count

    @property
    def canonical_sha256(self) -> str:
        payload = {
            "version": STAGE8_RESEARCH_PREREGISTRATION_VERSION,
            "target_id": self.target_id,
            "objective_id": self.objective_id,
            "primary_metric": self.primary_metric.value,
            "dataset_manifest_sha256": self.dataset_manifest_sha256,
            "deterministic_engine_sha": self.deterministic_engine_sha,
            "train_case_count": self.train_case_count,
            "validation_case_count": self.validation_case_count,
            "teacher_gold_overlap_count": self.teacher_gold_overlap_count,
            "holdout_overlap_count": self.holdout_overlap_count,
            "uses_holdout_for_model_selection": self.uses_holdout_for_model_selection,
            "derived_from_holdout_labels": self.derived_from_holdout_labels,
            "data_governance_passed": self.data_governance_passed,
            "target_authorized": self.target_authorized,
            "frozen_before_training": self.frozen_before_training,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Stage8PreregistrationAssessment:
    status: Stage8PreregistrationStatus
    reasons: tuple[str, ...]
    preregistration_sha256: str
    model_training_authorized: bool = False
    production_authority_granted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.status, Stage8PreregistrationStatus):
            raise TypeError("status must be Stage8PreregistrationStatus")
        if not isinstance(self.reasons, tuple) or any(
            not isinstance(item, str) or not item for item in self.reasons
        ):
            raise TypeError("reasons must contain non-empty strings")
        if tuple(sorted(set(self.reasons))) != self.reasons:
            raise ValueError("reasons must be unique canonical order")
        if not isinstance(self.preregistration_sha256, str) or _SHA256_RE.fullmatch(
            self.preregistration_sha256
        ) is None:
            raise ValueError("preregistration_sha256 must be lowercase SHA-256")
        if self.model_training_authorized or self.production_authority_granted:
            raise ValueError("preregistration cannot authorize training or production")
        if self.status is Stage8PreregistrationStatus.RESEARCH_DESIGN_PREREGISTERED and self.reasons:
            raise ValueError("preregistered result cannot contain blocking reasons")
        if self.status is not Stage8PreregistrationStatus.RESEARCH_DESIGN_PREREGISTERED and not self.reasons:
            raise ValueError("blocked result requires reasons")


def assess_stage8_research_preregistration(
    preregistration: Stage8ResearchPreregistration,
) -> Stage8PreregistrationAssessment:
    """Validate one aggregate preregistration without granting training authority."""

    if not isinstance(preregistration, Stage8ResearchPreregistration):
        raise TypeError("preregistration must be Stage8ResearchPreregistration")

    digest = preregistration.canonical_sha256
    if preregistration.corpus_case_count == 0 or preregistration.train_case_count == 0:
        return Stage8PreregistrationAssessment(
            Stage8PreregistrationStatus.BLOCKED_INCOMPLETE,
            ("research_corpus_or_training_partition_is_empty",),
            digest,
        )

    leakage: list[str] = []
    if preregistration.teacher_gold_overlap_count:
        leakage.append("teacher_gold_overlap_present")
    if preregistration.holdout_overlap_count:
        leakage.append("holdout_overlap_present")
    if preregistration.uses_holdout_for_model_selection:
        leakage.append("holdout_used_for_model_selection")
    if preregistration.derived_from_holdout_labels:
        leakage.append("target_derived_from_holdout_labels")
    if leakage:
        return Stage8PreregistrationAssessment(
            Stage8PreregistrationStatus.BLOCKED_DATA_LEAKAGE,
            tuple(sorted(leakage)),
            digest,
        )

    governance: list[str] = []
    if not preregistration.data_governance_passed:
        governance.append("data_governance_not_passed")
    if not preregistration.target_authorized:
        governance.append("research_target_not_authorized")
    if governance:
        return Stage8PreregistrationAssessment(
            Stage8PreregistrationStatus.BLOCKED_GOVERNANCE,
            tuple(sorted(governance)),
            digest,
        )

    if not preregistration.frozen_before_training:
        return Stage8PreregistrationAssessment(
            Stage8PreregistrationStatus.BLOCKED_NOT_FROZEN,
            ("preregistration_not_frozen_before_training",),
            digest,
        )

    return Stage8PreregistrationAssessment(
        Stage8PreregistrationStatus.RESEARCH_DESIGN_PREREGISTERED,
        (),
        digest,
    )
