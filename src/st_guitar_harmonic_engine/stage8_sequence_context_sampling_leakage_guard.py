"""Fail-closed pre-assembly leakage guard for Stage 8 SC sampling v0.1.

The guard operates on metadata-only candidate assignments before human labels are
assembled into TRAIN, VALIDATION, or untouched SC-HOLDOUT cases. It prevents
source-group, score, and exact-frame leakage and can optionally require the full
frozen source/split allocation. It never authorizes model selection, training,
or production authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath
import re

from .stage8_sequence_context_sample_plan import (
    canonical_stage8_sequence_context_sample_plan,
)


STAGE8_SEQUENCE_CONTEXT_SAMPLING_LEAKAGE_GUARD_VERSION = "0.1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{2,127}$")


class Stage8SamplingPartition(str, Enum):
    TRAIN = "train"
    VALIDATION = "validation"
    HOLDOUT = "holdout"


class Stage8SamplingLeakageStatus(str, Enum):
    BLOCKED_EMPTY = "blocked_empty"
    BLOCKED_DUPLICATE = "blocked_duplicate"
    BLOCKED_CROSS_SPLIT = "blocked_cross_split"
    BLOCKED_SOURCE = "blocked_source"
    BLOCKED_ALLOCATION = "blocked_allocation"
    LEAKAGE_GUARD_PASS = "leakage_guard_pass"


@dataclass(frozen=True, slots=True)
class Stage8SamplingLeakageRecord:
    candidate_uid: str
    source_id: str
    source_group_id: str
    score_relative_path: str
    source_score_sha256: str
    current_frame_sha256: str
    candidate_set_sha256: str
    partition: Stage8SamplingPartition

    def __post_init__(self) -> None:
        for name in (
            "candidate_uid",
            "source_score_sha256",
            "current_frame_sha256",
            "candidate_set_sha256",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
                raise ValueError(f"{name} must be lowercase SHA-256")
        for name in ("source_id", "source_group_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or _TOKEN_RE.fullmatch(value) is None:
                raise ValueError(f"{name} must be a canonical token")
        if not isinstance(self.score_relative_path, str) or not self.score_relative_path or "\x00" in self.score_relative_path:
            raise ValueError("score_relative_path must be a non-empty NUL-free string")
        path = PurePosixPath(self.score_relative_path)
        if path.is_absolute() or "." in path.parts or ".." in path.parts or path.as_posix() != self.score_relative_path:
            raise ValueError("score_relative_path must be canonical safe POSIX relative form")
        if not isinstance(self.partition, Stage8SamplingPartition):
            raise TypeError("partition must be Stage8SamplingPartition")


@dataclass(frozen=True, slots=True)
class Stage8SamplingLeakageAssessment:
    status: Stage8SamplingLeakageStatus
    reasons: tuple[str, ...]
    record_count: int
    train_count: int
    validation_count: int
    holdout_count: int
    complete_allocation_required: bool
    model_selection_authorized: bool = False
    model_training_authorized: bool = False
    production_authority_granted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.status, Stage8SamplingLeakageStatus):
            raise TypeError("status must be Stage8SamplingLeakageStatus")
        if not isinstance(self.reasons, tuple) or any(
            not isinstance(item, str) or not item for item in self.reasons
        ):
            raise TypeError("reasons must contain non-empty strings")
        if tuple(sorted(set(self.reasons))) != self.reasons:
            raise ValueError("reasons must be unique canonical order")
        for name in ("record_count", "train_count", "validation_count", "holdout_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative int")
        if self.train_count + self.validation_count + self.holdout_count != self.record_count:
            raise ValueError("partition counts must sum to record_count")
        if not isinstance(self.complete_allocation_required, bool):
            raise TypeError("complete_allocation_required must be bool")
        if self.model_selection_authorized or self.model_training_authorized or self.production_authority_granted:
            raise ValueError("leakage assessment cannot authorize selection, training, or production")
        passed = self.status is Stage8SamplingLeakageStatus.LEAKAGE_GUARD_PASS
        if passed and self.reasons:
            raise ValueError("passing assessment cannot contain blocking reasons")
        if not passed and not self.reasons:
            raise ValueError("blocked assessment requires reasons")


def _assessment(
    status: Stage8SamplingLeakageStatus,
    reasons: tuple[str, ...],
    records: tuple[Stage8SamplingLeakageRecord, ...],
    *,
    require_complete_allocation: bool,
) -> Stage8SamplingLeakageAssessment:
    return Stage8SamplingLeakageAssessment(
        status=status,
        reasons=tuple(sorted(set(reasons))),
        record_count=len(records),
        train_count=sum(item.partition is Stage8SamplingPartition.TRAIN for item in records),
        validation_count=sum(item.partition is Stage8SamplingPartition.VALIDATION for item in records),
        holdout_count=sum(item.partition is Stage8SamplingPartition.HOLDOUT for item in records),
        complete_allocation_required=require_complete_allocation,
    )


def _cross_split_reasons(
    records: tuple[Stage8SamplingLeakageRecord, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    dimensions = (
        ("source_group", lambda item: item.source_group_id),
        ("score_path", lambda item: f"{item.source_id}:{item.score_relative_path}"),
        ("score_sha", lambda item: item.source_score_sha256),
    )
    for label, getter in dimensions:
        partitions_by_value: dict[str, set[Stage8SamplingPartition]] = {}
        for item in records:
            partitions_by_value.setdefault(getter(item), set()).add(item.partition)
        for value, partitions in sorted(partitions_by_value.items()):
            if len(partitions) > 1:
                reasons.append(f"{label}:{value}:crosses_partitions")
    return tuple(reasons)


def _allocation_reasons(
    records: tuple[Stage8SamplingLeakageRecord, ...],
) -> tuple[str, ...]:
    plan = canonical_stage8_sequence_context_sample_plan()
    expected: dict[tuple[str, Stage8SamplingPartition], int] = {}
    approved_sources: set[str] = set()
    for item in plan.sources:
        if item.total_cases <= 0:
            continue
        approved_sources.add(item.source_id)
        expected[(item.source_id, Stage8SamplingPartition.TRAIN)] = item.train_cases
        expected[(item.source_id, Stage8SamplingPartition.VALIDATION)] = item.validation_cases
        expected[(item.source_id, Stage8SamplingPartition.HOLDOUT)] = item.holdout_cases

    observed: dict[tuple[str, Stage8SamplingPartition], int] = {}
    for item in records:
        key = (item.source_id, item.partition)
        observed[key] = observed.get(key, 0) + 1

    reasons: list[str] = []
    unknown = sorted({item.source_id for item in records} - approved_sources)
    reasons.extend(f"{source_id}:unapproved_sampling_source" for source_id in unknown)
    for key, expected_count in sorted(expected.items(), key=lambda pair: (pair[0][0], pair[0][1].value)):
        observed_count = observed.get(key, 0)
        if observed_count != expected_count:
            source_id, partition = key
            reasons.append(
                f"{source_id}:{partition.value}:expected_{expected_count}:observed_{observed_count}"
            )
    extra = sorted(set(observed) - set(expected), key=lambda item: (item[0], item[1].value))
    reasons.extend(f"{source_id}:{partition.value}:unexpected_allocation" for source_id, partition in extra)
    return tuple(reasons)


def assess_sampling_leakage(
    records: tuple[Stage8SamplingLeakageRecord, ...],
    *,
    require_complete_allocation: bool = False,
) -> Stage8SamplingLeakageAssessment:
    """Assess pre-label sampling assignments for exact and split-level leakage."""

    if not isinstance(records, tuple) or any(
        not isinstance(item, Stage8SamplingLeakageRecord) for item in records
    ):
        raise TypeError("records must contain Stage8SamplingLeakageRecord values")
    if not isinstance(require_complete_allocation, bool):
        raise TypeError("require_complete_allocation must be bool")
    if not records:
        return _assessment(
            Stage8SamplingLeakageStatus.BLOCKED_EMPTY,
            ("sampling_assignment_is_empty",),
            records,
            require_complete_allocation=require_complete_allocation,
        )

    plan = canonical_stage8_sequence_context_sample_plan()
    approved_sources = {item.source_id for item in plan.sources if item.total_cases > 0}
    unknown_sources = tuple(sorted({item.source_id for item in records} - approved_sources))
    if unknown_sources:
        return _assessment(
            Stage8SamplingLeakageStatus.BLOCKED_SOURCE,
            tuple(f"{item}:unapproved_sampling_source" for item in unknown_sources),
            records,
            require_complete_allocation=require_complete_allocation,
        )

    candidate_uids = [item.candidate_uid for item in records]
    frame_hashes = [item.current_frame_sha256 for item in records]
    if len(set(candidate_uids)) != len(candidate_uids) or len(set(frame_hashes)) != len(frame_hashes):
        reasons: list[str] = []
        if len(set(candidate_uids)) != len(candidate_uids):
            reasons.append("duplicate_candidate_uid")
        if len(set(frame_hashes)) != len(frame_hashes):
            reasons.append("duplicate_current_frame_sha256")
        return _assessment(
            Stage8SamplingLeakageStatus.BLOCKED_DUPLICATE,
            tuple(reasons),
            records,
            require_complete_allocation=require_complete_allocation,
        )

    path_to_sha: dict[tuple[str, str], set[str]] = {}
    sha_to_paths: dict[str, set[tuple[str, str]]] = {}
    for item in records:
        path_key = (item.source_id, item.score_relative_path)
        path_to_sha.setdefault(path_key, set()).add(item.source_score_sha256)
        sha_to_paths.setdefault(item.source_score_sha256, set()).add(path_key)
    inconsistent = [
        f"score_path:{source_id}:{path}:multiple_source_hashes"
        for (source_id, path), hashes in sorted(path_to_sha.items())
        if len(hashes) > 1
    ]
    aliased = [
        f"score_sha:{digest}:multiple_score_paths"
        for digest, paths in sorted(sha_to_paths.items())
        if len(paths) > 1
    ]
    if inconsistent or aliased:
        return _assessment(
            Stage8SamplingLeakageStatus.BLOCKED_DUPLICATE,
            tuple(inconsistent + aliased),
            records,
            require_complete_allocation=require_complete_allocation,
        )

    crossed = _cross_split_reasons(records)
    if crossed:
        return _assessment(
            Stage8SamplingLeakageStatus.BLOCKED_CROSS_SPLIT,
            crossed,
            records,
            require_complete_allocation=require_complete_allocation,
        )

    if require_complete_allocation:
        allocation = _allocation_reasons(records)
        if allocation:
            return _assessment(
                Stage8SamplingLeakageStatus.BLOCKED_ALLOCATION,
                allocation,
                records,
                require_complete_allocation=require_complete_allocation,
            )

    return _assessment(
        Stage8SamplingLeakageStatus.LEAKAGE_GUARD_PASS,
        (),
        records,
        require_complete_allocation=require_complete_allocation,
    )
