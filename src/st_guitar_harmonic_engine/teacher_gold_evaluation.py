"""Deterministic Teacher-Gold evaluation over the frozen public runtime.

This module measures agreement between human Teacher-Gold truth and current engine
outputs. It never mutates resolver/runtime state, never promotes reference-only
labels, and never authorizes model training or production use.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from .abstention import FinalDecisionState
from .calibration import BenchmarkSplit
from .public_api import is_public_result_payload_compatible
from .public_runtime import execute_public_request
from .resolver import CandidateFamily, HarmonicIdentity
from .teacher_gold_benchmark_assembly import TeacherGoldBenchmarkAssembly


TEACHER_GOLD_EVALUATION_SCHEMA_NAME = "st_guitar_harmonic_engine.teacher_gold_evaluation"
TEACHER_GOLD_EVALUATION_SCHEMA_VERSION = "1.0"
TEACHER_GOLD_ACCURACY_DENOMINATOR = "engine_executable_cases_only"
TEACHER_GOLD_INVERSION_ACCURACY_CLAIM = "not_available_public_result_v1_0"


@dataclass(frozen=True, slots=True)
class TeacherGoldEvaluationCaseResult:
    case_id: str
    split: BenchmarkSplit
    reference_only: bool
    expected_state: FinalDecisionState
    actual_state: FinalDecisionState | None
    state_match: bool | None
    identity_match: bool | None
    schema_valid: bool
    deterministic_stable: bool
    output_sha256: str | None
    error_type: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or not self.case_id:
            raise ValueError("case_id must be non-empty text")
        if not isinstance(self.split, BenchmarkSplit):
            raise TypeError("split must be a BenchmarkSplit")
        if not isinstance(self.reference_only, bool):
            raise TypeError("reference_only must be bool")
        if not isinstance(self.expected_state, FinalDecisionState):
            raise TypeError("expected_state must be a FinalDecisionState")
        if self.actual_state is not None and not isinstance(self.actual_state, FinalDecisionState):
            raise TypeError("actual_state must be a FinalDecisionState or None")
        if self.state_match is not None and not isinstance(self.state_match, bool):
            raise TypeError("state_match must be bool or None")
        if self.identity_match is not None and not isinstance(self.identity_match, bool):
            raise TypeError("identity_match must be bool or None")
        if not isinstance(self.schema_valid, bool) or not isinstance(self.deterministic_stable, bool):
            raise TypeError("schema_valid and deterministic_stable must be bool")
        if self.output_sha256 is not None and not isinstance(self.output_sha256, str):
            raise TypeError("output_sha256 must be str or None")
        if self.error_type is not None and not isinstance(self.error_type, str):
            raise TypeError("error_type must be str or None")

        if self.reference_only:
            if any(
                value is not None
                for value in (
                    self.actual_state,
                    self.state_match,
                    self.identity_match,
                    self.output_sha256,
                    self.error_type,
                )
            ):
                raise ValueError("reference-only cases cannot claim engine evaluation results")
            if self.schema_valid or self.deterministic_stable:
                raise ValueError("reference-only cases are not executed")

    @property
    def is_correct(self) -> bool:
        if self.reference_only or self.error_type is not None:
            return False
        if not self.schema_valid or not self.deterministic_stable:
            return False
        if self.state_match is not True:
            return False
        return self.identity_match is not False


@dataclass(frozen=True, slots=True)
class TeacherGoldEvaluationReport:
    reference_case_count: int
    executable_case_count: int
    reference_only_case_count: int
    correct_case_count: int
    state_match_count: int
    identity_applicable_count: int
    identity_match_count: int
    validation_or_runtime_error_count: int
    deterministic_stable: bool
    cases: tuple[TeacherGoldEvaluationCaseResult, ...]

    def __post_init__(self) -> None:
        integer_fields = (
            "reference_case_count",
            "executable_case_count",
            "reference_only_case_count",
            "correct_case_count",
            "state_match_count",
            "identity_applicable_count",
            "identity_match_count",
            "validation_or_runtime_error_count",
        )
        for field in integer_fields:
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{field} must be a non-negative int")
        if self.executable_case_count + self.reference_only_case_count != self.reference_case_count:
            raise ValueError("executable + reference-only counts must equal reference count")
        if self.correct_case_count > self.executable_case_count:
            raise ValueError("correct_case_count cannot exceed executable_case_count")
        if self.state_match_count > self.executable_case_count:
            raise ValueError("state_match_count cannot exceed executable_case_count")
        if self.identity_match_count > self.identity_applicable_count:
            raise ValueError("identity_match_count cannot exceed identity_applicable_count")
        if not isinstance(self.deterministic_stable, bool):
            raise TypeError("deterministic_stable must be bool")
        if not isinstance(self.cases, tuple) or any(
            not isinstance(item, TeacherGoldEvaluationCaseResult) for item in self.cases
        ):
            raise TypeError("cases must contain TeacherGoldEvaluationCaseResult values")
        if len(self.cases) != self.reference_case_count:
            raise ValueError("cases length must match reference_case_count")

    @property
    def executable_coverage(self) -> float:
        return self.executable_case_count / self.reference_case_count if self.reference_case_count else 0.0

    @property
    def musical_accuracy(self) -> float:
        return self.correct_case_count / self.executable_case_count if self.executable_case_count else 0.0

    @property
    def state_accuracy(self) -> float:
        return self.state_match_count / self.executable_case_count if self.executable_case_count else 0.0

    @property
    def identity_accuracy(self) -> float:
        return self.identity_match_count / self.identity_applicable_count if self.identity_applicable_count else 0.0


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _digest(payload: object) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _decision_identity(item: object) -> HarmonicIdentity:
    if not isinstance(item, dict) or "identity" not in item:
        raise ValueError("public result candidate is malformed")
    raw = item["identity"]
    if not isinstance(raw, dict) or set(raw) != {"root_pc", "family", "variant"}:
        raise ValueError("public result identity is malformed")
    return HarmonicIdentity(
        raw["root_pc"],
        CandidateFamily(raw["family"]),
        raw["variant"],
    )


def _extract_single_decision(payload: object) -> tuple[FinalDecisionState, tuple[HarmonicIdentity, ...]]:
    if not is_public_result_payload_compatible(payload):
        raise ValueError("public result schema is incompatible")
    assert isinstance(payload, dict)
    results = payload["results"]
    if len(results) != 1:
        raise ValueError("Teacher-Gold v0.1 evaluation requires exactly one result frame per case")
    item = results[0]
    if not isinstance(item, dict) or "decision" not in item:
        raise ValueError("public result frame is malformed")
    decision = item["decision"]
    if not isinstance(decision, dict) or "state" not in decision or "candidates" not in decision:
        raise ValueError("public result decision is malformed")
    state = FinalDecisionState(decision["state"])
    raw_candidates = decision["candidates"]
    if not isinstance(raw_candidates, list):
        raise ValueError("public result candidates must be a list")
    identities = tuple(sorted(_decision_identity(candidate) for candidate in raw_candidates))
    if len(set(identities)) != len(identities):
        raise ValueError("public result candidate identities must be unique")
    return state, identities


def evaluate_teacher_gold_assembly(
    assembly: TeacherGoldBenchmarkAssembly,
) -> TeacherGoldEvaluationReport:
    """Execute each engine-representable case twice and compare with human truth."""

    if not isinstance(assembly, TeacherGoldBenchmarkAssembly):
        raise TypeError("assembly must be a TeacherGoldBenchmarkAssembly")

    expected_by_id = {item.case_id: item for item in assembly.benchmark.cases}
    reference_only = set(assembly.reference_only_case_ids)
    case_results: list[TeacherGoldEvaluationCaseResult] = []
    correct = 0
    state_matches = 0
    identity_applicable = 0
    identity_matches = 0
    errors = 0
    all_stable = True

    for reference in assembly.reference_cases:
        if reference.case_id in reference_only:
            case_results.append(
                TeacherGoldEvaluationCaseResult(
                    case_id=reference.case_id,
                    split=reference.split,
                    reference_only=True,
                    expected_state=reference.expected_state,
                    actual_state=None,
                    state_match=None,
                    identity_match=None,
                    schema_valid=False,
                    deterministic_stable=False,
                    output_sha256=None,
                    error_type=None,
                )
            )
            continue

        expected = expected_by_id[reference.case_id]
        try:
            first = execute_public_request(reference.public_request)
            second = execute_public_request(reference.public_request)
            schema_valid = (
                is_public_result_payload_compatible(first)
                and is_public_result_payload_compatible(second)
            )
            stable = first == second and _canonical_bytes(first) == _canonical_bytes(second)
            if not stable:
                all_stable = False
                errors += 1
                case_results.append(
                    TeacherGoldEvaluationCaseResult(
                        case_id=reference.case_id,
                        split=reference.split,
                        reference_only=False,
                        expected_state=reference.expected_state,
                        actual_state=None,
                        state_match=None,
                        identity_match=None,
                        schema_valid=schema_valid,
                        deterministic_stable=False,
                        output_sha256=_digest(first),
                        error_type="NondeterministicOutput",
                    )
                )
                continue
            if not schema_valid:
                errors += 1
                case_results.append(
                    TeacherGoldEvaluationCaseResult(
                        case_id=reference.case_id,
                        split=reference.split,
                        reference_only=False,
                        expected_state=reference.expected_state,
                        actual_state=None,
                        state_match=None,
                        identity_match=None,
                        schema_valid=False,
                        deterministic_stable=True,
                        output_sha256=_digest(first),
                        error_type="IncompatiblePublicResult",
                    )
                )
                continue

            actual_state, actual_identities = _extract_single_decision(first)
            state_match = actual_state is expected.expected_state
            identity_match: bool | None
            if expected.expected_state in {
                FinalDecisionState.RESOLVED,
                FinalDecisionState.AMBIGUOUS,
            }:
                identity_applicable += 1
                identity_match = actual_identities == expected.acceptable_identities
                if identity_match:
                    identity_matches += 1
            else:
                identity_match = None

            if state_match:
                state_matches += 1
            result = TeacherGoldEvaluationCaseResult(
                case_id=reference.case_id,
                split=reference.split,
                reference_only=False,
                expected_state=reference.expected_state,
                actual_state=actual_state,
                state_match=state_match,
                identity_match=identity_match,
                schema_valid=True,
                deterministic_stable=True,
                output_sha256=_digest(first),
                error_type=None,
            )
            if result.is_correct:
                correct += 1
            case_results.append(result)
        except Exception as exc:  # isolate one benchmark case without hiding failure
            errors += 1
            all_stable = False
            case_results.append(
                TeacherGoldEvaluationCaseResult(
                    case_id=reference.case_id,
                    split=reference.split,
                    reference_only=False,
                    expected_state=reference.expected_state,
                    actual_state=None,
                    state_match=None,
                    identity_match=None,
                    schema_valid=False,
                    deterministic_stable=False,
                    output_sha256=None,
                    error_type=type(exc).__name__,
                )
            )

    return TeacherGoldEvaluationReport(
        reference_case_count=assembly.reference_case_count,
        executable_case_count=assembly.executable_case_count,
        reference_only_case_count=assembly.reference_only_case_count,
        correct_case_count=correct,
        state_match_count=state_matches,
        identity_applicable_count=identity_applicable,
        identity_match_count=identity_matches,
        validation_or_runtime_error_count=errors,
        deterministic_stable=all_stable,
        cases=tuple(case_results),
    )


def serialize_teacher_gold_evaluation(report: TeacherGoldEvaluationReport) -> dict[str, Any]:
    if not isinstance(report, TeacherGoldEvaluationReport):
        raise TypeError("report must be a TeacherGoldEvaluationReport")
    return {
        "schema_name": TEACHER_GOLD_EVALUATION_SCHEMA_NAME,
        "schema_version": TEACHER_GOLD_EVALUATION_SCHEMA_VERSION,
        "accuracy_denominator": TEACHER_GOLD_ACCURACY_DENOMINATOR,
        "inversion_accuracy_claim": TEACHER_GOLD_INVERSION_ACCURACY_CLAIM,
        "reference_case_count": report.reference_case_count,
        "executable_case_count": report.executable_case_count,
        "reference_only_case_count": report.reference_only_case_count,
        "executable_coverage": report.executable_coverage,
        "musical_accuracy": report.musical_accuracy,
        "state_accuracy": report.state_accuracy,
        "identity_accuracy": report.identity_accuracy,
        "correct_case_count": report.correct_case_count,
        "state_match_count": report.state_match_count,
        "identity_applicable_count": report.identity_applicable_count,
        "identity_match_count": report.identity_match_count,
        "validation_or_runtime_error_count": report.validation_or_runtime_error_count,
        "deterministic_stable": report.deterministic_stable,
        "cases": [
            {
                "case_id": item.case_id,
                "split": item.split.value,
                "reference_only": item.reference_only,
                "expected_state": item.expected_state.value,
                "actual_state": item.actual_state.value if item.actual_state is not None else None,
                "state_match": item.state_match,
                "identity_match": item.identity_match,
                "schema_valid": item.schema_valid,
                "deterministic_stable": item.deterministic_stable,
                "output_sha256": item.output_sha256,
                "error_type": item.error_type,
            }
            for item in report.cases
        ],
    }
