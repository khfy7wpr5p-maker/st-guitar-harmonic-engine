import unittest

from st_guitar_harmonic_engine.abstention import FinalDecisionState
from st_guitar_harmonic_engine.public_api import validate_public_request
from st_guitar_harmonic_engine.resolver import CandidateFamily, HarmonicIdentity
from st_guitar_harmonic_engine.teacher_gold_adapter import (
    FROZEN_CALIBRATION_V0_1_CASE_COUNT,
    TeacherGoldAdapterError,
    adapt_teacher_gold_row,
)
from st_guitar_harmonic_engine.teacher_gold_reference import (
    adapt_teacher_gold_reference_row,
    build_frozen_calibration_reference_cases,
    parse_teacher_reference_candidate,
    summarize_teacher_gold_reference_coverage,
    validate_frozen_calibration_reference_v0_1,
    validate_teacher_gold_reference_rows,
)


def row(
    case_id="TG-0001",
    notes="C4,E4,G4",
    state="RESOLVED",
    primary="C major",
    alternatives="",
    inversion="root_position",
    reason="Verified teacher reason.",
    status="VERIFIED",
):
    return {
        "example_id": case_id,
        "input_notes": notes,
        "expected_state": state,
        "primary_candidate": primary,
        "acceptable_alternatives": alternatives,
        "inversion": inversion,
        "teacher_reason": reason,
        "annotation_status": status,
    }


class TeacherGoldReferenceTests(unittest.TestCase):
    def test_supported_label_keeps_frozen_engine_identity(self):
        candidate = parse_teacher_reference_candidate("Cmaj7/E")
        self.assertTrue(candidate.is_engine_representable)
        self.assertEqual(candidate.label, "Cmaj7/E")
        self.assertEqual(
            candidate.engine_identity,
            HarmonicIdentity(0, CandidateFamily.BASIC, "major_seventh"),
        )

    def test_known_vocabulary_gaps_are_preserved_reference_only(self):
        for label in ("C6", "Dm6", "C7sus4", "G7sus4", "C6/E"):
            with self.subTest(label=label):
                candidate = parse_teacher_reference_candidate(label)
                self.assertEqual(candidate.label, label)
                self.assertIsNone(candidate.engine_identity)
                self.assertFalse(candidate.is_engine_representable)

    def test_unknown_label_still_fails_closed(self):
        for label in ("Cfoobar", "C13sus9", "H6", "C6/H"):
            with self.subTest(label=label):
                with self.assertRaises(TeacherGoldAdapterError):
                    parse_teacher_reference_candidate(label)

    def test_existing_authoritative_adapter_still_rejects_reference_only_identity(self):
        with self.assertRaises(TeacherGoldAdapterError) as context:
            adapt_teacher_gold_row(
                row(
                    case_id="TG-0026",
                    notes="C3,F3,G3,Bb3",
                    primary="C7sus4",
                )
            )
        self.assertEqual(context.exception.code, "unsupported_identity")

    def test_reference_adapter_preserves_resolved_gap_without_promoting_identity(self):
        adapted = adapt_teacher_gold_reference_row(
            row(
                case_id="TG-0026",
                notes="C3,F3,G3,Bb3",
                primary="C7sus4",
            )
        )
        self.assertIs(adapted.expected_state, FinalDecisionState.RESOLVED)
        self.assertEqual(tuple(item.label for item in adapted.expected_candidates), ("C7sus4",))
        self.assertIsNone(adapted.expected_candidates[0].engine_identity)
        self.assertFalse(adapted.is_engine_executable)
        validated = validate_public_request(adapted.public_request)
        self.assertEqual(
            tuple(event.midi_pitch for event in validated.frames[0].events),
            (48, 53, 55, 58),
        )

    def test_ambiguous_gap_preserves_full_teacher_truth(self):
        adapted = adapt_teacher_gold_reference_row(
            row(
                case_id="TG-0009",
                notes="C3,E3,G3,A3",
                state="AMBIGUOUS",
                primary="",
                alternatives="C6 | Am7/C",
                inversion="",
            )
        )
        self.assertIs(adapted.expected_state, FinalDecisionState.AMBIGUOUS)
        self.assertEqual(
            tuple(item.label for item in adapted.expected_candidates),
            ("C6", "Am7/C"),
        )
        self.assertIsNone(adapted.expected_candidates[0].engine_identity)
        self.assertEqual(
            adapted.expected_candidates[1].engine_identity,
            HarmonicIdentity(9, CandidateFamily.BASIC, "minor_seventh"),
        )
        self.assertFalse(adapted.is_engine_executable)

    def test_abstain_and_no_match_are_executable_without_identity_vocabulary(self):
        for case_id, state, notes in (
            ("TG-0081", "ABSTAIN", "C3,E3"),
            ("TG-0099", "NO_MATCH", "C3,C#3,D3"),
        ):
            with self.subTest(state=state):
                adapted = adapt_teacher_gold_reference_row(
                    row(
                        case_id=case_id,
                        notes=notes,
                        state=state,
                        primary="",
                        alternatives="",
                        inversion="",
                    )
                )
                self.assertEqual(adapted.expected_candidates, ())
                self.assertTrue(adapted.is_engine_executable)

    def test_reference_path_keeps_existing_schema_and_status_guards(self):
        with self.assertRaises(TeacherGoldAdapterError) as context:
            adapt_teacher_gold_reference_row(row(status="DRAFT"))
        self.assertEqual(context.exception.code, "unverified_row")

        bad = row()
        del bad["teacher_reason"]
        bad["unexpected"] = "value"
        with self.assertRaises(TeacherGoldAdapterError) as context:
            adapt_teacher_gold_reference_row(bad)
        self.assertEqual(context.exception.code, "schema_mismatch")

    def test_reference_path_keeps_state_candidate_cardinality_guards(self):
        with self.assertRaises(TeacherGoldAdapterError):
            adapt_teacher_gold_reference_row(row(state="RESOLVED", primary="", inversion="root_position"))
        with self.assertRaises(TeacherGoldAdapterError):
            adapt_teacher_gold_reference_row(
                row(
                    state="AMBIGUOUS",
                    primary="C6",
                    alternatives="C6 | Am7/C",
                    inversion="",
                )
            )
        with self.assertRaises(TeacherGoldAdapterError):
            adapt_teacher_gold_reference_row(
                row(state="ABSTAIN", primary="C6", alternatives="", inversion="")
            )

    def test_reference_validation_accepts_known_gap_but_rejects_true_unknown(self):
        report = validate_teacher_gold_reference_rows(
            (
                row(case_id="TG-0001"),
                row(
                    case_id="TG-0002",
                    state="AMBIGUOUS",
                    primary="",
                    alternatives="C6 | Am7/C",
                    inversion="",
                ),
            )
        )
        self.assertTrue(report.is_valid)
        self.assertEqual(report.valid_row_count, 2)

        unknown = validate_teacher_gold_reference_rows(
            (row(case_id="TG-0001", primary="Cfoobar"),)
        )
        self.assertFalse(unknown.is_valid)
        self.assertEqual(unknown.issues[0].code, "unsupported_identity")

    def test_duplicate_and_noncanonical_order_still_fail(self):
        duplicate = validate_teacher_gold_reference_rows(
            (row(case_id="TG-0001"), row(case_id="TG-0001"))
        )
        self.assertFalse(duplicate.is_valid)
        self.assertEqual(duplicate.issues[0].code, "duplicate_case_id")

        unsorted = validate_teacher_gold_reference_rows(
            (row(case_id="TG-0002"), row(case_id="TG-0001"))
        )
        self.assertFalse(unsorted.is_valid)
        self.assertEqual(unsorted.issues[0].code, "noncanonical_order")

    def test_frozen_reference_validator_accepts_reference_only_cases(self):
        synthetic = [
            row(case_id=f"TG-{index:04d}")
            for index in range(1, FROZEN_CALIBRATION_V0_1_CASE_COUNT + 1)
        ]
        synthetic[8] = row(
            case_id="TG-0009",
            notes="C3,E3,G3,A3",
            state="AMBIGUOUS",
            primary="",
            alternatives="C6 | Am7/C",
            inversion="",
        )
        report = validate_frozen_calibration_reference_v0_1(tuple(synthetic))
        self.assertTrue(report.is_valid)
        self.assertEqual(report.valid_row_count, 100)

        cases = build_frozen_calibration_reference_cases(tuple(synthetic))
        self.assertEqual(len(cases), 100)
        self.assertFalse(cases[8].is_engine_executable)

    def test_coverage_separates_executable_and_reference_only_cases(self):
        cases = (
            adapt_teacher_gold_reference_row(row(case_id="TG-0001")),
            adapt_teacher_gold_reference_row(
                row(
                    case_id="TG-0002",
                    notes="C3,E3,G3,A3",
                    state="AMBIGUOUS",
                    primary="",
                    alternatives="C6 | Am7/C",
                    inversion="",
                )
            ),
            adapt_teacher_gold_reference_row(
                row(
                    case_id="TG-0003",
                    notes="C3,F3,G3,Bb3",
                    primary="C7sus4",
                )
            ),
        )
        coverage = summarize_teacher_gold_reference_coverage(cases)
        self.assertEqual(coverage.case_count, 3)
        self.assertEqual(coverage.executable_case_count, 1)
        self.assertEqual(coverage.reference_only_case_count, 2)
        self.assertEqual(coverage.reference_only_case_ids, ("TG-0002", "TG-0003"))
        self.assertEqual(coverage.reference_only_labels, ("C6", "C7sus4"))
        self.assertFalse(coverage.is_fully_executable)

    def test_repeated_reference_adaptation_is_deterministic(self):
        target = row(
            case_id="TG-0071",
            notes="G3,B3,D4,E4",
            state="AMBIGUOUS",
            primary="",
            alternatives="G6 | Em7/G",
            inversion="",
        )
        expected = adapt_teacher_gold_reference_row(target)
        for _ in range(10):
            self.assertEqual(adapt_teacher_gold_reference_row(target), expected)


if __name__ == "__main__":
    unittest.main()
