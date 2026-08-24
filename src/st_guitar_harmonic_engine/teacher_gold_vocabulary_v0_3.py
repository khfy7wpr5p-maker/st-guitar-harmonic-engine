"""Additive Teacher-Gold vocabulary mapping v0.3.

v0.3 preserves all earlier frozen adapters and v0.2 mappings, then promotes
major-sixth and minor-sixth labels only because the deterministic runtime can now
represent their equal-pitch-set collisions explicitly without forcing a root.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re

from .calibration import BenchmarkSplit
from .resolver import CandidateFamily, HarmonicIdentity
from .teacher_gold_adapter import TeacherGoldAdapterError, note_name_to_midi
from .teacher_gold_benchmark_assembly import TeacherGoldBenchmarkAssembly
from .teacher_gold_reference import (
    TeacherGoldReferenceCandidate,
    TeacherGoldReferenceCase,
    TeacherGoldReferenceCoverage,
    adapt_teacher_gold_reference_row,
    summarize_teacher_gold_reference_coverage,
)
from .teacher_gold_vocabulary_v0_2 import (
    assemble_frozen_teacher_gold_benchmark_v0_2,
    parse_teacher_candidate_identity_v0_2,
    upgrade_reference_case_v0_2,
)


TEACHER_GOLD_VOCABULARY_VERSION_V0_3 = "0.3"
_SIXTH_RE = re.compile(
    r"^(?P<root>[A-G](?:#|b)?)(?P<suffix>m6|6)(?:/(?P<bass>[A-G](?:#|b)?))?$"
)


def _pitch_class(name: str) -> int:
    return note_name_to_midi(f"{name}4") % 12


def parse_teacher_candidate_identity_v0_3(label: str) -> HarmonicIdentity:
    """Map v0.2 labels plus safely representable major/minor sixth labels."""

    try:
        return parse_teacher_candidate_identity_v0_2(label)
    except TeacherGoldAdapterError as exc:
        if exc.code != "unsupported_identity":
            raise
        match = _SIXTH_RE.fullmatch(label) if isinstance(label, str) else None
        if match is None:
            raise
        bass = match.group("bass")
        if bass is not None:
            _pitch_class(bass)
        variant = "minor_sixth" if match.group("suffix") == "m6" else "major_sixth"
        return HarmonicIdentity(
            _pitch_class(match.group("root")),
            CandidateFamily.BASIC,
            variant,
        )


def upgrade_reference_candidate_v0_3(
    candidate: TeacherGoldReferenceCandidate,
) -> TeacherGoldReferenceCandidate:
    if not isinstance(candidate, TeacherGoldReferenceCandidate):
        raise TypeError("candidate must be a TeacherGoldReferenceCandidate")
    if candidate.engine_identity is not None:
        return candidate
    try:
        identity = parse_teacher_candidate_identity_v0_3(candidate.label)
    except TeacherGoldAdapterError:
        return candidate
    return TeacherGoldReferenceCandidate(candidate.label, identity)


def upgrade_reference_case_v0_3(
    case: TeacherGoldReferenceCase,
) -> TeacherGoldReferenceCase:
    """Apply v0.2 first, then promote only still-unmapped sixth labels."""

    if not isinstance(case, TeacherGoldReferenceCase):
        raise TypeError("case must be a TeacherGoldReferenceCase")
    base = upgrade_reference_case_v0_2(case)
    return TeacherGoldReferenceCase(
        case_id=base.case_id,
        split=base.split,
        expected_state=base.expected_state,
        expected_candidates=tuple(
            upgrade_reference_candidate_v0_3(candidate)
            for candidate in base.expected_candidates
        ),
        public_request=base.public_request,
        expected_inversion=base.expected_inversion,
        teacher_reason=base.teacher_reason,
    )


def upgrade_reference_cases_v0_3(
    cases: Sequence[TeacherGoldReferenceCase],
) -> tuple[TeacherGoldReferenceCase, ...]:
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes, bytearray)):
        raise TypeError("cases must be a sequence")
    return tuple(upgrade_reference_case_v0_3(case) for case in cases)


def adapt_teacher_gold_reference_row_v0_3(
    row: Mapping[str, object],
    *,
    split: BenchmarkSplit = BenchmarkSplit.CALIBRATION,
) -> TeacherGoldReferenceCase:
    return upgrade_reference_case_v0_3(
        adapt_teacher_gold_reference_row(row, split=split)
    )


def summarize_teacher_gold_reference_coverage_v0_3(
    cases: Sequence[TeacherGoldReferenceCase],
) -> TeacherGoldReferenceCoverage:
    return summarize_teacher_gold_reference_coverage(
        upgrade_reference_cases_v0_3(cases)
    )


def assemble_frozen_teacher_gold_benchmark_v0_3(
    calibration_cases: Sequence[TeacherGoldReferenceCase],
    holdout_cases: Sequence[TeacherGoldReferenceCase],
) -> TeacherGoldBenchmarkAssembly:
    """Upgrade to v0.3, then reuse all frozen partition/readiness guards."""

    return assemble_frozen_teacher_gold_benchmark_v0_2(
        upgrade_reference_cases_v0_3(calibration_cases),
        upgrade_reference_cases_v0_3(holdout_cases),
    )
