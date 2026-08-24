import unittest

from st_guitar_harmonic_engine.aggregator import aggregate_frame_evidence
from st_guitar_harmonic_engine.frames import HarmonicFrame
from st_guitar_harmonic_engine.models import NoteEvent, RationalBeat, TieState
from st_guitar_harmonic_engine.resolver import CandidateFamily, HarmonicIdentity
from st_guitar_harmonic_engine.teacher_gold_adapter import TeacherGoldAdapterError
from st_guitar_harmonic_engine.teacher_gold_reference import adapt_teacher_gold_reference_row
from st_guitar_harmonic_engine.teacher_gold_vocabulary_v0_2 import (
    parse_teacher_candidate_identity_v0_2,
)
from st_guitar_harmonic_engine.teacher_gold_vocabulary_v0_3 import (
    TEACHER_GOLD_VOCABULARY_VERSION_V0_3,
    adapt_teacher_gold_reference_row_v0_3,
    parse_teacher_candidate_identity_v0_3,
    summarize_teacher_gold_reference_coverage_v0_3,
    upgrade_reference_case_v0_3,
)


def row(
    case_id="TG-0009",
    notes="C3,E3,G3,A3",
    state="AMBIGUOUS",
    primary="",
    alternatives="C6 | Am7/C",
    inversion="",
):
    return {
        "example_id": case_id,
        "input_notes": notes,
        "expected_state": state,
        "primary_candidate": primary,
        "acceptable_alternatives": alternatives,
        "inversion": inversion,
        "teacher_reason": "Verified teacher reason.",
        "annotation_status": "VERIFIED",
    }


def frame(*pitches):
    return HarmonicFrame(
        1,
        RationalBeat(0),
        RationalBeat(1),
        tuple(
            NoteEvent(
                measure_number=1,
                staff=1,
                voice=index + 1,
                midi_pitch=pitch,
                onset=RationalBeat(0),
                duration=RationalBeat(1),
                tie=TieState.NONE,
            )
            for index, pitch in enumerate(pitches)
        ),
    )


class TeacherGoldVocabularyV03Tests(unittest.TestCase):
    def test_version_is_explicit(self):
        self.assertEqual(TEACHER_GOLD_VOCABULARY_VERSION_V0_3, "0.3")

    def test_v0_3_maps_major_and_minor_sixth_labels(self):
        self.assertEqual(
            parse_teacher_candidate_identity_v0_3("C6"),
            HarmonicIdentity(0, CandidateFamily.BASIC, "major_sixth"),
        )
        self.assertEqual(
            parse_teacher_candidate_identity_v0_3("Dm6/A"),
            HarmonicIdentity(2, CandidateFamily.BASIC, "minor_sixth"),
        )

    def test_v0_2_remains_frozen_and_rejects_sixth_labels(self):
        with self.assertRaises(TeacherGoldAdapterError):
            parse_teacher_candidate_identity_v0_2("C6")

    def test_ambiguous_major_sixth_reference_becomes_fully_executable(self):
        legacy = adapt_teacher_gold_reference_row(row())
        self.assertFalse(legacy.is_engine_executable)
        upgraded = upgrade_reference_case_v0_3(legacy)
        self.assertTrue(upgraded.is_engine_executable)
        self.assertEqual(
            {candidate.engine_identity for candidate in upgraded.expected_candidates},
            {
                HarmonicIdentity(0, CandidateFamily.BASIC, "major_sixth"),
                HarmonicIdentity(9, CandidateFamily.BASIC, "minor_seventh"),
            },
        )

    def test_minor_sixth_reference_becomes_fully_executable(self):
        upgraded = adapt_teacher_gold_reference_row_v0_3(
            row(
                case_id="TG-0019",
                notes="D3,F3,A3,B3",
                alternatives="Dm6 | Bm7b5/D",
            )
        )
        self.assertTrue(upgraded.is_engine_executable)
        self.assertEqual(
            {candidate.engine_identity for candidate in upgraded.expected_candidates},
            {
                HarmonicIdentity(2, CandidateFamily.BASIC, "minor_sixth"),
                HarmonicIdentity(11, CandidateFamily.BASIC, "half_diminished_seventh"),
            },
        )

    def test_runtime_collision_identities_match_teacher_v0_3(self):
        runtime = {item.identity for item in aggregate_frame_evidence(frame(48, 52, 55, 57))}
        teacher = {
            parse_teacher_candidate_identity_v0_3("C6"),
            parse_teacher_candidate_identity_v0_3("Am7/C"),
        }
        self.assertEqual(runtime, teacher)

    def test_coverage_has_no_reference_only_cases_when_only_sixth_gap_remains(self):
        cases = (
            adapt_teacher_gold_reference_row(row(case_id="TG-0009")),
            adapt_teacher_gold_reference_row(
                row(
                    case_id="TG-0019",
                    notes="D3,F3,A3,B3",
                    alternatives="Dm6 | Bm7b5/D",
                )
            ),
        )
        coverage = summarize_teacher_gold_reference_coverage_v0_3(cases)
        self.assertEqual(coverage.case_count, 2)
        self.assertEqual(coverage.executable_case_count, 2)
        self.assertEqual(coverage.reference_only_case_count, 0)
        self.assertEqual(coverage.reference_only_case_ids, ())

    def test_unknown_labels_still_fail_closed(self):
        for label in ("Cfoobar", "H6", "C6/H", "C13"):
            with self.subTest(label=label):
                with self.assertRaises((TeacherGoldAdapterError, TypeError, ValueError)):
                    parse_teacher_candidate_identity_v0_3(label)

    def test_repeated_upgrade_is_deterministic_and_idempotent(self):
        legacy = adapt_teacher_gold_reference_row(row())
        expected = upgrade_reference_case_v0_3(legacy)
        self.assertEqual(upgrade_reference_case_v0_3(expected), expected)
        for _ in range(10):
            self.assertEqual(upgrade_reference_case_v0_3(legacy), expected)


if __name__ == "__main__":
    unittest.main()
