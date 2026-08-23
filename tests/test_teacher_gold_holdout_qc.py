import unittest

from st_guitar_harmonic_engine.teacher_gold_holdout_qc import (
    find_calibration_holdout_pitch_class_overlaps,
    normalized_pitch_classes,
    validate_holdout_candidate_review_v0_1,
)


def row(
    case_id,
    notes="F3,A3,C4",
    state="RESOLVED",
    primary="F major",
    alternatives="",
    inversion="root_position",
    reason="Verified teacher reason.",
    status="DRAFT",
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


def full_holdout():
    return tuple(row(f"TG-{index:04d}") for index in range(101, 201))


class TeacherGoldHoldoutQCTests(unittest.TestCase):
    def test_normalized_pitch_classes_ignore_octave_and_enharmonic_spelling(self):
        self.assertEqual(normalized_pitch_classes("C3,E3,G3"), (0, 4, 7))
        self.assertEqual(normalized_pitch_classes("B#4,Fb5,G5"), (0, 4, 7))

    def test_complete_draft_template_can_be_review_ready_without_becoming_verified(self):
        rows = full_holdout()
        report = validate_holdout_candidate_review_v0_1(rows)
        self.assertTrue(report.is_review_ready)
        self.assertEqual(report.candidate_ready_count, 100)
        self.assertEqual(report.draft_count, 100)
        self.assertEqual(report.verified_count, 0)
        self.assertEqual(report.state_counts, (("RESOLVED", 100),))
        self.assertTrue(all(item["annotation_status"] == "DRAFT" for item in rows))

    def test_incomplete_draft_is_not_review_ready(self):
        rows = list(full_holdout())
        rows[0] = row("TG-0101", notes="", primary="", reason="")
        report = validate_holdout_candidate_review_v0_1(tuple(rows))
        self.assertFalse(report.is_review_ready)
        self.assertEqual(report.candidate_ready_count, 99)
        self.assertIn("candidate_missing_value", {issue.code for issue in report.issues})

    def test_reference_only_candidate_is_preserved_and_counted(self):
        rows = list(full_holdout())
        rows[0] = row(
            "TG-0101",
            notes="A2,C#3,E3,F#3",
            state="AMBIGUOUS",
            primary="",
            alternatives="A6 | F#m7/A",
            inversion="",
        )
        report = validate_holdout_candidate_review_v0_1(tuple(rows))
        self.assertTrue(report.is_review_ready)
        self.assertEqual(report.reference_only_case_ids, ("TG-0101",))

    def test_true_unknown_candidate_fails_closed(self):
        rows = list(full_holdout())
        rows[0] = row("TG-0101", primary="Ffoobar")
        report = validate_holdout_candidate_review_v0_1(tuple(rows))
        self.assertFalse(report.is_review_ready)
        self.assertIn("candidate_unsupported_identity", {issue.code for issue in report.issues})

    def test_pitch_class_overlap_detects_octave_revoicing(self):
        calibration = (row("TG-0001", notes="C3,E3,G3", status="VERIFIED"),)
        holdout = (row("TG-0101", notes="C4,E4,G4"),)
        overlaps = find_calibration_holdout_pitch_class_overlaps(calibration, holdout)
        self.assertEqual(len(overlaps), 1)
        self.assertEqual(overlaps[0].calibration_case_id, "TG-0001")
        self.assertEqual(overlaps[0].holdout_case_id, "TG-0101")
        self.assertEqual(overlaps[0].pitch_classes, (0, 4, 7))

    def test_review_qc_blocks_calibration_pitch_class_reuse(self):
        calibration = (row("TG-0001", notes="C3,E3,G3", status="VERIFIED"),)
        rows = list(full_holdout())
        rows[0] = row("TG-0101", notes="C4,E4,G4", primary="C major")
        report = validate_holdout_candidate_review_v0_1(
            tuple(rows), calibration_rows=calibration
        )
        self.assertFalse(report.is_review_ready)
        self.assertEqual(len(report.overlaps), 1)
        self.assertIn("calibration_pitch_class_overlap", {issue.code for issue in report.issues})

    def test_different_pitch_class_sets_do_not_overlap(self):
        calibration = (row("TG-0001", notes="C3,E3,G3", status="VERIFIED"),)
        holdout = (row("TG-0101", notes="F3,A3,C4"),)
        self.assertEqual(
            find_calibration_holdout_pitch_class_overlaps(calibration, holdout), ()
        )

    def test_repeated_qc_is_deterministic(self):
        rows = full_holdout()
        expected = validate_holdout_candidate_review_v0_1(rows)
        for _ in range(10):
            self.assertEqual(validate_holdout_candidate_review_v0_1(rows), expected)


if __name__ == "__main__":
    unittest.main()
