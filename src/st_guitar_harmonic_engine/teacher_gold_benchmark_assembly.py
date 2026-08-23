"""Fail-closed assembly of frozen Teacher-Gold calibration and holdout truth.

This module combines already validated reference cases into one benchmark manifest.
It preserves all human reference truth while allowing only fully engine-representable
cases into ``TeacherGoldBenchmark``. A partially representable ambiguous case is
never partially scored. No resolver, runtime, model, or training authority is added.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .calibration import (
    BenchmarkSplit,
    CalibrationReadiness,
    TeacherGoldBenchmark,
    TeacherGoldCase,
    calibration_readiness,
)
from .teacher_gold_adapter import FROZEN_CALIBRATION_V0_1_CASE_COUNT
from .teacher_gold_holdout import HOLDOUT_V0_1_CASE_COUNT, HOLDOUT_V0_1_CASE_IDS
from .teacher_gold_reference import TeacherGoldReferenceCase


CALIBRATION_V0_1_CASE_IDS: tuple[str, ...] = tuple(
    f"TG-{index:04d}" for index in range(1, FROZEN_CALIBRATION_V0_1_CASE_COUNT + 1)
)
TEACHER_GOLD_V0_1_REFERENCE_CASE_COUNT = (
    FROZEN_CALIBRATION_V0_1_CASE_COUNT + HOLDOUT_V0_1_CASE_COUNT
)


@dataclass(frozen=True, slots=True)
class TeacherGoldBenchmarkAssembly:
    """Frozen reference truth plus the safely executable benchmark subset."""

    reference_cases: tuple[TeacherGoldReferenceCase, ...]
    benchmark: TeacherGoldBenchmark
    reference_only_case_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.reference_cases, tuple) or any(
            not isinstance(item, TeacherGoldReferenceCase) for item in self.reference_cases
        ):
            raise TypeError("reference_cases must contain TeacherGoldReferenceCase values")
        if not isinstance(self.benchmark, TeacherGoldBenchmark):
            raise TypeError("benchmark must be a TeacherGoldBenchmark")
        if not isinstance(self.reference_only_case_ids, tuple) or any(
            not isinstance(item, str) for item in self.reference_only_case_ids
        ):
            raise TypeError("reference_only_case_ids must contain strings")

        reference_ids = tuple(item.case_id for item in self.reference_cases)
        if len(set(reference_ids)) != len(reference_ids):
            raise ValueError("reference case ids must be unique")
        if tuple(sorted(reference_ids)) != reference_ids:
            raise ValueError("reference cases must use canonical case_id order")
        if tuple(sorted(set(self.reference_only_case_ids))) != self.reference_only_case_ids:
            raise ValueError("reference_only_case_ids must be unique canonical order")
        if not set(self.reference_only_case_ids).issubset(reference_ids):
            raise ValueError("reference_only_case_ids must belong to reference_cases")

        executable_ids = tuple(item.case_id for item in self.benchmark.cases)
        if set(executable_ids) & set(self.reference_only_case_ids):
            raise ValueError("reference-only cases cannot enter executable benchmark")
        if set(executable_ids) | set(self.reference_only_case_ids) != set(reference_ids):
            raise ValueError("every reference case must be executable or explicitly reference-only")

    @property
    def reference_case_count(self) -> int:
        return len(self.reference_cases)

    @property
    def executable_case_count(self) -> int:
        return len(self.benchmark.cases)

    @property
    def reference_only_case_count(self) -> int:
        return len(self.reference_only_case_ids)

    @property
    def calibration_executable_count(self) -> int:
        return len(self.benchmark.cases_for(BenchmarkSplit.CALIBRATION))

    @property
    def holdout_executable_count(self) -> int:
        return len(self.benchmark.cases_for(BenchmarkSplit.HOLDOUT))

    @property
    def readiness(self) -> CalibrationReadiness:
        return calibration_readiness(self.benchmark)

    @property
    def is_full_reference_partition_ready(self) -> bool:
        return (
            self.reference_case_count == TEACHER_GOLD_V0_1_REFERENCE_CASE_COUNT
            and sum(
                item.split is BenchmarkSplit.CALIBRATION for item in self.reference_cases
            )
            == FROZEN_CALIBRATION_V0_1_CASE_COUNT
            and sum(item.split is BenchmarkSplit.HOLDOUT for item in self.reference_cases)
            == HOLDOUT_V0_1_CASE_COUNT
        )

    @property
    def is_fully_engine_executable(self) -> bool:
        return self.reference_only_case_count == 0


def _validate_partition(
    cases: Sequence[TeacherGoldReferenceCase],
    *,
    split: BenchmarkSplit,
    expected_ids: tuple[str, ...],
) -> tuple[TeacherGoldReferenceCase, ...]:
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes, bytearray)):
        raise TypeError("cases must be a sequence of TeacherGoldReferenceCase values")
    normalized = tuple(cases)
    if any(not isinstance(item, TeacherGoldReferenceCase) for item in normalized):
        raise TypeError("cases must contain TeacherGoldReferenceCase values")
    if len(normalized) != len(expected_ids):
        raise ValueError(
            f"{split.value} v0.1 requires exactly {len(expected_ids)} reference cases"
        )
    if any(item.split is not split for item in normalized):
        raise ValueError(f"all {split.value} cases must carry the {split.value} split")
    actual_ids = tuple(item.case_id for item in normalized)
    if actual_ids != expected_ids:
        raise ValueError(f"{split.value} v0.1 case ids must match the frozen namespace")
    return normalized


def _to_engine_case(reference: TeacherGoldReferenceCase) -> TeacherGoldCase | None:
    identities = tuple(candidate.engine_identity for candidate in reference.expected_candidates)
    if any(identity is None for identity in identities):
        return None

    engine_identities = tuple(identity for identity in identities if identity is not None)
    # Distinct human alternatives that collapse onto one engine identity cannot be
    # scored faithfully and therefore remain reference-only as a whole case.
    if len(set(engine_identities)) != len(engine_identities):
        return None

    return TeacherGoldCase(
        case_id=reference.case_id,
        split=reference.split,
        expected_state=reference.expected_state,
        acceptable_identities=tuple(sorted(engine_identities)),
    )


def assemble_frozen_teacher_gold_benchmark_v0_1(
    calibration_cases: Sequence[TeacherGoldReferenceCase],
    holdout_cases: Sequence[TeacherGoldReferenceCase],
) -> TeacherGoldBenchmarkAssembly:
    """Assemble exact frozen v0.1 partitions without partial-reference scoring.

    ``BENCHMARK_READY`` means that the executable benchmark contains both frozen
    partitions. It does not mean every human label is representable by the current
    engine vocabulary, and it grants no model-training or production authority.
    """

    calibration = _validate_partition(
        calibration_cases,
        split=BenchmarkSplit.CALIBRATION,
        expected_ids=CALIBRATION_V0_1_CASE_IDS,
    )
    holdout = _validate_partition(
        holdout_cases,
        split=BenchmarkSplit.HOLDOUT,
        expected_ids=HOLDOUT_V0_1_CASE_IDS,
    )
    reference_cases = calibration + holdout

    executable: list[TeacherGoldCase] = []
    reference_only_ids: list[str] = []
    for reference in reference_cases:
        engine_case = _to_engine_case(reference)
        if engine_case is None:
            reference_only_ids.append(reference.case_id)
        else:
            executable.append(engine_case)

    benchmark = TeacherGoldBenchmark(tuple(executable))
    assembly = TeacherGoldBenchmarkAssembly(
        reference_cases=reference_cases,
        benchmark=benchmark,
        reference_only_case_ids=tuple(reference_only_ids),
    )
    if not assembly.is_full_reference_partition_ready:
        raise ValueError("frozen Teacher-Gold reference partitions are incomplete")
    return assembly
