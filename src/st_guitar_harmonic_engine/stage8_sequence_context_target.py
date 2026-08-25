"""Fail-closed Stage 8 sequence/context ambiguity shadow-ranking target v0.1.

This module defines the approved research *target shape* only. It does not select
or ingest a corpus, extract features, train a model, change harmonic authority, or
grant production use.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


STAGE8_SEQUENCE_CONTEXT_TARGET_VERSION = "0.1"
STAGE8_SEQUENCE_CONTEXT_TARGET_ID = "sequence-context-ambiguity-shadow-v1"
STAGE8_SEQUENCE_CONTEXT_OBJECTIVE_ID = "rank-existing-ambiguous-candidates-causally"
_MAX_PREVIOUS_FRAMES = 4


class Stage8SequenceContextTargetStatus(str, Enum):
    BLOCKED_TARGET_MISMATCH = "blocked_target_mismatch"
    BLOCKED_NONCAUSAL_CONTEXT = "blocked_noncausal_context"
    BLOCKED_AUTHORITY_RISK = "blocked_authority_risk"
    BLOCKED_LABEL_LEAKAGE = "blocked_label_leakage"
    TARGET_DESIGN_ELIGIBLE = "target_design_eligible"


@dataclass(frozen=True, slots=True)
class Stage8SequenceContextTarget:
    """Aggregate design metadata for the approved shadow-ranking target.

    The task is intentionally narrow: for a frame already left AMBIGUOUS by the
    deterministic engine, rank only the existing deterministic candidate set.
    """

    target_id: str
    objective_id: str
    previous_frame_limit: int
    uses_current_frame: bool
    uses_previous_frames: bool
    uses_future_frames: bool
    requires_source_state_ambiguous: bool
    candidate_set_immutable: bool
    may_generate_candidates: bool
    may_change_authoritative_state: bool
    may_suppress_abstain_or_no_match: bool
    teacher_gold_labels_available_to_model: bool
    holdout_labels_available_to_model: bool
    derived_from_holdout_labels: bool

    def __post_init__(self) -> None:
        if not isinstance(self.target_id, str) or not self.target_id:
            raise TypeError("target_id must be a non-empty string")
        if not isinstance(self.objective_id, str) or not self.objective_id:
            raise TypeError("objective_id must be a non-empty string")
        if isinstance(self.previous_frame_limit, bool) or not isinstance(self.previous_frame_limit, int):
            raise TypeError("previous_frame_limit must be int")
        if self.previous_frame_limit < 0 or self.previous_frame_limit > _MAX_PREVIOUS_FRAMES:
            raise ValueError(f"previous_frame_limit must be in 0..{_MAX_PREVIOUS_FRAMES}")
        for name in (
            "uses_current_frame",
            "uses_previous_frames",
            "uses_future_frames",
            "requires_source_state_ambiguous",
            "candidate_set_immutable",
            "may_generate_candidates",
            "may_change_authoritative_state",
            "may_suppress_abstain_or_no_match",
            "teacher_gold_labels_available_to_model",
            "holdout_labels_available_to_model",
            "derived_from_holdout_labels",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")
        if not self.uses_previous_frames and self.previous_frame_limit != 0:
            raise ValueError("previous_frame_limit must be 0 when previous frames are disabled")
        if self.uses_previous_frames and self.previous_frame_limit == 0:
            raise ValueError("previous_frame_limit must be positive when previous frames are enabled")


@dataclass(frozen=True, slots=True)
class Stage8SequenceContextTargetAssessment:
    status: Stage8SequenceContextTargetStatus
    reasons: tuple[str, ...]
    research_design_authorized: bool
    model_training_authorized: bool = False
    production_authority_granted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.status, Stage8SequenceContextTargetStatus):
            raise TypeError("status must be Stage8SequenceContextTargetStatus")
        if not isinstance(self.reasons, tuple) or any(
            not isinstance(item, str) or not item for item in self.reasons
        ):
            raise TypeError("reasons must contain non-empty strings")
        if tuple(sorted(set(self.reasons))) != self.reasons:
            raise ValueError("reasons must be unique canonical order")
        if not isinstance(self.research_design_authorized, bool):
            raise TypeError("research_design_authorized must be bool")
        if self.model_training_authorized or self.production_authority_granted:
            raise ValueError("target contract cannot authorize training or production")
        eligible = self.status is Stage8SequenceContextTargetStatus.TARGET_DESIGN_ELIGIBLE
        if eligible != self.research_design_authorized:
            raise ValueError("research_design_authorized must match eligible status")
        if eligible and self.reasons:
            raise ValueError("eligible assessment cannot contain blocking reasons")
        if not eligible and not self.reasons:
            raise ValueError("blocked assessment requires reasons")


def approved_sequence_context_target() -> Stage8SequenceContextTarget:
    """Return the canonical approved target shape.

    Four previous frames is a hard maximum, not a requirement for every future
    feature schema. No future-frame access is permitted.
    """

    return Stage8SequenceContextTarget(
        target_id=STAGE8_SEQUENCE_CONTEXT_TARGET_ID,
        objective_id=STAGE8_SEQUENCE_CONTEXT_OBJECTIVE_ID,
        previous_frame_limit=_MAX_PREVIOUS_FRAMES,
        uses_current_frame=True,
        uses_previous_frames=True,
        uses_future_frames=False,
        requires_source_state_ambiguous=True,
        candidate_set_immutable=True,
        may_generate_candidates=False,
        may_change_authoritative_state=False,
        may_suppress_abstain_or_no_match=False,
        teacher_gold_labels_available_to_model=False,
        holdout_labels_available_to_model=False,
        derived_from_holdout_labels=False,
    )


def assess_sequence_context_target(
    target: Stage8SequenceContextTarget,
) -> Stage8SequenceContextTargetAssessment:
    """Validate a proposed target against the approved fail-closed boundary."""

    if not isinstance(target, Stage8SequenceContextTarget):
        raise TypeError("target must be Stage8SequenceContextTarget")

    mismatch: list[str] = []
    if target.target_id != STAGE8_SEQUENCE_CONTEXT_TARGET_ID:
        mismatch.append("unexpected_target_id")
    if target.objective_id != STAGE8_SEQUENCE_CONTEXT_OBJECTIVE_ID:
        mismatch.append("unexpected_objective_id")
    if not target.uses_current_frame:
        mismatch.append("current_frame_required")
    if not target.uses_previous_frames or target.previous_frame_limit <= 0:
        mismatch.append("bounded_previous_context_required")
    if mismatch:
        return Stage8SequenceContextTargetAssessment(
            Stage8SequenceContextTargetStatus.BLOCKED_TARGET_MISMATCH,
            tuple(sorted(mismatch)),
            False,
        )

    if target.uses_future_frames or target.previous_frame_limit > _MAX_PREVIOUS_FRAMES:
        return Stage8SequenceContextTargetAssessment(
            Stage8SequenceContextTargetStatus.BLOCKED_NONCAUSAL_CONTEXT,
            ("future_or_unbounded_context_forbidden",),
            False,
        )

    authority: list[str] = []
    if not target.requires_source_state_ambiguous:
        authority.append("source_must_already_be_ambiguous")
    if not target.candidate_set_immutable:
        authority.append("candidate_set_must_be_immutable")
    if target.may_generate_candidates:
        authority.append("candidate_generation_forbidden")
    if target.may_change_authoritative_state:
        authority.append("authoritative_state_change_forbidden")
    if target.may_suppress_abstain_or_no_match:
        authority.append("abstain_or_no_match_suppression_forbidden")
    if authority:
        return Stage8SequenceContextTargetAssessment(
            Stage8SequenceContextTargetStatus.BLOCKED_AUTHORITY_RISK,
            tuple(sorted(authority)),
            False,
        )

    leakage: list[str] = []
    if target.teacher_gold_labels_available_to_model:
        leakage.append("teacher_gold_labels_forbidden")
    if target.holdout_labels_available_to_model:
        leakage.append("holdout_labels_forbidden")
    if target.derived_from_holdout_labels:
        leakage.append("holdout_derived_target_forbidden")
    if leakage:
        return Stage8SequenceContextTargetAssessment(
            Stage8SequenceContextTargetStatus.BLOCKED_LABEL_LEAKAGE,
            tuple(sorted(leakage)),
            False,
        )

    return Stage8SequenceContextTargetAssessment(
        Stage8SequenceContextTargetStatus.TARGET_DESIGN_ELIGIBLE,
        (),
        True,
    )
