import unittest

from st_guitar_harmonic_engine.aggregator import aggregate_frame_evidence
from st_guitar_harmonic_engine.frames import HarmonicFrame
from st_guitar_harmonic_engine.models import NoteEvent, RationalBeat, TieState
from st_guitar_harmonic_engine.resolver import CandidateFamily, HarmonicIdentity
from st_guitar_harmonic_engine.teacher_gold_adapter import TeacherGoldAdapterError
from st_guitar_harmonic_engine.teacher_gold_reference import adapt_teacher_gold_reference_row
from st_guitar_harmonic_engine.teacher_gold_vocabulary_v0_2 import (
    TEACHER_GOLD_VOCABULARY_VERSION_V0_2,
    adapt_teacher_gold_reference_row_v0_2,
    parse_teacher_candidate_identity_v0_2,
    summarize_teacher_gold_reference_coverage_v0_2,
    upgrade_reference_case_v0_2,
)


def row(
    case_id="TG-0026",
    notes="C3,F3,G3,Bb3",
    state="RESOLVED",
    primary="C7sus4",
    alternatives="",
    inversion="root_position",
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


class TeacherGoldVocabularyV02Tests(unittest.TestCase):
    def test_version_is_additive_and_explicit(self):
        self.assertEqual(TEACHER_GOLD_VOCABULARY_VERSION_V0_2, "0.2")

    def test_v0_2_maps_complete_seventh_suspended_labels(self):
        self.assertEqual(
            parse_teacher_candidate_identity_v0_2("C7sus4"),
            HarmonicIdentity(0, CandidateFamily.SUSPENDED, "7sus4"),
        )
        self.assertEqual(
            parse_teacher_candidate_identity_v0_2("D7sus2/A"),
            HarmonicIdentity(2, CandidateFamily.SUSPENDED, "7sus2"),
        )

    def test_runtime_and_teacher_v0_2_identity_are_identical(self):
        runtime = aggregate_frame_evidence(frame(48, 53, 55, 58))
        self.assertEqual(len(runtime), 1)
        self.assertEqual(
            runtime[0].identity,
            parse_teacher_candidate_identity_v0_2("C7sus4"),
        )

    def test_frozen_v0_1_reference_behavior_is_not_mutated(self):
        legacy = adapt_teacher_gold_reference_row(row())
        self.assertIsNone(legacy.expected_candidates[0].engine_identity)
        self.assertFalse(legacy.is_engine_executable)

        upgraded = upgrade_reference_case_v0_2(legacy)
        self.assertEqual(
            upgraded.expected_candidates[0].engine_identity,
            HarmonicIdentity(0, CandidateFamily.SUSPENDED, "7sus4"),
        )
        self.assertTrue(upgraded.is_engine_executable)

    def test_v0_2_row_adapter_reuses_v0_1_validation_then_upgrades_only_identity(self):
        upgraded = adapt_teacher_gold_reference_row_v0_2(row())
        self.assertEqual(upgraded.case_id, "TG-0026")
        self.assertEqual(upgraded.expected_candidates[0].label, "C7sus4")
        self.assertEqual(
            upgraded.expected_candidates[0].engine_identity,
            HarmonicIdentity(0, CandidateFamily.SUSPENDED, "7sus4"),
        )
        self.assertEqual(upgraded.teacher_reason, "Verified teacher reason.")
        self.assertEqual(upgraded.expected_inversion, "root_position")

    def test_sixth_and_minor_sixth_remain_reference_only(self):
        for label in ("C6", "Dm6", "F6/A", "Cm6/Eb"):
            with self.subTest(label=label):
                with self.assertRaises(TeacherGoldAdapterError):
                    parse_teacher_candidate_identity_v0_2(label)

    def test_unknown_labels_still_fail_closed(self):
        for label in ("Cfoobar", "H7sus4", "C7sus9"):
            with self.subTest(label=label):
                with self.assertRaises((TeacherGoldAdapterError, TypeError, ValueError)):
                    parse_teacher_candidate_identity_v0_2(label)

    def test_coverage_changes_only_for_promoted_suspended_seventh_cases(self):
        legacy_7sus = adapt_teacher_gold_reference_row(row(case_id="TG-0001"))
        legacy_sixth = adapt_teacher_gold_reference_row(
            row(
                case_id="TG-0002",
                notes="C3,E3,G3,A3",
                state="AMBIGUOUS",
                primary="",
                alternatives="C6 | Am7/C",
                inversion="",
            )
        )
        coverage = summarize_teacher_gold_reference_coverage_v0_2(
            (legacy_7sus, legacy_sixth)
        )
        self.assertEqual(coverage.case_count, 2)
        self.assertEqual(coverage.executable_case_count, 1)
        self.assertEqual(coverage.reference_only_case_count, 1)
        self.assertEqual(coverage.reference_only_case_ids, ("TG-0002",))
        self.assertEqual(coverage.reference_only_labels, ("C6",))

    def test_repeated_upgrade_is_deterministic_and_idempotent(self):
        legacy = adapt_teacher_gold_reference_row(row())
        expected = upgrade_reference_case_v0_2(legacy)
        self.assertEqual(upgrade_reference_case_v0_2(expected), expected)
        for _ in range(10):
            self.assertEqual(upgrade_reference_case_v0_2(legacy), expected)


if __name__ == "__main__":
    unittest.main()
