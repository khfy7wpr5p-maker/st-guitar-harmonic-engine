"""Leakage-resistant Teacher Gold holdout v0.1 contract.

This module governs the separate TG-0101..TG-0200 holdout namespace. It allows
DRAFT rows to remain incomplete during human annotation, but refuses to build a
frozen holdout until every row is VERIFIED and reference-valid. No resolver,
model, or runtime authority is changed here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .calibration import BenchmarkSplit
from .teacher_gold_adapter import (
    TEACHER_GOLD_SHEET_COLUMNS,
    TeacherGoldAdapterError,
    TeacherGoldValidationIssue,
)
from .teacher_gold_reference import (
    TeacherGoldReferenceCase,
    adapt_teacher_gold_reference_row,
)


HOLDOUT_V0_1_FIRST_CASE = 101
HOLDOUT_V0_1_LAST_CASE = 200
HOLDOUT_V0_1_CASE_COUNT = 100
HOLDOUT_V0_1_CASE_IDS: tuple[str, ...] = tuple(
    f"TG-{index:04d}" for index in range(HOLDOUT_V0_1_FIRST_CASE, HOLDOUT_V0_1_LAST_CASE + 1)
)


@dataclass(frozen=True, slots=True)
class TeacherGoldHoldoutReport:
    row_count: int
    draft_count: int
    verified_count: int
    issues: tuple[TeacherGoldValidationIssue, ...]

    def __post_init__(self) -> None:
        for name in ("row_count", "draft_count", "verified_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an int")
            if value < 0:
                raise ValueError(f"{name} must not be negative")
        if self.draft_count + self.verified_count > self.row_count:
            raise ValueError("status counts must not exceed row_count")
        if not isinstance(self.issues, tuple) or any(
            not isinstance(item, TeacherGoldValidationIssue) for item in self.issues
        ):
            raise TypeError("issues must contain TeacherGoldValidationIssue values")

    @property
    def is_template_valid(self) -> bool:
        return (
            not self.issues
            and self.row_count == HOLDOUT_V0_1_CASE_COUNT
            and self.draft_count + self.verified_count == self.row_count
        )

    @property
    def is_freeze_ready(self) -> bool:
        return self.is_template_valid and self.verified_count == HOLDOUT_V0_1_CASE_COUNT


def _issue(
    *,
    row_number: int | None,
    case_id: str | None,
    code: str,
    field: str,
    message: str,
) -> TeacherGoldValidationIssue:
    return TeacherGoldValidationIssue(row_number, case_id, code, field, message)


def _row_case_id(row: object) -> str | None:
    if not isinstance(row, Mapping):
        return None
    value = row.get("example_id")
    return value if isinstance(value, str) else None


def _validate_draft_shape(row: Mapping[str, object], *, row_number: int) -> list[TeacherGoldValidationIssue]:
    issues: list[TeacherGoldValidationIssue] = []
    case_id = _row_case_id(row)
    if set(row) != set(TEACHER_GOLD_SHEET_COLUMNS):
        missing = sorted(set(TEACHER_GOLD_SHEET_COLUMNS) - set(row))
        extra = sorted(set(row) - set(TEACHER_GOLD_SHEET_COLUMNS))
        issues.append(
            _issue(
                row_number=row_number,
                case_id=case_id,
                code="schema_mismatch",
                field="row",
                message=f"row columns do not match v0.1 schema; missing={missing}, extra={extra}",
            )
        )
        return issues

    for field in TEACHER_GOLD_SHEET_COLUMNS:
        value = row[field]
        if value is None:
            continue
        if not isinstance(value, str):
            issues.append(
                _issue(
                    row_number=row_number,
                    case_id=case_id,
                    code="invalid_type",
                    field=field,
                    message=f"{field} must be a string or blank",
                )
            )
        elif value != value.strip():
            issues.append(
                _issue(
                    row_number=row_number,
                    case_id=case_id,
                    code="noncanonical_text",
                    field=field,
                    message=f"{field} must not have surrounding whitespace",
                )
            )
    return issues


def validate_holdout_template_v0_1(
    rows: Sequence[Mapping[str, object]],
) -> TeacherGoldHoldoutReport:
    """Validate the exact 100-row holdout namespace while permitting DRAFT work.

    VERIFIED rows must already satisfy the full reference contract. DRAFT rows may
    remain blank or partially annotated, but their schema, IDs, status, and value
    types remain bounded.
    """

    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        raise TypeError("rows must be a sequence of mappings")

    issues: list[TeacherGoldValidationIssue] = []
    draft_count = 0
    verified_count = 0

    if len(rows) != HOLDOUT_V0_1_CASE_COUNT:
        issues.append(
            _issue(
                row_number=None,
                case_id=None,
                code="holdout_case_count",
                field="rows",
                message=f"holdout v0.1 requires exactly {HOLDOUT_V0_1_CASE_COUNT} rows",
            )
        )

    for offset, row in enumerate(rows):
        row_number = offset + 2
        expected_id = (
            HOLDOUT_V0_1_CASE_IDS[offset]
            if offset < len(HOLDOUT_V0_1_CASE_IDS)
            else None
        )
        case_id = _row_case_id(row)

        if not isinstance(row, Mapping):
            issues.append(
                _issue(
                    row_number=row_number,
                    case_id=None,
                    code="invalid_row_type",
                    field="row",
                    message="teacher-gold holdout row must be a mapping",
                )
            )
            continue

        shape_issues = _validate_draft_shape(row, row_number=row_number)
        issues.extend(shape_issues)
        if shape_issues:
            continue

        if expected_id is None or case_id != expected_id:
            issues.append(
                _issue(
                    row_number=row_number,
                    case_id=case_id,
                    code="holdout_case_sequence",
                    field="example_id",
                    message=f"expected {expected_id!r} at holdout position {offset + 1}",
                )
            )

        status = row["annotation_status"]
        if status == "DRAFT":
            draft_count += 1
            continue
        if status == "VERIFIED":
            verified_count += 1
            try:
                adapt_teacher_gold_reference_row(row, split=BenchmarkSplit.HOLDOUT)
            except TeacherGoldAdapterError as exc:
                issues.append(
                    _issue(
                        row_number=row_number,
                        case_id=case_id,
                        code=exc.code,
                        field=exc.field,
                        message=str(exc),
                    )
                )
            continue

        issues.append(
            _issue(
                row_number=row_number,
                case_id=case_id,
                code="invalid_annotation_status",
                field="annotation_status",
                message="holdout annotation_status must be DRAFT or VERIFIED",
            )
        )

    return TeacherGoldHoldoutReport(
        row_count=len(rows),
        draft_count=draft_count,
        verified_count=verified_count,
        issues=tuple(issues),
    )


def build_frozen_holdout_reference_v0_1(
    rows: Sequence[Mapping[str, object]],
) -> tuple[TeacherGoldReferenceCase, ...]:
    """Build the untouched holdout only after 100/100 rows are human VERIFIED."""

    report = validate_holdout_template_v0_1(rows)
    if not report.is_freeze_ready:
        if report.issues:
            first = report.issues[0]
            detail = f"{first.code}: {first.message}"
            field = first.field
        else:
            detail = (
                f"holdout is not freeze-ready: {report.verified_count}/"
                f"{HOLDOUT_V0_1_CASE_COUNT} rows are VERIFIED"
            )
            field = "annotation_status"
        raise TeacherGoldAdapterError("holdout_not_freeze_ready", field, detail)

    return tuple(
        adapt_teacher_gold_reference_row(row, split=BenchmarkSplit.HOLDOUT)
        for row in rows
    )


def assert_disjoint_calibration_holdout_ids(
    calibration_case_ids: Sequence[str],
    holdout_case_ids: Sequence[str] = HOLDOUT_V0_1_CASE_IDS,
) -> None:
    """Fail closed if calibration and holdout identifiers overlap."""

    if not isinstance(calibration_case_ids, Sequence) or isinstance(
        calibration_case_ids, (str, bytes, bytearray)
    ):
        raise TypeError("calibration_case_ids must be a sequence of strings")
    if not isinstance(holdout_case_ids, Sequence) or isinstance(
        holdout_case_ids, (str, bytes, bytearray)
    ):
        raise TypeError("holdout_case_ids must be a sequence of strings")
    if any(not isinstance(item, str) for item in calibration_case_ids):
        raise TypeError("calibration_case_ids must contain strings")
    if any(not isinstance(item, str) for item in holdout_case_ids):
        raise TypeError("holdout_case_ids must contain strings")

    overlap = tuple(sorted(set(calibration_case_ids) & set(holdout_case_ids)))
    if overlap:
        raise ValueError(f"calibration and holdout ids must be disjoint; overlap={overlap}")
