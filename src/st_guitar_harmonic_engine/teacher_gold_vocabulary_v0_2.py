"""Additive Teacher-Gold vocabulary mapping v0.2.

The frozen v0.1 adapters remain unchanged for reproducibility. This layer only
upgrades reference identities that the deterministic runtime can now represent.
At v0.2 the only promoted reference-only labels are complete 7sus2 / 7sus4.
Sixth chords intentionally remain reference-only because their pitch sets collide
with relative m7 / m7b5 identities and cannot be safely resolved from notes alone.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re

from .calibration import BenchmarkSplit
from .resolver import CandidateFamily, HarmonicIdentity
from .teacher_gold_adapter import (
    TeacherGoldAdapterError,
    note_name_to_midi,
    parse_teacher_candidate_identity,
)
from .teacher_gold_benchmark_assembly import (
    TeacherGoldBenchmarkAssembly,
    assemble_frozen_teacher_gold_benchmark_v0_1,
)
from .teacher_gold_reference import (
    TeacherGoldReferenceCandidate,
    TeacherGoldReferenceCase,
    TeacherGoldReferenceCoverage,
    adapt_teacher_gold_reference_row,
    summarize_teacher_gold_reference_coverage,
)


TEACHER_GOLD_VOCABULARY_VERSION_V0_2 = "0.2"
_SUSPENDED_SEVENTH_RE = re.compile(
    r"^(?P<root>[A-G](?:#|b)?)(?P<suffix>7sus2|7sus4)(?:/(?P<bass>[A-G](?:#|b)?))?$"
)


def _pitch_class(name: str) -> int:
    return note_name_to_midi(f"{name}4") % 12


def parse_teacher_candidate_identity_v0_2(label: str) -> HarmonicIdentity:
    """Map a teacher label using v0.1 plus the safely promoted v0.2 vocabulary."""

    try:
        return parse_teacher_candidate_identity(label)
    except TeacherGoldAdapterError as exc:
        if exc.code != "unsupported_identity":
            raise
        match = _SUSPENDED_SEVENTH_RE.fullmatch(label) if isinstance(label, str) else None
        if match is None:
            raise
        bass = match.group("bass")
        if bass is not None:
            _pitch_class(bass)  # validate canonical slash-bass spelling
        return HarmonicIdentity(
            _pitch_class(match.group("root")),
            CandidateFamily.SUSPENDED,
            match.group("suffix"),
        )


def upgrade_reference_candidate_v0_2(
    candidate: TeacherGoldReferenceCandidate,
) -> TeacherGoldReferenceCandidate:
    """Attach an engine identity only when v0.2 can represent the exact label."""

    if not isinstance(candidate, TeacherGoldReferenceCandidate):
        raise TypeError("candidate must be a TeacherGoldReferenceCandidate")
    if candidate.engine_identity is not None:
        return candidate
    try:
        identity = parse_teacher_candidate_identity_v0_2(candidate.label)
    except TeacherGoldAdapterError:
        return candidate
    return TeacherGoldReferenceCandidate(candidate.label, identity)


def upgrade_reference_case_v0_2(
    case: TeacherGoldReferenceCase,
) -> TeacherGoldReferenceCase:
    """Upgrade representability metadata without changing human reference truth."""

    if not isinstance(case, TeacherGoldReferenceCase):
        raise TypeError("case must be a TeacherGoldReferenceCase")
    return TeacherGoldReferenceCase(
        case_id=case.case_id,
        split=case.split,
        expected_state=case.expected_state,
        expected_candidates=tuple(
            upgrade_reference_candidate_v0_2(candidate)
            for candidate in case.expected_candidates
        ),
        public_request=case.public_request,
        expected_inversion=case.expected_inversion,
        teacher_reason=case.teacher_reason,
    )


def upgrade_reference_cases_v0_2(
    cases: Sequence[TeacherGoldReferenceCase],
) -> tuple[TeacherGoldReferenceCase, ...]:
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes, bytearray)):
        raise TypeError("cases must be a sequence")
    return tuple(upgrade_reference_case_v0_2(case) for case in cases)


def adapt_teacher_gold_reference_row_v0_2(
    row: Mapping[str, object],
    *,
    split: BenchmarkSplit = BenchmarkSplit.CALIBRATION,
) -> TeacherGoldReferenceCase:
    """Adapt via frozen v0.1 validation, then upgrade representability metadata."""

    return upgrade_reference_case_v0_2(
        adapt_teacher_gold_reference_row(row, split=split)
    )


def summarize_teacher_gold_reference_coverage_v0_2(
    cases: Sequence[TeacherGoldReferenceCase],
) -> TeacherGoldReferenceCoverage:
    return summarize_teacher_gold_reference_coverage(
        upgrade_reference_cases_v0_2(cases)
    )


def assemble_frozen_teacher_gold_benchmark_v0_2(
    calibration_cases: Sequence[TeacherGoldReferenceCase],
    holdout_cases: Sequence[TeacherGoldReferenceCase],
) -> TeacherGoldBenchmarkAssembly:
    """Upgrade vocabulary metadata, then reuse the frozen v0.1 partition assembly.

    This wrapper does not relax case-count, case-id, split, ordering, partial-
    alternative, or readiness rules. It only makes the vocabulary version used
    for representability explicit at the benchmark entrypoint.
    """

    return assemble_frozen_teacher_gold_benchmark_v0_1(
        upgrade_reference_cases_v0_2(calibration_cases),
        upgrade_reference_cases_v0_2(holdout_cases),
    )
