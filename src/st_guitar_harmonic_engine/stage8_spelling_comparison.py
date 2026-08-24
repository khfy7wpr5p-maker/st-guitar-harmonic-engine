"""Stage 8 spelling-aware Teacher-Gold comparison profile v0.1.

This module evaluates the frozen Teacher-Gold reference partitions through the
additive public request v1.1 spelling boundary.  It is a comparison profile only:
it does not replace the Stage 8-0 public-v1.0 baseline, alter resolver authority,
set a performance threshold, tune from holdout, or authorize model training.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
import re
from typing import Any

from .abstention import FinalDecisionState
from .calibration import BenchmarkSplit
from .public_api import is_public_result_payload_compatible
from .public_api_v1_1 import (
    PUBLIC_API_SCHEMA_VERSION_V1_1,
    execute_public_request_v1_1,
    validate_public_request_v1_1,
)
from .resolver import CandidateFamily, HarmonicIdentity
from .teacher_gold_evaluation import (
    TeacherGoldEvaluationCaseResult,
    TeacherGoldEvaluationReport,
)
from .teacher_gold_vocabulary_v0_3 import (
    adapt_teacher_gold_reference_row_v0_3,
    assemble_frozen_teacher_gold_benchmark_v0_3,
)


STAGE8_SPELLING_COMPARISON_PROFILE = "public_v1_1_spelling"
STAGE8_SPELLING_COMPARISON_VERSION = "0.1"
_NOTE_RE = re.compile(r"^(?P<step>[A-G])(?P<accidental>[#b]?)(?P<octave>-?\d+)$")


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def _digest(payload: object) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _written_pitch(note_name: str) -> dict[str, object]:
    if not isinstance(note_name, str):
        raise TypeError("note_name must be a str")
    match = _NOTE_RE.fullmatch(note_name)
    if match is None:
        raise ValueError("Teacher-Gold note token cannot be represented by public v1.1 spelling")
    accidental = match.group("accidental")
    alter = 1 if accidental == "#" else -1 if accidental == "b" else 0
    return {
        "step": match.group("step"),
        "alter": alter,
        "octave": int(match.group("octave")),
    }


def build_teacher_gold_public_request_v1_1(
    row: Mapping[str, object],
    *,
    split: BenchmarkSplit,
) -> dict[str, Any]:
    """Build one spelling-aware request after full frozen Teacher-Gold validation."""

    if not isinstance(row, Mapping):
        raise TypeError("row must be a mapping")
    if not isinstance(split, BenchmarkSplit):
        raise TypeError("split must be BenchmarkSplit")

    reference = adapt_teacher_gold_reference_row_v0_3(row, split=split)
    base = reference.public_request
    frames = base["frames"]
    if not isinstance(frames, list) or len(frames) != 1:
        raise ValueError("Teacher-Gold v0.1 comparison requires exactly one frame")
    events = frames[0]["events"]
    if not isinstance(events, list):
        raise ValueError("Teacher-Gold public request events are malformed")

    raw_notes = row.get("input_notes")
    if not isinstance(raw_notes, str) or not raw_notes:
        raise ValueError("input_notes must be non-empty text")
    notes = tuple(raw_notes.split(","))
    if len(notes) != len(events):
        raise ValueError("Teacher-Gold note/event cardinality changed during adaptation")

    spelling_events = [
        {**event, "written_pitch": _written_pitch(note)}
        for event, note in zip(events, notes)
    ]
    payload: dict[str, Any] = {
        **base,
        "schema_version": PUBLIC_API_SCHEMA_VERSION_V1_1,
        "frames": [{**frames[0], "events": spelling_events}],
    }
    validate_public_request_v1_1(payload)
    return payload


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


def _extract_single_decision(
    payload: object,
) -> tuple[FinalDecisionState, tuple[HarmonicIdentity, ...]]:
    if not is_public_result_payload_compatible(payload):
        raise ValueError("public result schema is incompatible")
    assert isinstance(payload, dict)
    results = payload["results"]
    if len(results) != 1:
        raise ValueError("Teacher-Gold comparison requires exactly one result frame")
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


def evaluate_teacher_gold_rows_v1_1(
    calibration_rows: Sequence[Mapping[str, object]],
    holdout_rows: Sequence[Mapping[str, object]],
) -> TeacherGoldEvaluationReport:
    """Evaluate frozen rows twice through spelling-aware public v1.1.

    Existing frozen partition/namespace/vocabulary guards are reused before any
    comparison output is counted.  The returned report uses the same metric
    semantics as the Stage 8-0 baseline report so profiles can be compared without
    changing the baseline itself.
    """

    if not isinstance(calibration_rows, Sequence) or isinstance(
        calibration_rows, (str, bytes, bytearray)
    ):
        raise TypeError("calibration_rows must be a sequence")
    if not isinstance(holdout_rows, Sequence) or isinstance(
        holdout_rows, (str, bytes, bytearray)
    ):
        raise TypeError("holdout_rows must be a sequence")

    calibration = tuple(calibration_rows)
    holdout = tuple(holdout_rows)
    calibration_refs = tuple(
        adapt_teacher_gold_reference_row_v0_3(row, split=BenchmarkSplit.CALIBRATION)
        for row in calibration
    )
    holdout_refs = tuple(
        adapt_teacher_gold_reference_row_v0_3(row, split=BenchmarkSplit.HOLDOUT)
        for row in holdout
    )
    assembly = assemble_frozen_teacher_gold_benchmark_v0_3(
        calibration_refs,
        holdout_refs,
    )

    rows = calibration + holdout
    expected_by_id = {item.case_id: item for item in assembly.benchmark.cases}
    reference_only = set(assembly.reference_only_case_ids)
    case_results: list[TeacherGoldEvaluationCaseResult] = []
    correct = 0
    state_matches = 0
    identity_applicable = 0
    identity_matches = 0
    errors = 0
    all_stable = True

    for reference, row in zip(assembly.reference_cases, rows):
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
            request = build_teacher_gold_public_request_v1_1(row, split=reference.split)
            first = execute_public_request_v1_1(request)
            second = execute_public_request_v1_1(request)
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
        except Exception as exc:
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
