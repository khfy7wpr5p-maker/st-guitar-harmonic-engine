"""Frozen Stage 8 sequence/context sampling policy v0.1.

This metadata-only contract sits between ambiguity mining and human review. It
freezes review-pool buffer targets and diversity caps without selecting musical
answers, authorizing model training, or granting production authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re

from .stage8_sequence_context_sample_plan import (
    canonical_stage8_sequence_context_sample_plan,
)


STAGE8_SEQUENCE_CONTEXT_SAMPLING_POLICY_VERSION = "0.1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class Stage8SamplingSourcePolicy:
    source_id: str
    final_case_target: int
    review_pool_target: int
    max_cases_per_source_item: int
    max_cases_per_source_group: int
    max_cases_per_candidate_set: int
    min_distinct_source_groups: int
    max_cases_per_composer: int | None = None
    min_distinct_composers: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id:
            raise TypeError("source_id must be a non-empty string")
        for name in (
            "final_case_target",
            "review_pool_target",
            "max_cases_per_source_item",
            "max_cases_per_source_group",
            "max_cases_per_candidate_set",
            "min_distinct_source_groups",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive int")
        if self.review_pool_target < 2 * self.final_case_target:
            raise ValueError("review_pool_target must provide at least a 2x human-review buffer")
        if self.max_cases_per_source_item > self.max_cases_per_source_group:
            raise ValueError("source-item cap cannot exceed source-group cap")
        if self.min_distinct_source_groups * self.max_cases_per_source_group < self.final_case_target:
            raise ValueError("source-group diversity floor cannot supply the final target")
        required_groups = math.ceil(self.final_case_target / self.max_cases_per_source_group)
        if self.min_distinct_source_groups < required_groups:
            raise ValueError("min_distinct_source_groups is weaker than the frozen group cap")

        composer_values = (self.max_cases_per_composer, self.min_distinct_composers)
        if (composer_values[0] is None) != (composer_values[1] is None):
            raise ValueError("composer cap and diversity floor must be configured together")
        if self.max_cases_per_composer is not None:
            if isinstance(self.max_cases_per_composer, bool) or not isinstance(self.max_cases_per_composer, int):
                raise ValueError("max_cases_per_composer must be a positive int or None")
            if self.max_cases_per_composer <= 0:
                raise ValueError("max_cases_per_composer must be a positive int or None")
            if isinstance(self.min_distinct_composers, bool) or not isinstance(self.min_distinct_composers, int):
                raise ValueError("min_distinct_composers must be a positive int or None")
            if self.min_distinct_composers <= 0:
                raise ValueError("min_distinct_composers must be a positive int or None")
            required_composers = math.ceil(self.final_case_target / self.max_cases_per_composer)
            if self.min_distinct_composers < required_composers:
                raise ValueError("min_distinct_composers is weaker than the frozen composer cap")


@dataclass(frozen=True, slots=True)
class Stage8OpenScorePilotEvidence:
    source_id: str
    source_item_count: int
    harmonic_frame_count: int
    ambiguous_candidate_count: int
    manifest_sha256: str
    candidate_pool_sha256: str
    output_sha256: str
    pipeline_evidence_only: bool = True
    auto_inclusion_in_final_corpus: bool = False
    model_training_authorized: bool = False
    production_authority_granted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id:
            raise TypeError("source_id must be a non-empty string")
        for name in ("source_item_count", "harmonic_frame_count", "ambiguous_candidate_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive int")
        if self.ambiguous_candidate_count > self.harmonic_frame_count:
            raise ValueError("ambiguous candidates cannot exceed harmonic frames")
        for name in ("manifest_sha256", "candidate_pool_sha256", "output_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
                raise ValueError(f"{name} must be lowercase SHA-256")
        if not self.pipeline_evidence_only:
            raise ValueError("pilot artifacts are pipeline evidence only")
        if self.auto_inclusion_in_final_corpus:
            raise ValueError("pilot artifacts cannot be auto-included in the final corpus")
        if self.model_training_authorized or self.production_authority_granted:
            raise ValueError("pilot evidence cannot authorize training or production")


@dataclass(frozen=True, slots=True)
class Stage8SequenceContextSamplingPolicy:
    sources: tuple[Stage8SamplingSourcePolicy, ...]
    pilot_evidence: tuple[Stage8OpenScorePilotEvidence, ...]
    deterministic_selection_required: bool
    group_disjoint_partitions_required: bool
    holdout_selected_without_model_feedback: bool
    human_verification_required: bool
    pilot_auto_inclusion_forbidden: bool
    model_training_authorized: bool = False
    production_authority_granted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.sources, tuple) or not self.sources or any(
            not isinstance(item, Stage8SamplingSourcePolicy) for item in self.sources
        ):
            raise TypeError("sources must contain Stage8SamplingSourcePolicy values")
        if len({item.source_id for item in self.sources}) != len(self.sources):
            raise ValueError("sampling source_id values must be unique")
        if not isinstance(self.pilot_evidence, tuple) or any(
            not isinstance(item, Stage8OpenScorePilotEvidence) for item in self.pilot_evidence
        ):
            raise TypeError("pilot_evidence must contain Stage8OpenScorePilotEvidence values")
        if len({item.source_id for item in self.pilot_evidence}) != len(self.pilot_evidence):
            raise ValueError("pilot evidence source_id values must be unique")
        for name in (
            "deterministic_selection_required",
            "group_disjoint_partitions_required",
            "holdout_selected_without_model_feedback",
            "human_verification_required",
            "pilot_auto_inclusion_forbidden",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")
        if not all(
            (
                self.deterministic_selection_required,
                self.group_disjoint_partitions_required,
                self.holdout_selected_without_model_feedback,
                self.human_verification_required,
                self.pilot_auto_inclusion_forbidden,
            )
        ):
            raise ValueError("v0.1 requires deterministic, leakage-safe, human-verified sampling")
        if self.model_training_authorized or self.production_authority_granted:
            raise ValueError("sampling policy cannot authorize training or production")

        plan = canonical_stage8_sequence_context_sample_plan()
        expected = {
            item.source_id: item.total_cases
            for item in plan.sources
            if item.total_cases > 0
        }
        observed = {item.source_id: item.final_case_target for item in self.sources}
        if observed != expected:
            raise ValueError("sampling final targets must match the frozen 1,200-case sample plan")
        pilot_sources = {item.source_id for item in self.pilot_evidence}
        if not pilot_sources.issubset(expected):
            raise ValueError("pilot evidence references a source outside the frozen sample plan")

    @property
    def final_case_target(self) -> int:
        return sum(item.final_case_target for item in self.sources)

    @property
    def review_pool_target(self) -> int:
        return sum(item.review_pool_target for item in self.sources)


def canonical_stage8_sequence_context_sampling_policy() -> Stage8SequenceContextSamplingPolicy:
    """Return the frozen v0.1 sampling policy and aggregate pilot fingerprints."""

    return Stage8SequenceContextSamplingPolicy(
        sources=(
            Stage8SamplingSourcePolicy(
                source_id="openscore-string-quartets",
                final_case_target=600,
                review_pool_target=1200,
                max_cases_per_source_item=20,
                max_cases_per_source_group=20,
                max_cases_per_candidate_set=90,
                min_distinct_source_groups=30,
                max_cases_per_composer=100,
                min_distinct_composers=6,
            ),
            Stage8SamplingSourcePolicy(
                source_id="openscore-lieder",
                final_case_target=300,
                review_pool_target=600,
                max_cases_per_source_item=10,
                max_cases_per_source_group=20,
                max_cases_per_candidate_set=45,
                min_distinct_source_groups=15,
                max_cases_per_composer=45,
                min_distinct_composers=7,
            ),
            Stage8SamplingSourcePolicy(
                source_id="owned-synthetic-guitar-context",
                final_case_target=300,
                review_pool_target=600,
                max_cases_per_source_item=10,
                max_cases_per_source_group=20,
                max_cases_per_candidate_set=45,
                min_distinct_source_groups=15,
            ),
        ),
        pilot_evidence=(
            Stage8OpenScorePilotEvidence(
                source_id="openscore-string-quartets",
                source_item_count=10,
                harmonic_frame_count=52209,
                ambiguous_candidate_count=1755,
                manifest_sha256="adb53f4f1749af2b13092bacba4a7c31c547e4c41c64d3d1b4fa496ac141ec5c",
                candidate_pool_sha256="7f1981f3f232cb0dce70a913d7b38829451d20dcaaef86c3c6c7b85c09243dab",
                output_sha256="12d6af3b3796c932295bfc61482e2d6d00f7c38c199b21dd2c0f1be78bfd9a46",
            ),
            Stage8OpenScorePilotEvidence(
                source_id="openscore-lieder",
                source_item_count=10,
                harmonic_frame_count=4047,
                ambiguous_candidate_count=235,
                manifest_sha256="9f3697141977251729cade9cc9faa0c4150cd78dee7c757367a7e26f71943965",
                candidate_pool_sha256="0f44c508250f9e4300252266a7f7858be0f91d3c7582faf6fac7eea66cd47f49",
                output_sha256="b52fff82e8082046c831cd67bb9bbc2e565372f6279b9129001aea761882952e",
            ),
        ),
        deterministic_selection_required=True,
        group_disjoint_partitions_required=True,
        holdout_selected_without_model_feedback=True,
        human_verification_required=True,
        pilot_auto_inclusion_forbidden=True,
    )
