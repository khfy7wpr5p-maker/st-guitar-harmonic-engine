import unittest

from st_guitar_harmonic_engine.abstention import FinalDecisionState
from st_guitar_harmonic_engine.calibration import BenchmarkSplit
from st_guitar_harmonic_engine.public_api import validate_public_request
from st_guitar_harmonic_engine.resolver import CandidateFamily, HarmonicIdentity
from st_guitar_harmonic_engine.teacher_gold_adapter import (
    FROZEN_CALIBRATION_V0_1_CASE_COUNT,
    TEACHER_GOLD_SHEET_COLUMNS,
    TeacherGoldAdapterError,
    adapt_teacher_gold_row,
    build_teacher_gold_benchmark,
    note_name_to_midi,
    parse_teacher_candidate_identity,
    validate_frozen_calibration_v0_1,
    validate_teacher_gold_rows,
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


class TeacherGoldAdapterTests(unittest.TestCase):
    def test_sheet_schema_is_exactly_frozen_eight_columns(self):
        self.assertEqual(
            TEACHER_GOLD_SHEET_COLUMNS,
            (
                "example_id",
                "input_notes",
                "expected_state",
                "primary_candidate",
                "acceptable_alternatives",
                "inversion",
                "teacher_reason",
                "annotation_status",
            ),
        )

    def test_scientific_pitch_conversion_supports_sharps_flats_and_enharmonics(self):
        self.assertEqual(note_name_to_midi("C4"), 60)
        self.assertEqual(note_name_to_midi("C#4"), 61)
        self.assertEqual(note_name_to_midi("Db4"), 61)
        self.assertEqual(note_name_to_midi("E#3"), 53)
        self.assertEqual(note_name_to_midi("Bb2"), 46)

    def test_resolved_row_adapts_to_gold_case_and_valid_public_request(self):
        adapted = adapt_teacher_gold_row(
            row(
                case_id="TG-0041",
                notes="C#3,E#3,G#3,B3",
                primary="C#7",
            )
        )
        self.assertEqual(adapted.gold_case.case_id, "TG-0041")
        self.assertIs(adapted.gold_case.split, BenchmarkSplit.CALIBRATION)
        self.assertIs(adapted.gold_case.expected_state, FinalDecisionState.RESOLVED)
        self.assertEqual(
            adapted.gold_case.acceptable_identities,
            (HarmonicIdentity(1, CandidateFamily.BASIC, "dominant_seventh"),),
        )
        self.assertEqual(adapted.expected_inversion, "root_position")
        validated = validate_public_request(adapted.public_request)
        self.assertEqual(len(validated.frames), 1)
        self.assertEqual(
            tuple(event.midi_pitch for event in validated.frames[0].events),
            (49, 53, 56, 59),
        )

    def test_slash_bass_is_preserved_as_review_metadata_but_not_identity(self):
        adapted = adapt_teacher_gold_row(
            row(
                case_id="TG-0054",
                notes="E3,G3,B3,C4",
                primary="Cmaj7/E",
                inversion="first_inversion",
            )
        )
        self.assertEqual(
            adapted.gold_case.acceptable_identities,
            (HarmonicIdentity(0, CandidateFamily.BASIC, "major_seventh"),),
        )
        self.assertEqual(adapted.expected_inversion, "first_inversion")

    def test_supported_suspended_ambiguity_maps_to_two_canonical_identities(self):
        adapted = adapt_teacher_gold_row(
            row(
                case_id="TG-0021",
                notes="C3,F3,G3",
                state="AMBIGUOUS",
                primary="",
                alternatives="Csus4 | Fsus2/C",
                inversion="",
            )
        )
        self.assertIs(adapted.gold_case.expected_state, FinalDecisionState.AMBIGUOUS)
        self.assertEqual(
            set(adapted.gold_case.acceptable_identities),
            {
                HarmonicIdentity(0, CandidateFamily.SUSPENDED, "sus4"),
                HarmonicIdentity(5, CandidateFamily.SUSPENDED, "sus2"),
            },
        )

    def test_abstain_and_no_match_do_not_claim_identities(self):
        for case_id, state, notes in (
            ("TG-0081", "ABSTAIN", "C3,E3"),
            ("TG-0099", "NO_MATCH", "C3,C#3,D3"),
        ):
            with self.subTest(state=state):
                adapted = adapt_teacher_gold_row(
                    row(
                        case_id=case_id,
                        notes=notes,
                        state=state,
                        primary="",
                        alternatives="",
                        inversion="",
                    )
                )
                self.assertEqual(adapted.gold_case.acceptable_identities, ())

    def test_extension_and_altered_labels_map_to_current_identity_vocabulary(self):
        expected = {
            "Cadd9": HarmonicIdentity(0, CandidateFamily.EXTENSION, "major:natural_ninth"),
            "Cmadd9": HarmonicIdentity(0, CandidateFamily.EXTENSION, "minor:natural_ninth"),
            "C9": HarmonicIdentity(0, CandidateFamily.EXTENSION, "dominant_seventh:natural_ninth"),
            "Cmaj9": HarmonicIdentity(0, CandidateFamily.EXTENSION, "major_seventh:natural_ninth"),
            "C7(add11)": HarmonicIdentity(
                0, CandidateFamily.EXTENSION, "dominant_seventh:natural_eleventh"
            ),
            "C7(add13)": HarmonicIdentity(
                0, CandidateFamily.EXTENSION, "dominant_seventh:natural_thirteenth"
            ),
            "G7b9": HarmonicIdentity(
                7, CandidateFamily.ALTERED, "dominant_seventh:flat_ninth"
            ),
            "G7#9": HarmonicIdentity(
                7, CandidateFamily.ALTERED, "dominant_seventh:sharp_ninth"
            ),
            "G7#11": HarmonicIdentity(
                7, CandidateFamily.ALTERED, "dominant_seventh:sharp_eleventh"
            ),
            "G7b13": HarmonicIdentity(
                7, CandidateFamily.ALTERED, "dominant_seventh:flat_thirteenth"
            ),
        }
        for label, identity in expected.items():
            with self.subTest(label=label):
                self.assertEqual(parse_teacher_candidate_identity(label), identity)

    def test_sixth_chords_fail_closed_instead_of_being_coerced(self):
        with self.assertRaisesRegex(TeacherGoldAdapterError, "not representable"):
            parse_teacher_candidate_identity("C6")
        with self.assertRaisesRegex(TeacherGoldAdapterError, "not representable"):
            parse_teacher_candidate_identity("Dm6")

    def test_seventh_suspended_chords_fail_closed_instead_of_losing_seventh(self):
        with self.assertRaisesRegex(TeacherGoldAdapterError, "not representable"):
            parse_teacher_candidate_identity("C7sus4")

    def test_unverified_rows_are_rejected(self):
        with self.assertRaises(TeacherGoldAdapterError) as context:
            adapt_teacher_gold_row(row(status="DRAFT"))
        self.assertEqual(context.exception.code, "unverified_row")

    def test_schema_mismatch_is_rejected(self):
        bad = row()
        del bad["teacher_reason"]
        bad["unexpected"] = "value"
        with self.assertRaises(TeacherGoldAdapterError) as context:
            adapt_teacher_gold_row(bad)
        self.assertEqual(context.exception.code, "schema_mismatch")

    def test_bad_notes_and_out_of_range_notes_are_rejected(self):
        with self.assertRaises(TeacherGoldAdapterError):
            note_name_to_midi("H4")
        with self.assertRaises(TeacherGoldAdapterError):
            note_name_to_midi("C10")

    def test_state_candidate_cardinality_is_fail_closed(self):
        with self.assertRaises(TeacherGoldAdapterError):
            adapt_teacher_gold_row(row(state="RESOLVED", primary="", inversion="root_position"))
        with self.assertRaises(TeacherGoldAdapterError):
            adapt_teacher_gold_row(
                row(
                    state="AMBIGUOUS",
                    primary="C major",
                    alternatives="C major | A minor",
                    inversion="",
                )
            )
        with self.assertRaises(TeacherGoldAdapterError):
            adapt_teacher_gold_row(
                row(state="ABSTAIN", primary="C major", alternatives="", inversion="")
            )

    def test_validation_report_collects_multiple_independent_failures(self):
        rows = (
            row(case_id="TG-0001"),
            row(
                case_id="TG-0002",
                state="AMBIGUOUS",
                primary="",
                alternatives="C6 | Am7/C",
                inversion="",
            ),
            row(case_id="TG-0003", status="DRAFT"),
        )
        report = validate_teacher_gold_rows(rows)
        self.assertFalse(report.is_valid)
        self.assertEqual(report.row_count, 3)
        self.assertEqual(report.valid_row_count, 1)
        self.assertEqual(
            tuple(issue.code for issue in report.issues),
            ("unsupported_identity", "unverified_row"),
        )

    def test_duplicate_and_noncanonical_case_order_are_rejected(self):
        duplicate = validate_teacher_gold_rows(
            (row(case_id="TG-0001"), row(case_id="TG-0001"))
        )
        self.assertFalse(duplicate.is_valid)
        self.assertEqual(duplicate.issues[0].code, "duplicate_case_id")

        unsorted = validate_teacher_gold_rows(
            (row(case_id="TG-0002"), row(case_id="TG-0001"))
        )
        self.assertFalse(unsorted.is_valid)
        self.assertEqual(unsorted.issues[0].code, "noncanonical_order")

    def test_frozen_snapshot_validator_requires_exact_100_case_sequence(self):
        synthetic = tuple(
            row(case_id=f"TG-{index:04d}")
            for index in range(1, FROZEN_CALIBRATION_V0_1_CASE_COUNT + 1)
        )
        report = validate_frozen_calibration_v0_1(synthetic)
        self.assertTrue(report.is_valid)
        self.assertEqual(report.valid_row_count, 100)

        short = validate_frozen_calibration_v0_1(synthetic[:-1])
        self.assertFalse(short.is_valid)
        self.assertIn("snapshot_case_count", {issue.code for issue in short.issues})

    def test_benchmark_build_refuses_partial_or_unsupported_rows(self):
        valid_rows = (row(case_id="TG-0001"), row(case_id="TG-0002"))
        benchmark = build_teacher_gold_benchmark(valid_rows)
        self.assertEqual(tuple(item.case_id for item in benchmark.cases), ("TG-0001", "TG-0002"))

        invalid_rows = (
            row(case_id="TG-0001"),
            row(
                case_id="TG-0002",
                state="AMBIGUOUS",
                primary="",
                alternatives="C6 | Am7/C",
                inversion="",
            ),
        )
        with self.assertRaises(TeacherGoldAdapterError) as context:
            build_teacher_gold_benchmark(invalid_rows)
        self.assertEqual(context.exception.code, "validation_failed")

    def test_repeated_adaptation_is_deterministic(self):
        target = row(
            case_id="TG-0043",
            notes="G3,B3,D4,F4,Ab4",
            primary="G7b9",
        )
        expected = adapt_teacher_gold_row(target)
        for _ in range(10):
            self.assertEqual(adapt_teacher_gold_row(target), expected)


if __name__ == "__main__":
    unittest.main()
