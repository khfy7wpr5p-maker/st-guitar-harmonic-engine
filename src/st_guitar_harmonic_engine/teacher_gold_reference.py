"""Benchmark-only reference contract for teacher-gold vocabulary gaps.

This module preserves musically valid teacher labels that are not representable by
the frozen authoritative ``HarmonicIdentity`` vocabulary. It never promotes those
labels into resolver identities and never changes resolver/runtime authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re
from typing import Any

from .abstention import FinalDecisionState
from .calibration import BenchmarkSplit
from .resolver import HarmonicIdentity
from .teacher_gold_adapter import (
    FROZEN_CALIBRATION_V0_1_CASE_COUNT,
    TEACHER_GOLD_SHEET_COLUMNS,
    TeacherGoldAdapterError,
    TeacherGoldValidationIssue,
    TeacherGoldValidationReport,
    adapt_teacher_gold_row,
    parse_teacher_candidate_identity,
)


REFERENCE_VOCABULARY_SCHEMA_VERSION = "0.1"
_REFERENCE_ONLY_LABEL_RE = re.compile(
    r"^(?P<root>[A-G](?:#|b)?)(?P<suffix>7sus4|7sus2|m6|6)(?:/(?P<bass>[A-G](?:#|b)?))?$"
)
_EXAMPLE_ID_RE = re.compile(r"^TG-\d{4}$")
_INVERSION_VALUES = frozenset(
    {
        "root_position",
        "first_inversion",
        "second_inversion",
        "third_inversion",
    }
)


@dataclass(frozen=True, slots=True)
class TeacherGoldReferenceCandidate:
    """Exact teacher label with an optional frozen engine identity mapping."""

    label: str
    engine_identity: HarmonicIdentity | None

    def __post_init__(self) -> None:
        if not isinstance(self.label, str) or not self.label or self.label != self.label.strip():
            raise ValueError("reference candidate label must be canonical non-empty text")
        if self.engine_identity is not None and not isinstance(self.engine_identity, HarmonicIdentity):
            raise TypeError("engine_identity must be a HarmonicIdentity or None")

    @property
    def is_engine_representable(self) -> bool:
        return self.engine_identity is not None


@dataclass(frozen=True, slots=True)
class TeacherGoldReferenceCase:
    """Human reference truth without granting new harmonic authority."""

    case_id: str
    split: BenchmarkSplit
    expected_state: FinalDecisionState
    expected_candidates: tuple[TeacherGoldReferenceCandidate, ...]
    public_request: dict[str, Any]
    expected_inversion: str | None
    teacher_reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or not self.case_id or self.case_id != self.case_id.strip():
            raise ValueError("case_id must be canonical non-empty text")
        if not isinstance(self.split, BenchmarkSplit):
            raise TypeError("split must be a BenchmarkSplit")
        if not isinstance(self.expected_state, FinalDecisionState):
            raise TypeError("expected_state must be a FinalDecisionState")
        if not isinstance(self.expected_candidates, tuple) or any(
            not isinstance(item, TeacherGoldReferenceCandidate) for item in self.expected_candidates
        ):
            raise TypeError("expected_candidates must contain TeacherGoldReferenceCandidate values")
        labels = tuple(item.label for item in self.expected_candidates)
        if len(set(labels)) != len(labels):
            raise ValueError("reference candidate labels must be unique")
        if not isinstance(self.public_request, dict):
            raise TypeError("public_request must be a dict")
        if self.expected_inversion is not None and self.expected_inversion not in _INVERSION_VALUES:
            raise ValueError("expected_inversion contains an unsupported value")
        if not isinstance(self.teacher_reason, str) or not self.teacher_reason:
            raise ValueError("teacher_reason must be non-empty text")

        count = len(self.expected_candidates)
        if self.expected_state is FinalDecisionState.RESOLVED and count != 1:
            raise ValueError("RESOLVED reference cases require exactly one candidate")
        if self.expected_state is FinalDecisionState.AMBIGUOUS and count < 2:
            raise ValueError("AMBIGUOUS reference cases require at least two candidates")
        if self.expected_state in {FinalDecisionState.ABSTAIN, FinalDecisionState.NO_MATCH} and count:
            raise ValueError("ABSTAIN/NO_MATCH reference cases cannot claim candidates")

    @property
    def is_engine_executable(self) -> bool:
        """Whether the existing TeacherGoldCase vocabulary can encode the full truth."""

        return all(item.is_engine_representable for item in self.expected_candidates)


@dataclass(frozen=True, slots=True)
class TeacherGoldReferenceCoverage:
    case_count: int
    executable_case_count: int
    reference_only_case_count: int
    reference_only_case_ids: tuple[str, ...]
    reference_only_labels: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.case_count < 0 or self.executable_case_count < 0 or self.reference_only_case_count < 0:
            raise ValueError("coverage counts must not be negative")
        if self.executable_case_count + self.reference_only_case_count != self.case_count:
            raise ValueError("coverage counts must sum to case_count")
        if len(self.reference_only_case_ids) != self.reference_only_case_count:
            raise ValueError("reference_only_case_ids must match reference_only_case_count")
        if tuple(sorted(self.reference_only_case_ids)) != self.reference_only_case_ids:
            raise ValueError("reference_only_case_ids must use canonical order")
        if len(set(self.reference_only_case_ids)) != len(self.reference_only_case_ids):
            raise ValueError("reference_only_case_ids must be unique")
        if tuple(sorted(set(self.reference_only_labels))) != self.reference_only_labels:
            raise ValueError("reference_only_labels must be unique canonical order")

    @property
    def is_fully_executable(self) -> bool:
        return self.reference_only_case_count == 0


def _error(code: str, field: str, message: str) -> TeacherGoldAdapterError:
    return TeacherGoldAdapterError(code, field, message)


def _text(value: object, *, field: str, required: bool = False) -> str:
    if value is None:
        text = ""
    elif isinstance(value, str):
        text = value
    else:
        raise _error("invalid_type", field, f"{field} must be a string or blank")
    if text != text.strip():
        raise _error("noncanonical_text", field, f"{field} must not have surrounding whitespace")
    if required and not text:
        raise _error("missing_value", field, f"{field} must not be blank")
    return text


def parse_teacher_reference_candidate(label: str) -> TeacherGoldReferenceCandidate:
    """Preserve known reference-only labels without inventing an engine identity."""

    if not isinstance(label, str):
        raise TypeError("label must be a str")
    if not label or label != label.strip():
        raise _error("unsupported_identity", "candidate", "candidate label must be canonical non-empty text")

    try:
        return TeacherGoldReferenceCandidate(label, parse_teacher_candidate_identity(label))
    except TeacherGoldAdapterError as exc:
        if exc.code != "unsupported_identity":
            raise
        if _REFERENCE_ONLY_LABEL_RE.fullmatch(label) is None:
            raise _error("unsupported_identity", "candidate", f"unsupported chord label: {label!r}") from exc
        return TeacherGoldReferenceCandidate(label, None)


def _row_contract(
    row: Mapping[str, object],
) -> tuple[str, FinalDecisionState, tuple[str, ...], str | None, str]:
    if not isinstance(row, Mapping):
        raise _error("invalid_row_type", "row", "teacher-gold row must be a mapping")
    if set(row) != set(TEACHER_GOLD_SHEET_COLUMNS):
        missing = sorted(set(TEACHER_GOLD_SHEET_COLUMNS) - set(row))
        extra = sorted(set(row) - set(TEACHER_GOLD_SHEET_COLUMNS))
        raise _error(
            "schema_mismatch",
            "row",
            f"row columns do not match v0.1 schema; missing={missing}, extra={extra}",
        )

    case_id = _text(row["example_id"], field="example_id", required=True)
    if _EXAMPLE_ID_RE.fullmatch(case_id) is None:
        raise _error("invalid_case_id", "example_id", "example_id must match TG-0000 format")

    status = _text(row["annotation_status"], field="annotation_status", required=True)
    if status != "VERIFIED":
        raise _error(
            "unverified_row",
            "annotation_status",
            "only VERIFIED teacher-gold rows may enter the reference contract",
        )

    state_text = _text(row["expected_state"], field="expected_state", required=True)
    if state_text not in {"RESOLVED", "AMBIGUOUS", "ABSTAIN", "NO_MATCH"}:
        raise _error("invalid_state", "expected_state", f"unsupported expected_state: {state_text!r}")
    state = FinalDecisionState(state_text.lower())

    primary = _text(row["primary_candidate"], field="primary_candidate")
    alternatives = _text(row["acceptable_alternatives"], field="acceptable_alternatives")
    inversion = _text(row["inversion"], field="inversion")
    reason = _text(row["teacher_reason"], field="teacher_reason", required=True)

    if state is FinalDecisionState.RESOLVED:
        if not primary or alternatives:
            raise _error(
                "candidate_cardinality",
                "primary_candidate",
                "RESOLVED rows require one primary candidate and no alternatives",
            )
        if inversion not in _INVERSION_VALUES:
            raise _error(
                "invalid_inversion",
                "inversion",
                "RESOLVED rows require one supported inversion value",
            )
        labels = (primary,)
        expected_inversion = inversion
    elif state is FinalDecisionState.AMBIGUOUS:
        if primary or not alternatives:
            raise _error(
                "candidate_cardinality",
                "acceptable_alternatives",
                "AMBIGUOUS rows require blank primary_candidate and explicit alternatives",
            )
        if inversion:
            raise _error("invalid_inversion", "inversion", "AMBIGUOUS rows must leave inversion blank")
        labels = tuple(alternatives.split(" | "))
        if len(labels) < 2 or any(not item for item in labels):
            raise _error(
                "invalid_alternatives",
                "acceptable_alternatives",
                "AMBIGUOUS rows require at least two candidates separated by ' | '",
            )
        if len(set(labels)) != len(labels):
            raise _error(
                "duplicate_identity",
                "acceptable_alternatives",
                "acceptable alternatives must use unique teacher labels",
            )
        expected_inversion = None
    else:
        if primary or alternatives:
            raise _error(
                "candidate_cardinality",
                "primary_candidate",
                "ABSTAIN/NO_MATCH rows must not claim candidate identities",
            )
        if inversion:
            raise _error("invalid_inversion", "inversion", "ABSTAIN/NO_MATCH rows must leave inversion blank")
        labels = ()
        expected_inversion = None

    return case_id, state, labels, expected_inversion, reason


def _surrogate_row(row: Mapping[str, object], state: FinalDecisionState) -> dict[str, object]:
    surrogate = dict(row)
    if state is FinalDecisionState.RESOLVED:
        surrogate["primary_candidate"] = "C major"
        surrogate["acceptable_alternatives"] = ""
    elif state is FinalDecisionState.AMBIGUOUS:
        surrogate["primary_candidate"] = ""
        surrogate["acceptable_alternatives"] = "C major | D major"
        surrogate["inversion"] = ""
    return surrogate


def adapt_teacher_gold_reference_row(
    row: Mapping[str, object],
    *,
    split: BenchmarkSplit = BenchmarkSplit.CALIBRATION,
) -> TeacherGoldReferenceCase:
    """Adapt one row into benchmark reference truth, including known vocabulary gaps."""

    if not isinstance(split, BenchmarkSplit):
        raise TypeError("split must be a BenchmarkSplit")
    case_id, state, labels, expected_inversion, reason = _row_contract(row)
    candidates = tuple(parse_teacher_reference_candidate(label) for label in labels)

    # Reuse the existing strict adapter for note/public-request and all non-vocabulary
    # boundary validation. Surrogate labels are never returned or scored.
    surrogate = _surrogate_row(row, state)
    validated = adapt_teacher_gold_row(surrogate, split=split)

    return TeacherGoldReferenceCase(
        case_id=case_id,
        split=split,
        expected_state=state,
        expected_candidates=candidates,
        public_request=validated.public_request,
        expected_inversion=expected_inversion,
        teacher_reason=reason,
    )


def validate_teacher_gold_reference_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    split: BenchmarkSplit = BenchmarkSplit.CALIBRATION,
) -> TeacherGoldValidationReport:
    """Validate reference truth while reporting schema errors and true unknown labels."""

    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        raise TypeError("rows must be a sequence of mappings")
    if not isinstance(split, BenchmarkSplit):
        raise TypeError("split must be a BenchmarkSplit")

    issues: list[TeacherGoldValidationIssue] = []
    valid = 0
    seen_ids: set[str] = set()
    previous_id: str | None = None

    for index, row in enumerate(rows, start=2):
        case_id: str | None = None
        if isinstance(row, Mapping):
            raw_id = row.get("example_id")
            if isinstance(raw_id, str):
                case_id = raw_id
        try:
            adapted = adapt_teacher_gold_reference_row(row, split=split)
            case_id = adapted.case_id
            if case_id in seen_ids:
                raise _error("duplicate_case_id", "example_id", f"duplicate case id: {case_id}")
            if previous_id is not None and case_id <= previous_id:
                raise _error(
                    "noncanonical_order",
                    "example_id",
                    "teacher-gold rows must use strictly increasing case_id order",
                )
            seen_ids.add(case_id)
            previous_id = case_id
            valid += 1
        except TeacherGoldAdapterError as exc:
            issues.append(
                TeacherGoldValidationIssue(
                    row_number=index,
                    case_id=case_id,
                    code=exc.code,
                    field=exc.field,
                    message=str(exc),
                )
            )

    return TeacherGoldValidationReport(len(rows), valid, tuple(issues))


def validate_frozen_calibration_reference_v0_1(
    rows: Sequence[Mapping[str, object]],
) -> TeacherGoldValidationReport:
    """Validate exact TG-0001..TG-0100 reference shape without erasing vocabulary gaps."""

    report = validate_teacher_gold_reference_rows(rows, split=BenchmarkSplit.CALIBRATION)
    issues = list(report.issues)

    if len(rows) != FROZEN_CALIBRATION_V0_1_CASE_COUNT:
        issues.append(
            TeacherGoldValidationIssue(
                row_number=None,
                case_id=None,
                code="snapshot_case_count",
                field="rows",
                message=(
                    "frozen calibration v0.1 requires exactly "
                    f"{FROZEN_CALIBRATION_V0_1_CASE_COUNT} rows"
                ),
            )
        )

    expected_ids = tuple(
        f"TG-{index:04d}" for index in range(1, FROZEN_CALIBRATION_V0_1_CASE_COUNT + 1)
    )
    actual_ids = tuple(
        row.get("example_id") if isinstance(row, Mapping) else None
        for row in rows
    )
    for offset, expected in enumerate(expected_ids):
        if offset >= len(actual_ids):
            break
        if actual_ids[offset] != expected:
            issues.append(
                TeacherGoldValidationIssue(
                    row_number=offset + 2,
                    case_id=actual_ids[offset] if isinstance(actual_ids[offset], str) else None,
                    code="snapshot_case_sequence",
                    field="example_id",
                    message=f"expected {expected} at frozen snapshot position {offset + 1}",
                )
            )

    return TeacherGoldValidationReport(
        row_count=report.row_count,
        valid_row_count=report.valid_row_count,
        issues=tuple(issues),
    )


def build_frozen_calibration_reference_cases(
    rows: Sequence[Mapping[str, object]],
) -> tuple[TeacherGoldReferenceCase, ...]:
    """Build all 100 reference cases only when the full frozen source is structurally valid."""

    report = validate_frozen_calibration_reference_v0_1(rows)
    if not report.is_valid:
        first = report.issues[0]
        raise _error(
            "validation_failed",
            first.field,
            f"teacher-gold reference rows failed validation: {first.code}: {first.message}",
        )
    return tuple(
        adapt_teacher_gold_reference_row(row, split=BenchmarkSplit.CALIBRATION)
        for row in rows
    )


def summarize_teacher_gold_reference_coverage(
    cases: Sequence[TeacherGoldReferenceCase],
) -> TeacherGoldReferenceCoverage:
    """Report executable vs reference-only coverage without hiding partial truth."""

    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes, bytearray)):
        raise TypeError("cases must be a sequence of TeacherGoldReferenceCase values")
    if any(not isinstance(item, TeacherGoldReferenceCase) for item in cases):
        raise TypeError("cases must contain TeacherGoldReferenceCase values")

    ids = tuple(item.case_id for item in cases)
    if len(set(ids)) != len(ids):
        raise ValueError("reference case ids must be unique")
    if tuple(sorted(ids)) != ids:
        raise ValueError("reference cases must use canonical case_id order")

    reference_only = tuple(item for item in cases if not item.is_engine_executable)
    labels = tuple(
        sorted(
            {
                candidate.label
                for item in reference_only
                for candidate in item.expected_candidates
                if not candidate.is_engine_representable
            }
        )
    )
    return TeacherGoldReferenceCoverage(
        case_count=len(cases),
        executable_case_count=len(cases) - len(reference_only),
        reference_only_case_count=len(reference_only),
        reference_only_case_ids=tuple(item.case_id for item in reference_only),
        reference_only_labels=labels,
    )
