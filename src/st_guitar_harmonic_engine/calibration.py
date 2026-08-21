"""Teacher-gold calibration infrastructure for Stage 4-G.

This module defines benchmark contracts and leakage-resistant partitions only. It
never converts categorical confidence into a probability and never claims that
confidence is calibrated without external teacher-gold benchmark evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .abstention import FinalDecisionState
from .resolver import HarmonicIdentity


CALIBRATION_SEMANTICS = "requires_teacher_gold_benchmark_no_probability_claim"


class BenchmarkSplit(str, Enum):
    CALIBRATION = "calibration"
    HOLDOUT = "holdout"


class CalibrationReadiness(str, Enum):
    UNCALIBRATED = "uncalibrated"
    INCOMPLETE_BENCHMARK = "incomplete_benchmark"
    BENCHMARK_READY = "benchmark_ready"


@dataclass(frozen=True, slots=True)
class TeacherGoldCase:
    case_id: str
    split: BenchmarkSplit
    expected_state: FinalDecisionState
    acceptable_identities: tuple[HarmonicIdentity, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str):
            raise TypeError("case_id must be a str")
        if not self.case_id or self.case_id != self.case_id.strip():
            raise ValueError("case_id must be a non-empty canonical token")
        if not isinstance(self.split, BenchmarkSplit):
            raise TypeError("split must be a BenchmarkSplit")
        if not isinstance(self.expected_state, FinalDecisionState):
            raise TypeError("expected_state must be a FinalDecisionState")
        if not isinstance(self.acceptable_identities, tuple) or any(
            not isinstance(item, HarmonicIdentity) for item in self.acceptable_identities
        ):
            raise TypeError("acceptable_identities must contain HarmonicIdentity values")
        if len(set(self.acceptable_identities)) != len(self.acceptable_identities):
            raise ValueError("acceptable identities must be unique")
        if tuple(sorted(self.acceptable_identities)) != self.acceptable_identities:
            raise ValueError("acceptable identities must use canonical order")

        count = len(self.acceptable_identities)
        if self.expected_state is FinalDecisionState.RESOLVED and count != 1:
            raise ValueError("resolved teacher-gold case requires exactly one identity")
        if self.expected_state is FinalDecisionState.AMBIGUOUS and count < 2:
            raise ValueError("ambiguous teacher-gold case requires at least two identities")
        if self.expected_state in {FinalDecisionState.ABSTAIN, FinalDecisionState.NO_MATCH} and count:
            raise ValueError("abstain/no-match teacher-gold cases cannot claim an identity")


@dataclass(frozen=True, slots=True)
class TeacherGoldBenchmark:
    cases: tuple[TeacherGoldCase, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.cases, tuple) or any(
            not isinstance(item, TeacherGoldCase) for item in self.cases
        ):
            raise TypeError("cases must contain TeacherGoldCase values")
        ids = [item.case_id for item in self.cases]
        if len(set(ids)) != len(ids):
            raise ValueError("teacher-gold case ids must be unique")
        if tuple(sorted(self.cases, key=lambda item: item.case_id)) != self.cases:
            raise ValueError("teacher-gold cases must use canonical case_id order")

    def cases_for(self, split: BenchmarkSplit) -> tuple[TeacherGoldCase, ...]:
        if not isinstance(split, BenchmarkSplit):
            raise TypeError("split must be a BenchmarkSplit")
        return tuple(item for item in self.cases if item.split is split)


def calibration_readiness(benchmark: TeacherGoldBenchmark) -> CalibrationReadiness:
    """Report benchmark readiness without claiming empirical calibration."""

    if not isinstance(benchmark, TeacherGoldBenchmark):
        raise TypeError("benchmark must be a TeacherGoldBenchmark")
    if not benchmark.cases:
        return CalibrationReadiness.UNCALIBRATED
    has_calibration = bool(benchmark.cases_for(BenchmarkSplit.CALIBRATION))
    has_holdout = bool(benchmark.cases_for(BenchmarkSplit.HOLDOUT))
    if has_calibration and has_holdout:
        return CalibrationReadiness.BENCHMARK_READY
    return CalibrationReadiness.INCOMPLETE_BENCHMARK
