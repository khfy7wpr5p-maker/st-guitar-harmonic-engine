"""Frozen Stage 8 sequence/context sample and source plan v0.1.

This metadata-only contract fixes the initial research-corpus size and source mix.
It does not ingest data, adjudicate music, authorize model training, or grant
production authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


STAGE8_SEQUENCE_CONTEXT_SAMPLE_PLAN_VERSION = "0.1"


class Stage8SourceClass(str, Enum):
    CC0 = "cc0"
    OWNED_SYNTHETIC = "owned_synthetic"
    NONCOMMERCIAL_REFERENCE_ONLY = "noncommercial_reference_only"
    MIXED_OR_PER_ITEM_REVIEW = "mixed_or_per_item_review"


@dataclass(frozen=True, slots=True)
class Stage8SampleSourcePlan:
    source_id: str
    source_class: Stage8SourceClass
    train_cases: int
    validation_cases: int
    holdout_cases: int
    training_eligible: bool

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id:
            raise TypeError("source_id must be a non-empty string")
        if not isinstance(self.source_class, Stage8SourceClass):
            raise TypeError("source_class must be Stage8SourceClass")
        for name in ("train_cases", "validation_cases", "holdout_cases"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative int")
        if not isinstance(self.training_eligible, bool):
            raise TypeError("training_eligible must be bool")
        if self.training_eligible and self.source_class not in {
            Stage8SourceClass.CC0,
            Stage8SourceClass.OWNED_SYNTHETIC,
        }:
            raise ValueError("only CC0 or owned synthetic sources may be training eligible")
        if not self.training_eligible and any(
            (self.train_cases, self.validation_cases, self.holdout_cases)
        ):
            raise ValueError("non-training sources cannot receive v0.1 case allocations")

    @property
    def total_cases(self) -> int:
        return self.train_cases + self.validation_cases + self.holdout_cases


@dataclass(frozen=True, slots=True)
class Stage8SequenceContextSamplePlan:
    sources: tuple[Stage8SampleSourcePlan, ...]
    target_train_cases: int
    target_validation_cases: int
    target_holdout_cases: int
    group_disjoint_splits_required: bool
    holdout_frozen_before_model_selection: bool
    human_verification_required: bool
    model_training_authorized: bool = False
    production_authority_granted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.sources, tuple) or any(
            not isinstance(item, Stage8SampleSourcePlan) for item in self.sources
        ):
            raise TypeError("sources must contain Stage8SampleSourcePlan values")
        if not self.sources:
            raise ValueError("sample plan requires sources")
        if len({item.source_id for item in self.sources}) != len(self.sources):
            raise ValueError("source_id values must be unique")
        for name in (
            "target_train_cases",
            "target_validation_cases",
            "target_holdout_cases",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive int")
        for name in (
            "group_disjoint_splits_required",
            "holdout_frozen_before_model_selection",
            "human_verification_required",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")
        if not all(
            (
                self.group_disjoint_splits_required,
                self.holdout_frozen_before_model_selection,
                self.human_verification_required,
            )
        ):
            raise ValueError("v0.1 requires group-disjoint splits, frozen holdout, and human verification")
        if self.model_training_authorized or self.production_authority_granted:
            raise ValueError("sample planning cannot authorize training or production")
        if sum(item.train_cases for item in self.sources) != self.target_train_cases:
            raise ValueError("source train allocations must equal target_train_cases")
        if sum(item.validation_cases for item in self.sources) != self.target_validation_cases:
            raise ValueError("source validation allocations must equal target_validation_cases")
        if sum(item.holdout_cases for item in self.sources) != self.target_holdout_cases:
            raise ValueError("source holdout allocations must equal target_holdout_cases")

    @property
    def total_cases(self) -> int:
        return self.target_train_cases + self.target_validation_cases + self.target_holdout_cases


def canonical_stage8_sequence_context_sample_plan() -> Stage8SequenceContextSamplePlan:
    """Return the frozen v0.1 sample/source plan."""

    return Stage8SequenceContextSamplePlan(
        sources=(
            Stage8SampleSourcePlan(
                source_id="openscore-string-quartets",
                source_class=Stage8SourceClass.CC0,
                train_cases=400,
                validation_cases=100,
                holdout_cases=100,
                training_eligible=True,
            ),
            Stage8SampleSourcePlan(
                source_id="openscore-lieder",
                source_class=Stage8SourceClass.CC0,
                train_cases=200,
                validation_cases=50,
                holdout_cases=50,
                training_eligible=True,
            ),
            Stage8SampleSourcePlan(
                source_id="owned-synthetic-guitar-context",
                source_class=Stage8SourceClass.OWNED_SYNTHETIC,
                train_cases=200,
                validation_cases=50,
                holdout_cases=50,
                training_eligible=True,
            ),
            Stage8SampleSourcePlan(
                source_id="dcml-noncommercial-reference",
                source_class=Stage8SourceClass.NONCOMMERCIAL_REFERENCE_ONLY,
                train_cases=0,
                validation_cases=0,
                holdout_cases=0,
                training_eligible=False,
            ),
            Stage8SampleSourcePlan(
                source_id="maestro-asap-noncommercial-reference",
                source_class=Stage8SourceClass.NONCOMMERCIAL_REFERENCE_ONLY,
                train_cases=0,
                validation_cases=0,
                holdout_cases=0,
                training_eligible=False,
            ),
            Stage8SampleSourcePlan(
                source_id="mutopia-per-item-review",
                source_class=Stage8SourceClass.MIXED_OR_PER_ITEM_REVIEW,
                train_cases=0,
                validation_cases=0,
                holdout_cases=0,
                training_eligible=False,
            ),
        ),
        target_train_cases=800,
        target_validation_cases=200,
        target_holdout_cases=200,
        group_disjoint_splits_required=True,
        holdout_frozen_before_model_selection=True,
        human_verification_required=True,
    )
