"""Non-authoritative QC for proposed Teacher Gold holdout candidates.

This module checks whether the DRAFT TG-0101..TG-0200 proposal is ready for
human musical review. It does not mark rows VERIFIED, freeze the holdout, score
runtime output, or change resolver/model authority.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .calibration import BenchmarkSplit
from .teacher_gold_adapter import (
    TeacherGoldAdapterError,
    TeacherGoldValidationIssue,
    note_name_to_midi,
)
from .teacher_gold_holdout import (
    HOLDOUT_V0_1_CASE_COUNT,
    validate_holdout_template_v0_1,
)
from .teacher_gold_reference import adapt_teacher_gold_reference_row


@dataclass(frozen=True, slots=True)
class HoldoutPitchClassOverlap:
    calibration_case_id: str
    holdout_case_id: str
    pitch_classes: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class HoldoutCandidateQCReport:
    row_count: int
    candidate_ready_count: int
    draft_count: int
    verified_count: int
    state_counts: tuple[tuple[str, int], ...]
    reference_only_case_ids: tuple[str, ...]
    overlaps: tuple[HoldoutPitchClassOverlap, ...]
    issues: tuple[TeacherGoldValidationIssue, ...]

    @property
    def is_review_ready(self) -> bool:
        return (
            self.row_count == HOLDOUT_V0_1_CASE_COUNT
            and self.candidate_ready_count == HOLDOUT_V0_1_CASE_COUNT
            and self.draft_count + self.verified_count == self.row_count
            and not self.overlaps
            and not self.issues
        )


def _issue(
    *,
    row_number: int | None,
    case_id: str | None,
    code: str,
    field: str,
    message: str,
) -> TeacherGoldValidationIssue:
    return TeacherGoldValidationIssue(row_number, case_id, code, field, message)


def _case_id(row: Mapping[str, object]) -> str | None:
    value = row.get("example_id")
    return value if isinstance(value, str) else None


def normalized_pitch_classes(input_notes: object) -> tuple[int, ...]:
    """Return canonical sounding pitch classes for one comma-separated note list."""

    if not isinstance(input_notes, str):
        raise TypeError("input_notes must be a str")
    if not input_notes or input_notes != input_notes.strip():
        raise TeacherGoldAdapterError(
            "invalid_note_list", "input_notes", "input_notes must be canonical non-empty text"
        )
    tokens = tuple(input_notes.split(","))
    if any(not token for token in tokens):
        raise TeacherGoldAdapterError(
            "invalid_note_list", "input_notes", "input_notes must be a comma-separated note list"
        )
    return tuple(sorted({note_name_to_midi(token) % 12 for token in tokens}))


def find_calibration_holdout_pitch_class_overlaps(
    calibration_rows: Sequence[Mapping[str, object]],
    holdout_rows: Sequence[Mapping[str, object]],
) -> tuple[HoldoutPitchClassOverlap, ...]:
    """Find octave/enharmonic-insensitive pitch-class-set reuse across the split boundary."""

    if not isinstance(calibration_rows, Sequence) or isinstance(
        calibration_rows, (str, bytes, bytearray)
    ):
        raise TypeError("calibration_rows must be a sequence of mappings")
    if not isinstance(holdout_rows, Sequence) or isinstance(
        holdout_rows, (str, bytes, bytearray)
    ):
        raise TypeError("holdout_rows must be a sequence of mappings")

    calibration_index: dict[tuple[int, ...], list[str]] = {}
    for row in calibration_rows:
        if not isinstance(row, Mapping):
            raise TypeError("calibration_rows must contain mappings")
        case_id = _case_id(row)
        notes = row.get("input_notes")
        if case_id is None or not isinstance(notes, str) or not notes:
            continue
        pcs = normalized_pitch_classes(notes)
        calibration_index.setdefault(pcs, []).append(case_id)

    overlaps: list[HoldoutPitchClassOverlap] = []
    for row in holdout_rows:
        if not isinstance(row, Mapping):
            raise TypeError("holdout_rows must contain mappings")
        holdout_case_id = _case_id(row)
        notes = row.get("input_notes")
        if holdout_case_id is None or not isinstance(notes, str) or not notes:
            continue
        pcs = normalized_pitch_classes(notes)
        for calibration_case_id in calibration_index.get(pcs, ()):  # deterministic source order
            overlaps.append(HoldoutPitchClassOverlap(calibration_case_id, holdout_case_id, pcs))
    return tuple(sorted(overlaps, key=lambda item: (item.holdout_case_id, item.calibration_case_id)))


def validate_holdout_candidate_review_v0_1(
    rows: Sequence[Mapping[str, object]],
    *,
    calibration_rows: Sequence[Mapping[str, object]] = (),
) -> HoldoutCandidateQCReport:
    """Validate complete DRAFT proposals without promoting them to gold truth."""

    template = validate_holdout_template_v0_1(rows)
    issues = list(template.issues)
    candidate_ready_count = 0
    reference_only_case_ids: list[str] = []
    state_counter: Counter[str] = Counter()

    for index, row in enumerate(rows, start=2):
        if not isinstance(row, Mapping):
            continue
        case_id = _case_id(row)
        state = row.get("expected_state")
        if isinstance(state, str) and state:
            state_counter[state] += 1

        # Human review candidates remain DRAFT in the source. A private surrogate
        # status is used only to reuse the full reference validator; it is never
        # returned, written, scored, or treated as adjudication.
        surrogate = dict(row)
        surrogate["annotation_status"] = "VERIFIED"
        try:
            adapted = adapt_teacher_gold_reference_row(surrogate, split=BenchmarkSplit.HOLDOUT)
            candidate_ready_count += 1
            if not adapted.is_engine_executable and case_id is not None:
                reference_only_case_ids.append(case_id)
        except TeacherGoldAdapterError as exc:
            issues.append(
                _issue(
                    row_number=index,
                    case_id=case_id,
                    code="candidate_" + exc.code,
                    field=exc.field,
                    message=str(exc),
                )
            )

    overlaps = find_calibration_holdout_pitch_class_overlaps(calibration_rows, rows)
    for overlap in overlaps:
        issues.append(
            _issue(
                row_number=None,
                case_id=overlap.holdout_case_id,
                code="calibration_pitch_class_overlap",
                field="input_notes",
                message=(
                    f"{overlap.holdout_case_id} reuses pitch-class set {overlap.pitch_classes} "
                    f"from {overlap.calibration_case_id}"
                ),
            )
        )

    return HoldoutCandidateQCReport(
        row_count=len(rows),
        candidate_ready_count=candidate_ready_count,
        draft_count=template.draft_count,
        verified_count=template.verified_count,
        state_counts=tuple(sorted(state_counter.items())),
        reference_only_case_ids=tuple(sorted(set(reference_only_case_ids))),
        overlaps=overlaps,
        issues=tuple(issues),
    )
