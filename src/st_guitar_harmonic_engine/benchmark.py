"""Stage 7-E deterministic engine benchmark foundation.

This harness measures engine behavior and stability only. It does not claim
musical accuracy without teacher-gold labels.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from .public_api import is_public_result_payload_compatible
from .public_runtime import execute_public_request


BENCHMARK_SCHEMA_NAME = "st_guitar_harmonic_engine.benchmark"
BENCHMARK_SCHEMA_VERSION = "1.0"
BENCHMARK_ACCURACY_CLAIM = "not_available_without_teacher_gold"


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    case_id: str
    payload: object

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or not self.case_id or self.case_id != self.case_id.strip():
            raise ValueError("case_id must be a non-empty canonical string")


@dataclass(frozen=True, slots=True)
class BenchmarkCaseResult:
    case_id: str
    frame_count: int
    exact_resolved_count: int
    ambiguous_count: int
    abstain_count: int
    no_match_count: int
    schema_valid: bool
    deterministic_stable: bool
    output_sha256: str | None
    error_type: str | None


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    case_count: int
    frame_count: int
    exact_resolved_count: int
    ambiguous_count: int
    abstain_count: int
    no_match_count: int
    schema_valid_count: int
    validation_or_runtime_error_count: int
    deterministic_stable: bool
    cases: tuple[BenchmarkCaseResult, ...]

    @property
    def exact_resolution_rate(self) -> float:
        return self.exact_resolved_count / self.frame_count if self.frame_count else 0.0

    @property
    def ambiguity_rate(self) -> float:
        return self.ambiguous_count / self.frame_count if self.frame_count else 0.0

    @property
    def abstention_rate(self) -> float:
        return self.abstain_count / self.frame_count if self.frame_count else 0.0

    @property
    def no_match_rate(self) -> float:
        return self.no_match_count / self.frame_count if self.frame_count else 0.0


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _digest(payload: object) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _count_result_states(payload: dict[str, Any]) -> tuple[int, int, int, int, int]:
    results = payload["results"]
    frame_count = len(results)
    exact_resolved = 0
    ambiguous = 0
    abstain = 0
    no_match = 0
    for item in results:
        decision = item["decision"]
        state = decision["state"]
        if state == "resolved":
            candidates = decision["candidates"]
            if len(candidates) == 1 and "exact" in candidates[0]["evidence"]:
                exact_resolved += 1
        elif state == "ambiguous":
            ambiguous += 1
        elif state == "abstain":
            abstain += 1
        elif state == "no_match":
            no_match += 1
        else:
            raise ValueError("public result contains unsupported final state")
    return frame_count, exact_resolved, ambiguous, abstain, no_match


def run_deterministic_benchmark(cases: tuple[BenchmarkCase, ...]) -> BenchmarkReport:
    """Execute every case twice and summarize deterministic engine behavior."""

    if not isinstance(cases, tuple) or any(not isinstance(item, BenchmarkCase) for item in cases):
        raise TypeError("cases must contain BenchmarkCase values")
    if len({item.case_id for item in cases}) != len(cases):
        raise ValueError("benchmark case ids must be unique")

    case_results: list[BenchmarkCaseResult] = []
    totals = [0, 0, 0, 0, 0]
    schema_valid_count = 0
    error_count = 0
    all_stable = True

    for case in cases:
        try:
            first = execute_public_request(case.payload)
            second = execute_public_request(case.payload)
            schema_valid = is_public_result_payload_compatible(first)
            stable = first == second and _canonical_bytes(first) == _canonical_bytes(second)
            counts = _count_result_states(first)
            for index, value in enumerate(counts):
                totals[index] += value
            if schema_valid:
                schema_valid_count += 1
            if not stable:
                all_stable = False
            case_results.append(
                BenchmarkCaseResult(
                    case_id=case.case_id,
                    frame_count=counts[0],
                    exact_resolved_count=counts[1],
                    ambiguous_count=counts[2],
                    abstain_count=counts[3],
                    no_match_count=counts[4],
                    schema_valid=schema_valid,
                    deterministic_stable=stable,
                    output_sha256=_digest(first),
                    error_type=None,
                )
            )
        except Exception as exc:  # benchmark records isolated failures instead of aborting the corpus
            error_count += 1
            all_stable = False
            case_results.append(
                BenchmarkCaseResult(
                    case_id=case.case_id,
                    frame_count=0,
                    exact_resolved_count=0,
                    ambiguous_count=0,
                    abstain_count=0,
                    no_match_count=0,
                    schema_valid=False,
                    deterministic_stable=False,
                    output_sha256=None,
                    error_type=type(exc).__name__,
                )
            )

    return BenchmarkReport(
        case_count=len(cases),
        frame_count=totals[0],
        exact_resolved_count=totals[1],
        ambiguous_count=totals[2],
        abstain_count=totals[3],
        no_match_count=totals[4],
        schema_valid_count=schema_valid_count,
        validation_or_runtime_error_count=error_count,
        deterministic_stable=all_stable,
        cases=tuple(case_results),
    )


def serialize_benchmark_report(report: BenchmarkReport) -> dict[str, Any]:
    if not isinstance(report, BenchmarkReport):
        raise TypeError("report must be a BenchmarkReport")
    return {
        "schema_name": BENCHMARK_SCHEMA_NAME,
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "musical_accuracy_claim": BENCHMARK_ACCURACY_CLAIM,
        "case_count": report.case_count,
        "frame_count": report.frame_count,
        "exact_resolution_rate": report.exact_resolution_rate,
        "ambiguity_rate": report.ambiguity_rate,
        "abstention_rate": report.abstention_rate,
        "no_match_rate": report.no_match_rate,
        "schema_valid_count": report.schema_valid_count,
        "validation_or_runtime_error_count": report.validation_or_runtime_error_count,
        "deterministic_stable": report.deterministic_stable,
        "cases": [
            {
                "case_id": item.case_id,
                "frame_count": item.frame_count,
                "exact_resolved_count": item.exact_resolved_count,
                "ambiguous_count": item.ambiguous_count,
                "abstain_count": item.abstain_count,
                "no_match_count": item.no_match_count,
                "schema_valid": item.schema_valid,
                "deterministic_stable": item.deterministic_stable,
                "output_sha256": item.output_sha256,
                "error_type": item.error_type,
            }
            for item in report.cases
        ],
    }
