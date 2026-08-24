"""Stage 8-0 deterministic baseline seal contract.

The seal records integrity and reproducibility facts about one frozen Teacher-Gold
run.  It does not change resolver authority, impose a hidden accuracy threshold,
authorize model training, or expose private Teacher-Gold rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from typing import Any

from .calibration import BenchmarkSplit
from .teacher_gold_evaluation import TeacherGoldEvaluationReport
from .teacher_gold_vocabulary_v0_3 import TEACHER_GOLD_VOCABULARY_VERSION_V0_3


STAGE8_BASELINE_SEAL_SCHEMA_NAME = "st_guitar_harmonic_engine.stage8_baseline_seal"
STAGE8_BASELINE_SEAL_SCHEMA_VERSION = "0.1"
EXPECTED_REFERENCE_CASE_COUNT = 200
EXPECTED_EXECUTABLE_CASE_COUNT = 200
_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class Stage8BaselineStatus(str, Enum):
    READY = "ready"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class Stage8SplitMetrics:
    split: BenchmarkSplit
    reference_case_count: int
    correct_case_count: int
    state_match_count: int
    identity_applicable_count: int
    identity_match_count: int
    validation_or_runtime_error_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.split, BenchmarkSplit):
            raise TypeError("split must be a BenchmarkSplit")
        for name in (
            "reference_case_count",
            "correct_case_count",
            "state_match_count",
            "identity_applicable_count",
            "identity_match_count",
            "validation_or_runtime_error_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative int")
        if self.correct_case_count > self.reference_case_count:
            raise ValueError("correct_case_count cannot exceed reference_case_count")
        if self.state_match_count > self.reference_case_count:
            raise ValueError("state_match_count cannot exceed reference_case_count")
        if self.identity_match_count > self.identity_applicable_count:
            raise ValueError("identity_match_count cannot exceed identity_applicable_count")

    @property
    def musical_accuracy(self) -> float:
        return self.correct_case_count / self.reference_case_count if self.reference_case_count else 0.0

    @property
    def state_accuracy(self) -> float:
        return self.state_match_count / self.reference_case_count if self.reference_case_count else 0.0

    @property
    def identity_accuracy(self) -> float:
        return self.identity_match_count / self.identity_applicable_count if self.identity_applicable_count else 0.0


@dataclass(frozen=True, slots=True)
class Stage8BaselineSeal:
    status: Stage8BaselineStatus
    engine_commit_sha: str
    teacher_gold_vocabulary_version: str
    calibration_source_sha256: str
    holdout_source_sha256: str
    reference_case_count: int
    executable_case_count: int
    reference_only_case_count: int
    correct_case_count: int
    state_match_count: int
    identity_applicable_count: int
    identity_match_count: int
    validation_or_runtime_error_count: int
    deterministic_stable: bool
    calibration: Stage8SplitMetrics
    holdout: Stage8SplitMetrics
    blocking_reasons: tuple[str, ...]
    seal_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, Stage8BaselineStatus):
            raise TypeError("status must be a Stage8BaselineStatus")
        _validate_sha(self.engine_commit_sha, _SHA40_RE, "engine_commit_sha")
        if self.teacher_gold_vocabulary_version != TEACHER_GOLD_VOCABULARY_VERSION_V0_3:
            raise ValueError("teacher_gold_vocabulary_version must be v0.3")
        _validate_sha(self.calibration_source_sha256, _SHA256_RE, "calibration_source_sha256")
        _validate_sha(self.holdout_source_sha256, _SHA256_RE, "holdout_source_sha256")
        _validate_sha(self.seal_sha256, _SHA256_RE, "seal_sha256")
        if self.calibration_source_sha256 == self.holdout_source_sha256:
            raise ValueError("calibration and holdout source digests must differ")
        for name in (
            "reference_case_count",
            "executable_case_count",
            "reference_only_case_count",
            "correct_case_count",
            "state_match_count",
            "identity_applicable_count",
            "identity_match_count",
            "validation_or_runtime_error_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative int")
        if not isinstance(self.deterministic_stable, bool):
            raise TypeError("deterministic_stable must be bool")
        if not isinstance(self.calibration, Stage8SplitMetrics) or not isinstance(
            self.holdout, Stage8SplitMetrics
        ):
            raise TypeError("calibration and holdout must be Stage8SplitMetrics")
        if self.calibration.split is not BenchmarkSplit.CALIBRATION:
            raise ValueError("calibration metrics must use calibration split")
        if self.holdout.split is not BenchmarkSplit.HOLDOUT:
            raise ValueError("holdout metrics must use holdout split")
        if self.calibration.reference_case_count + self.holdout.reference_case_count != self.reference_case_count:
            raise ValueError("split case counts must equal reference_case_count")
        if not isinstance(self.blocking_reasons, tuple) or any(
            not isinstance(item, str) or not item for item in self.blocking_reasons
        ):
            raise TypeError("blocking_reasons must contain non-empty strings")
        if tuple(sorted(set(self.blocking_reasons))) != self.blocking_reasons:
            raise ValueError("blocking_reasons must be unique canonical order")
        if self.status is Stage8BaselineStatus.READY and self.blocking_reasons:
            raise ValueError("ready seal cannot contain blocking reasons")
        if self.status is Stage8BaselineStatus.BLOCKED and not self.blocking_reasons:
            raise ValueError("blocked seal requires at least one blocking reason")

    @property
    def musical_accuracy(self) -> float:
        return self.correct_case_count / self.executable_case_count if self.executable_case_count else 0.0

    @property
    def state_accuracy(self) -> float:
        return self.state_match_count / self.executable_case_count if self.executable_case_count else 0.0

    @property
    def identity_accuracy(self) -> float:
        return self.identity_match_count / self.identity_applicable_count if self.identity_applicable_count else 0.0


def _validate_sha(value: object, pattern: re.Pattern[str], name: str) -> None:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase hexadecimal digest")


def _split_metrics(report: TeacherGoldEvaluationReport, split: BenchmarkSplit) -> Stage8SplitMetrics:
    cases = tuple(item for item in report.cases if item.split is split)
    return Stage8SplitMetrics(
        split=split,
        reference_case_count=len(cases),
        correct_case_count=sum(item.is_correct for item in cases),
        state_match_count=sum(item.state_match is True for item in cases),
        identity_applicable_count=sum(item.identity_match is not None for item in cases),
        identity_match_count=sum(item.identity_match is True for item in cases),
        validation_or_runtime_error_count=sum(item.error_type is not None for item in cases),
    )


def _blocking_reasons(report: TeacherGoldEvaluationReport) -> tuple[str, ...]:
    reasons: list[str] = []
    if report.reference_case_count != EXPECTED_REFERENCE_CASE_COUNT:
        reasons.append("reference_case_count_not_200")
    if report.executable_case_count != EXPECTED_EXECUTABLE_CASE_COUNT:
        reasons.append("executable_case_count_not_200")
    if report.reference_only_case_count != 0:
        reasons.append("reference_only_cases_present")
    if report.validation_or_runtime_error_count != 0:
        reasons.append("validation_or_runtime_errors_present")
    if not report.deterministic_stable:
        reasons.append("evaluation_not_deterministic")
    calibration_count = sum(item.split is BenchmarkSplit.CALIBRATION for item in report.cases)
    holdout_count = sum(item.split is BenchmarkSplit.HOLDOUT for item in report.cases)
    if calibration_count != 100:
        reasons.append("calibration_case_count_not_100")
    if holdout_count != 100:
        reasons.append("holdout_case_count_not_100")
    return tuple(sorted(reasons))


def _seal_payload(
    *,
    status: Stage8BaselineStatus,
    engine_commit_sha: str,
    calibration_source_sha256: str,
    holdout_source_sha256: str,
    report: TeacherGoldEvaluationReport,
    calibration: Stage8SplitMetrics,
    holdout: Stage8SplitMetrics,
    blocking_reasons: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "schema_name": STAGE8_BASELINE_SEAL_SCHEMA_NAME,
        "schema_version": STAGE8_BASELINE_SEAL_SCHEMA_VERSION,
        "status": status.value,
        "engine_commit_sha": engine_commit_sha,
        "teacher_gold_vocabulary_version": TEACHER_GOLD_VOCABULARY_VERSION_V0_3,
        "calibration_source_sha256": calibration_source_sha256,
        "holdout_source_sha256": holdout_source_sha256,
        "reference_case_count": report.reference_case_count,
        "executable_case_count": report.executable_case_count,
        "reference_only_case_count": report.reference_only_case_count,
        "correct_case_count": report.correct_case_count,
        "state_match_count": report.state_match_count,
        "identity_applicable_count": report.identity_applicable_count,
        "identity_match_count": report.identity_match_count,
        "validation_or_runtime_error_count": report.validation_or_runtime_error_count,
        "deterministic_stable": report.deterministic_stable,
        "musical_accuracy": report.musical_accuracy,
        "state_accuracy": report.state_accuracy,
        "identity_accuracy": report.identity_accuracy,
        "calibration": _serialize_split(calibration),
        "holdout": _serialize_split(holdout),
        "blocking_reasons": list(blocking_reasons),
    }


def _serialize_split(metrics: Stage8SplitMetrics) -> dict[str, Any]:
    return {
        "split": metrics.split.value,
        "reference_case_count": metrics.reference_case_count,
        "correct_case_count": metrics.correct_case_count,
        "state_match_count": metrics.state_match_count,
        "identity_applicable_count": metrics.identity_applicable_count,
        "identity_match_count": metrics.identity_match_count,
        "validation_or_runtime_error_count": metrics.validation_or_runtime_error_count,
        "musical_accuracy": metrics.musical_accuracy,
        "state_accuracy": metrics.state_accuracy,
        "identity_accuracy": metrics.identity_accuracy,
    }


def _digest_payload(payload: object) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_stage8_baseline_seal(
    report: TeacherGoldEvaluationReport,
    *,
    engine_commit_sha: str,
    calibration_source_sha256: str,
    holdout_source_sha256: str,
) -> Stage8BaselineSeal:
    """Build a fail-closed Stage 8-0 baseline seal from one evaluation report.

    Accuracy is recorded but deliberately not used as an implicit readiness
    threshold.  Readiness means the frozen corpus is complete, fully executable,
    error-free, and deterministic.  Any future performance threshold must be an
    explicit separately reviewed contract.
    """

    if not isinstance(report, TeacherGoldEvaluationReport):
        raise TypeError("report must be a TeacherGoldEvaluationReport")
    _validate_sha(engine_commit_sha, _SHA40_RE, "engine_commit_sha")
    _validate_sha(calibration_source_sha256, _SHA256_RE, "calibration_source_sha256")
    _validate_sha(holdout_source_sha256, _SHA256_RE, "holdout_source_sha256")
    if calibration_source_sha256 == holdout_source_sha256:
        raise ValueError("calibration and holdout source digests must differ")

    calibration = _split_metrics(report, BenchmarkSplit.CALIBRATION)
    holdout = _split_metrics(report, BenchmarkSplit.HOLDOUT)
    reasons = _blocking_reasons(report)
    status = Stage8BaselineStatus.BLOCKED if reasons else Stage8BaselineStatus.READY
    payload = _seal_payload(
        status=status,
        engine_commit_sha=engine_commit_sha,
        calibration_source_sha256=calibration_source_sha256,
        holdout_source_sha256=holdout_source_sha256,
        report=report,
        calibration=calibration,
        holdout=holdout,
        blocking_reasons=reasons,
    )
    return Stage8BaselineSeal(
        status=status,
        engine_commit_sha=engine_commit_sha,
        teacher_gold_vocabulary_version=TEACHER_GOLD_VOCABULARY_VERSION_V0_3,
        calibration_source_sha256=calibration_source_sha256,
        holdout_source_sha256=holdout_source_sha256,
        reference_case_count=report.reference_case_count,
        executable_case_count=report.executable_case_count,
        reference_only_case_count=report.reference_only_case_count,
        correct_case_count=report.correct_case_count,
        state_match_count=report.state_match_count,
        identity_applicable_count=report.identity_applicable_count,
        identity_match_count=report.identity_match_count,
        validation_or_runtime_error_count=report.validation_or_runtime_error_count,
        deterministic_stable=report.deterministic_stable,
        calibration=calibration,
        holdout=holdout,
        blocking_reasons=reasons,
        seal_sha256=_digest_payload(payload),
    )


def serialize_stage8_baseline_seal(seal: Stage8BaselineSeal) -> dict[str, Any]:
    if not isinstance(seal, Stage8BaselineSeal):
        raise TypeError("seal must be a Stage8BaselineSeal")
    payload = {
        "schema_name": STAGE8_BASELINE_SEAL_SCHEMA_NAME,
        "schema_version": STAGE8_BASELINE_SEAL_SCHEMA_VERSION,
        "status": seal.status.value,
        "engine_commit_sha": seal.engine_commit_sha,
        "teacher_gold_vocabulary_version": seal.teacher_gold_vocabulary_version,
        "calibration_source_sha256": seal.calibration_source_sha256,
        "holdout_source_sha256": seal.holdout_source_sha256,
        "reference_case_count": seal.reference_case_count,
        "executable_case_count": seal.executable_case_count,
        "reference_only_case_count": seal.reference_only_case_count,
        "correct_case_count": seal.correct_case_count,
        "state_match_count": seal.state_match_count,
        "identity_applicable_count": seal.identity_applicable_count,
        "identity_match_count": seal.identity_match_count,
        "validation_or_runtime_error_count": seal.validation_or_runtime_error_count,
        "deterministic_stable": seal.deterministic_stable,
        "musical_accuracy": seal.musical_accuracy,
        "state_accuracy": seal.state_accuracy,
        "identity_accuracy": seal.identity_accuracy,
        "calibration": _serialize_split(seal.calibration),
        "holdout": _serialize_split(seal.holdout),
        "blocking_reasons": list(seal.blocking_reasons),
        "seal_sha256": seal.seal_sha256,
    }
    expected_digest = _digest_payload({key: value for key, value in payload.items() if key != "seal_sha256"})
    if expected_digest != seal.seal_sha256:
        raise ValueError("seal_sha256 does not match canonical seal payload")
    return payload
