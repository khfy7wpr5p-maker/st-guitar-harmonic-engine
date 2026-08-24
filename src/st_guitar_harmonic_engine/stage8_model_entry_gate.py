"""Fail-closed Stage 8 model-entry gate v0.1.

The gate prevents Teacher-Gold or HOLDOUT measurements from being turned directly
into a model-training target. It grants no production authority and does not start
training. Its highest possible outcome is eligibility to design a separately
authorized shadow research run over a preregistered, disjoint target corpus.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re


STAGE8_MODEL_ENTRY_GATE_VERSION = "0.1"
_EXPECTED_REFERENCE_CASES = 200
_EXPECTED_EXECUTABLE_CASES = 200
_TARGET_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")


class Stage8ModelEntryStatus(str, Enum):
    BLOCKED_DETERMINISTIC_EVIDENCE_INCOMPLETE = "blocked_deterministic_evidence_incomplete"
    BLOCKED_DETERMINISTIC_SUFFICIENT = "blocked_deterministic_sufficient"
    BLOCKED_NO_DISJOINT_TARGET = "blocked_no_disjoint_target"
    BLOCKED_TARGET_NOT_READY = "blocked_target_not_ready"
    BLOCKED_DATA_LEAKAGE = "blocked_data_leakage"
    SHADOW_RESEARCH_DESIGN_ELIGIBLE = "shadow_research_design_eligible"


@dataclass(frozen=True, slots=True)
class Stage8DeterministicSummary:
    """Aggregate-only deterministic evidence; contains no Teacher-Gold rows."""

    reference_case_count: int
    executable_case_count: int
    correct_case_count: int
    validation_or_runtime_error_count: int
    deterministic_stable: bool

    def __post_init__(self) -> None:
        for name in (
            "reference_case_count",
            "executable_case_count",
            "correct_case_count",
            "validation_or_runtime_error_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative int")
        if self.correct_case_count > self.executable_case_count:
            raise ValueError("correct_case_count cannot exceed executable_case_count")
        if not isinstance(self.deterministic_stable, bool):
            raise TypeError("deterministic_stable must be bool")

    @property
    def is_complete_and_stable(self) -> bool:
        return (
            self.reference_case_count == _EXPECTED_REFERENCE_CASES
            and self.executable_case_count == _EXPECTED_EXECUTABLE_CASES
            and self.validation_or_runtime_error_count == 0
            and self.deterministic_stable
        )

    @property
    def is_fully_correct(self) -> bool:
        return self.is_complete_and_stable and self.correct_case_count == self.executable_case_count


@dataclass(frozen=True, slots=True)
class Stage8ResearchTarget:
    """Preregistered target metadata only; never contains training examples."""

    target_id: str
    case_count: int
    preregistered: bool
    authorized_source: bool
    teacher_gold_overlap_count: int
    holdout_overlap_count: int
    derived_from_holdout_labels: bool

    def __post_init__(self) -> None:
        if not isinstance(self.target_id, str) or _TARGET_ID_RE.fullmatch(self.target_id) is None:
            raise ValueError("target_id must be a canonical 3..64 character token")
        for name in ("case_count", "teacher_gold_overlap_count", "holdout_overlap_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative int")
        for name in ("preregistered", "authorized_source", "derived_from_holdout_labels"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")
        if self.teacher_gold_overlap_count > self.case_count:
            raise ValueError("teacher_gold_overlap_count cannot exceed case_count")
        if self.holdout_overlap_count > self.case_count:
            raise ValueError("holdout_overlap_count cannot exceed case_count")

    @property
    def is_disjoint(self) -> bool:
        return (
            self.teacher_gold_overlap_count == 0
            and self.holdout_overlap_count == 0
            and not self.derived_from_holdout_labels
        )

    @property
    def is_ready(self) -> bool:
        return self.case_count > 0 and self.preregistered and self.authorized_source and self.is_disjoint


@dataclass(frozen=True, slots=True)
class Stage8ModelEntryAssessment:
    status: Stage8ModelEntryStatus
    reasons: tuple[str, ...]
    model_training_authorized: bool = False
    production_authority_granted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.status, Stage8ModelEntryStatus):
            raise TypeError("status must be Stage8ModelEntryStatus")
        if not isinstance(self.reasons, tuple) or any(
            not isinstance(item, str) or not item for item in self.reasons
        ):
            raise TypeError("reasons must contain non-empty strings")
        if tuple(sorted(set(self.reasons))) != self.reasons:
            raise ValueError("reasons must be unique canonical order")
        if self.model_training_authorized or self.production_authority_granted:
            raise ValueError("Stage 8 model-entry gate cannot authorize training or production")
        if self.status is Stage8ModelEntryStatus.SHADOW_RESEARCH_DESIGN_ELIGIBLE and self.reasons:
            raise ValueError("eligible assessment cannot contain blocking reasons")
        if self.status is not Stage8ModelEntryStatus.SHADOW_RESEARCH_DESIGN_ELIGIBLE and not self.reasons:
            raise ValueError("blocked assessment requires reasons")


def assess_stage8_model_entry(
    deterministic: Stage8DeterministicSummary,
    target: Stage8ResearchTarget | None = None,
) -> Stage8ModelEntryAssessment:
    """Assess whether a separate shadow-research design may be prepared.

    This function never authorizes training. A caller must supply a distinct,
    preregistered, authorized and Teacher-Gold/HOLDOUT-disjoint target before even
    shadow research design becomes eligible.
    """

    if not isinstance(deterministic, Stage8DeterministicSummary):
        raise TypeError("deterministic must be Stage8DeterministicSummary")
    if target is not None and not isinstance(target, Stage8ResearchTarget):
        raise TypeError("target must be Stage8ResearchTarget or None")

    if not deterministic.is_complete_and_stable:
        return Stage8ModelEntryAssessment(
            Stage8ModelEntryStatus.BLOCKED_DETERMINISTIC_EVIDENCE_INCOMPLETE,
            ("deterministic_reference_not_complete_and_stable",),
        )

    if target is None:
        status = (
            Stage8ModelEntryStatus.BLOCKED_DETERMINISTIC_SUFFICIENT
            if deterministic.is_fully_correct
            else Stage8ModelEntryStatus.BLOCKED_NO_DISJOINT_TARGET
        )
        reason = (
            "frozen_teacher_gold_already_fully_solved_deterministically"
            if deterministic.is_fully_correct
            else "no_preregistered_disjoint_research_target"
        )
        return Stage8ModelEntryAssessment(status, (reason,))

    leakage_reasons: list[str] = []
    if target.teacher_gold_overlap_count:
        leakage_reasons.append("teacher_gold_overlap_present")
    if target.holdout_overlap_count:
        leakage_reasons.append("holdout_overlap_present")
    if target.derived_from_holdout_labels:
        leakage_reasons.append("target_derived_from_holdout_labels")
    if leakage_reasons:
        return Stage8ModelEntryAssessment(
            Stage8ModelEntryStatus.BLOCKED_DATA_LEAKAGE,
            tuple(sorted(leakage_reasons)),
        )

    readiness_reasons: list[str] = []
    if target.case_count == 0:
        readiness_reasons.append("target_is_empty")
    if not target.preregistered:
        readiness_reasons.append("target_not_preregistered")
    if not target.authorized_source:
        readiness_reasons.append("target_source_not_authorized")
    if readiness_reasons:
        return Stage8ModelEntryAssessment(
            Stage8ModelEntryStatus.BLOCKED_TARGET_NOT_READY,
            tuple(sorted(readiness_reasons)),
        )

    return Stage8ModelEntryAssessment(
        Stage8ModelEntryStatus.SHADOW_RESEARCH_DESIGN_ELIGIBLE,
        (),
    )
