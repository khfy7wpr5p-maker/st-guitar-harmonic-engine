"""Fail-closed adapter for frozen Teacher Gold calibration Sheet v0.1.

This module converts the human-maintained eight-column calibration rows into the
existing Stage 4-G ``TeacherGoldCase`` contract and Stage 7 public-request schema.
It performs no file/network I/O and never changes harmonic resolver authority.

The adapter intentionally rejects human chord labels that the frozen
``HarmonicIdentity`` vocabulary cannot represent instead of silently coercing or
dropping teacher-gold information.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re
from typing import Any

from .abstention import FinalDecisionState
from .calibration import BenchmarkSplit, TeacherGoldBenchmark, TeacherGoldCase
from .public_api import PUBLIC_API_SCHEMA_NAME, PUBLIC_API_SCHEMA_VERSION, validate_public_request
from .resolver import CandidateFamily, HarmonicIdentity


TEACHER_GOLD_SHEET_SCHEMA_VERSION = "0.1"
TEACHER_GOLD_SHEET_COLUMNS: tuple[str, ...] = (
    "example_id",
    "input_notes",
    "expected_state",
    "primary_candidate",
    "acceptable_alternatives",
    "inversion",
    "teacher_reason",
    "annotation_status",
)
FROZEN_CALIBRATION_V0_1_CASE_COUNT = 100

_INVERSION_VALUES = frozenset(
    {
        "root_position",
        "first_inversion",
        "second_inversion",
        "third_inversion",
    }
)
_NOTE_RE = re.compile(r"^(?P<letter>[A-G])(?P<accidental>[#b]?)(?P<octave>-?\d+)$")
_PITCH_CLASS_RE = re.compile(r"^(?P<letter>[A-G])(?P<accidental>[#b]?)$")
_EXAMPLE_ID_RE = re.compile(r"^TG-\d{4}$")
_BASE_PITCH_CLASSES = {
    "C": 0,
    "D": 2,
    "E": 4,
    "F": 5,
    "G": 7,
    "A": 9,
    "B": 11,
}


class TeacherGoldAdapterError(ValueError):
    """One fail-closed row/schema adaptation error."""

    def __init__(self, code: str, field: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.field = field


@dataclass(frozen=True, slots=True)
class AdaptedTeacherGoldCase:
    """Teacher-gold identity plus public request and preserved review metadata."""

    gold_case: TeacherGoldCase
    public_request: dict[str, Any]
    expected_inversion: str | None
    teacher_reason: str


@dataclass(frozen=True, slots=True)
class TeacherGoldValidationIssue:
    row_number: int | None
    case_id: str | None
    code: str
    field: str
    message: str


@dataclass(frozen=True, slots=True)
class TeacherGoldValidationReport:
    row_count: int
    valid_row_count: int
    issues: tuple[TeacherGoldValidationIssue, ...]

    @property
    def is_valid(self) -> bool:
        return not self.issues and self.valid_row_count == self.row_count


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


def _pitch_class(name: str, *, field: str) -> int:
    match = _PITCH_CLASS_RE.fullmatch(name)
    if match is None:
        raise _error("invalid_pitch_class", field, f"{field} contains an invalid pitch-class name")
    pitch_class = _BASE_PITCH_CLASSES[match.group("letter")]
    accidental = match.group("accidental")
    if accidental == "#":
        pitch_class += 1
    elif accidental == "b":
        pitch_class -= 1
    return pitch_class % 12


def note_name_to_midi(note_name: str) -> int:
    """Convert canonical scientific-pitch notation to MIDI, including #/b."""

    if not isinstance(note_name, str):
        raise TypeError("note_name must be a str")
    match = _NOTE_RE.fullmatch(note_name)
    if match is None:
        raise _error("invalid_note", "input_notes", f"unsupported note token: {note_name!r}")
    pitch_class = _pitch_class(
        f"{match.group('letter')}{match.group('accidental')}",
        field="input_notes",
    )
    octave = int(match.group("octave"))
    midi = (octave + 1) * 12 + pitch_class
    if not 0 <= midi <= 127:
        raise _error("midi_out_of_range", "input_notes", f"note is outside MIDI range: {note_name!r}")
    return midi


def _parse_input_notes(value: object) -> tuple[tuple[str, int], ...]:
    text = _text(value, field="input_notes", required=True)
    tokens = tuple(text.split(","))
    if not tokens or any(not token for token in tokens):
        raise _error("invalid_note_list", "input_notes", "input_notes must be a comma-separated note list")
    return tuple((token, note_name_to_midi(token)) for token in tokens)


def _split_slash_bass(label: str) -> str:
    if "/" not in label:
        return label
    if label.count("/") != 1:
        raise _error("unsupported_identity", "candidate", f"unsupported chord label: {label!r}")
    base, bass = label.rsplit("/", 1)
    if not base or not bass:
        raise _error("unsupported_identity", "candidate", f"unsupported chord label: {label!r}")
    _pitch_class(bass, field="candidate")
    return base


def _root_and_suffix(label: str) -> tuple[int, str]:
    match = re.fullmatch(r"(?P<root>[A-G](?:#|b)?)(?P<suffix>.*)", label)
    if match is None:
        raise _error("unsupported_identity", "candidate", f"unsupported chord label: {label!r}")
    return _pitch_class(match.group("root"), field="candidate"), match.group("suffix")


def parse_teacher_candidate_identity(label: str) -> HarmonicIdentity:
    """Map one supported human chord label to the frozen engine identity vocabulary."""

    if not isinstance(label, str):
        raise TypeError("label must be a str")
    if not label or label != label.strip():
        raise _error("unsupported_identity", "candidate", "candidate label must be canonical non-empty text")

    base_label = _split_slash_bass(label)

    for suffix, variant in (
        (" major", "major"),
        (" minor", "minor"),
        (" diminished", "diminished"),
        (" augmented", "augmented"),
    ):
        if base_label.endswith(suffix):
            root_name = base_label[: -len(suffix)]
            root_pc = _pitch_class(root_name, field="candidate")
            return HarmonicIdentity(root_pc, CandidateFamily.BASIC, variant)

    root_pc, suffix = _root_and_suffix(base_label)

    altered_variants = {
        "7b9": "dominant_seventh:flat_ninth",
        "7#9": "dominant_seventh:sharp_ninth",
        "7#11": "dominant_seventh:sharp_eleventh",
        "7b13": "dominant_seventh:flat_thirteenth",
    }
    if suffix in altered_variants:
        return HarmonicIdentity(root_pc, CandidateFamily.ALTERED, altered_variants[suffix])

    extension_variants = {
        "add9": "major:natural_ninth",
        "madd9": "minor:natural_ninth",
        "add11": "major:natural_eleventh",
        "9": "dominant_seventh:natural_ninth",
        "maj9": "major_seventh:natural_ninth",
        "7(add11)": "dominant_seventh:natural_eleventh",
        "7(add13)": "dominant_seventh:natural_thirteenth",
        "maj7(add11)": "major_seventh:natural_eleventh",
    }
    if suffix in extension_variants:
        return HarmonicIdentity(root_pc, CandidateFamily.EXTENSION, extension_variants[suffix])

    suspended_variants = {"sus2": "sus2", "sus4": "sus4"}
    if suffix in suspended_variants:
        return HarmonicIdentity(root_pc, CandidateFamily.SUSPENDED, suspended_variants[suffix])

    basic_variants = {
        "7": "dominant_seventh",
        "maj7": "major_seventh",
        "m7": "minor_seventh",
        "m7b5": "half_diminished_seventh",
        "dim7": "diminished_seventh",
    }
    if suffix in basic_variants:
        return HarmonicIdentity(root_pc, CandidateFamily.BASIC, basic_variants[suffix])

    if suffix in {"6", "m6", "7sus2", "7sus4"}:
        raise _error(
            "unsupported_identity",
            "candidate",
            f"{label!r} is musically valid teacher-gold text but is not representable "
            "by the frozen HarmonicIdentity vocabulary",
        )
    raise _error("unsupported_identity", "candidate", f"unsupported chord label: {label!r}")


def _validate_row_shape(row: Mapping[str, object]) -> None:
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


def _state(value: object) -> FinalDecisionState:
    text = _text(value, field="expected_state", required=True)
    if text not in {"RESOLVED", "AMBIGUOUS", "ABSTAIN", "NO_MATCH"}:
        raise _error("invalid_state", "expected_state", f"unsupported expected_state: {text!r}")
    return FinalDecisionState(text.lower())


def _parse_alternatives(text: str) -> tuple[HarmonicIdentity, ...]:
    parts = tuple(text.split(" | "))
    if len(parts) < 2 or any(not part for part in parts):
        raise _error(
            "invalid_alternatives",
            "acceptable_alternatives",
            "AMBIGUOUS rows require at least two candidates separated by ' | '",
        )
    identities = tuple(parse_teacher_candidate_identity(part) for part in parts)
    if len(set(identities)) != len(identities):
        raise _error(
            "duplicate_identity",
            "acceptable_alternatives",
            "acceptable alternatives collapse to duplicate harmonic identities",
        )
    return tuple(sorted(identities))


def _public_request(case_id: str, parsed_notes: tuple[tuple[str, int], ...]) -> dict[str, Any]:
    events = [
        {
            "staff": 1,
            "voice": index + 1,
            "midi_pitch": midi,
            "onset": {"numerator": 0, "denominator": 1},
            "duration": {"numerator": 1, "denominator": 1},
            "tie": "none",
        }
        for index, (_, midi) in enumerate(parsed_notes)
    ]
    payload: dict[str, Any] = {
        "schema_name": PUBLIC_API_SCHEMA_NAME,
        "schema_version": PUBLIC_API_SCHEMA_VERSION,
        "mode": "batch",
        "frames": [
            {
                "measure_number": 1,
                "start": {"numerator": 0, "denominator": 1},
                "end": {"numerator": 1, "denominator": 1},
                "events": events,
            }
        ],
        "phrase_spans": None,
    }
    try:
        validate_public_request(payload)
    except (TypeError, ValueError) as exc:
        raise _error(
            "public_request_incompatible",
            "input_notes",
            f"{case_id} could not be represented by public request schema v1.0",
        ) from exc
    return payload


def adapt_teacher_gold_row(
    row: Mapping[str, object],
    *,
    split: BenchmarkSplit = BenchmarkSplit.CALIBRATION,
) -> AdaptedTeacherGoldCase:
    """Adapt one verified v0.1 row without changing any resolver decision semantics."""

    if not isinstance(split, BenchmarkSplit):
        raise TypeError("split must be a BenchmarkSplit")
    _validate_row_shape(row)

    case_id = _text(row["example_id"], field="example_id", required=True)
    if _EXAMPLE_ID_RE.fullmatch(case_id) is None:
        raise _error("invalid_case_id", "example_id", "example_id must match TG-0000 format")

    annotation_status = _text(row["annotation_status"], field="annotation_status", required=True)
    if annotation_status != "VERIFIED":
        raise _error(
            "unverified_row",
            "annotation_status",
            "only VERIFIED teacher-gold rows may enter the benchmark adapter",
        )

    state = _state(row["expected_state"])
    primary = _text(row["primary_candidate"], field="primary_candidate")
    alternatives = _text(row["acceptable_alternatives"], field="acceptable_alternatives")
    inversion = _text(row["inversion"], field="inversion")
    reason = _text(row["teacher_reason"], field="teacher_reason", required=True)
    parsed_notes = _parse_input_notes(row["input_notes"])

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
        acceptable_identities = (parse_teacher_candidate_identity(primary),)
    elif state is FinalDecisionState.AMBIGUOUS:
        if primary or not alternatives:
            raise _error(
                "candidate_cardinality",
                "acceptable_alternatives",
                "AMBIGUOUS rows require blank primary_candidate and explicit alternatives",
            )
        if inversion:
            raise _error("invalid_inversion", "inversion", "AMBIGUOUS rows must leave inversion blank")
        acceptable_identities = _parse_alternatives(alternatives)
    else:
        if primary or alternatives:
            raise _error(
                "candidate_cardinality",
                "primary_candidate",
                "ABSTAIN/NO_MATCH rows must not claim candidate identities",
            )
        if inversion:
            raise _error("invalid_inversion", "inversion", "ABSTAIN/NO_MATCH rows must leave inversion blank")
        acceptable_identities = ()

    gold_case = TeacherGoldCase(
        case_id=case_id,
        split=split,
        expected_state=state,
        acceptable_identities=tuple(sorted(acceptable_identities)),
    )
    return AdaptedTeacherGoldCase(
        gold_case=gold_case,
        public_request=_public_request(case_id, parsed_notes),
        expected_inversion=inversion or None,
        teacher_reason=reason,
    )


def validate_teacher_gold_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    split: BenchmarkSplit = BenchmarkSplit.CALIBRATION,
) -> TeacherGoldValidationReport:
    """Collect all row-level adapter failures without weakening fail-closed behavior."""

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
            adapted = adapt_teacher_gold_row(row, split=split)
            case_id = adapted.gold_case.case_id
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


def validate_frozen_calibration_v0_1(
    rows: Sequence[Mapping[str, object]],
) -> TeacherGoldValidationReport:
    """Validate exact TG-0001..TG-0100 snapshot shape plus row compatibility."""

    report = validate_teacher_gold_rows(rows, split=BenchmarkSplit.CALIBRATION)
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


def build_teacher_gold_benchmark(
    rows: Sequence[Mapping[str, object]],
    *,
    split: BenchmarkSplit = BenchmarkSplit.CALIBRATION,
) -> TeacherGoldBenchmark:
    """Build a benchmark only when every supplied row adapts successfully."""

    report = validate_teacher_gold_rows(rows, split=split)
    if not report.is_valid:
        first = report.issues[0]
        raise _error(
            "validation_failed",
            first.field,
            f"teacher-gold rows failed validation: {first.code}: {first.message}",
        )
    adapted = tuple(adapt_teacher_gold_row(row, split=split) for row in rows)
    return TeacherGoldBenchmark(tuple(item.gold_case for item in adapted))
