import unittest

from st_guitar_harmonic_engine.calibration import BenchmarkSplit
from st_guitar_harmonic_engine.teacher_gold_adapter import TeacherGoldAdapterError
from st_guitar_harmonic_engine.teacher_gold_holdout import (
    HOLDOUT_V0_1_CASE_COUNT,
    HOLDOUT_V0_1_CASE_IDS,
    assert_disjoint_calibration_holdout_ids,
    build_frozen_holdout_reference_v0_1,
    validate_holdout_template_v0_1,
)


def row(
    case_id,
    *,
    notes="",
    state="",
    primary="",
    alternatives="",
    inversion="",
    reason="",
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


def blank_template():
    return tuple(row(case_id) for case_id in HOLDOUT_V0_1_CASE_IDS)


def verified_row(case_id):
    return row(
        case_id,
        notes="C4,E4,G4",
        state="RESOLVED",
        primary="C major",
        inversion="root_position",
        reason="Human verified holdout reference.",
        status="VERIFIED",
    )


class TeacherGoldHoldoutTests(unittest.TestCase):
    def test_namespace_is_exactly_tg_0101_through_tg_0200(self):
        self.assertEqual(HOLDOUT_V0_1_CASE_COUNT, 100)
        self.assertEqual(HOLDOUT_V0_1_CASE_IDS[0], "TG-0101")
        self.assertEqual(HOLDOUT_V0_1_CASE_IDS[-1], "TG-0200")
        self.assertEqual(len(HOLDOUT_V0_1_CASE_IDS), 100)
        self.assertEqual(len(set(HOLDOUT_V0_1_CASE_IDS)), 100)

    def test_blank_draft_template_is_valid_but_not_freeze_ready(self):
        report = validate_holdout_template_v0_1(blank_template())
        self.assertTrue(report.is_template_valid)
        self.assertFalse(report.is_freeze_ready)
        self.assertEqual(report.draft_count, 100)
        self.assertEqual(report.verified_count, 0)
        self.assertEqual(report.issues, ())

    def test_partially_annotated_draft_is_allowed_without_becoming_gold(self):
        rows = list(blank_template())
        rows[0] = row(
            "TG-0101",
            notes="C4,E4,G4",
            state="RESOLVED",
            primary="C major",
            inversion="root_position",
            reason="Draft human work.",
            status="DRAFT",
        )
        report = validate_holdout_template_v0_1(tuple(rows))
        self.assertTrue(report.is_template_valid)
        self.assertFalse(report.is_freeze_ready)
        self.assertEqual(report.draft_count, 100)

    def test_verified_row_must_satisfy_full_reference_contract(self):
        rows = list(blank_template())
        rows[0] = row("TG-0101", status="VERIFIED")
        report = validate_holdout_template_v0_1(tuple(rows))
        self.assertFalse(report.is_template_valid)
        self.assertEqual(report.verified_count, 1)
        self.assertIn("missing_value", {issue.code for issue in report.issues})

    def test_calibration_ids_are_rejected_from_holdout_sequence(self):
        rows = list(blank_template())
        rows[0] = row("TG-0001")
        report = validate_holdout_template_v0_1(tuple(rows))
        self.assertFalse(report.is_template_valid)
        self.assertEqual(report.issues[0].code, "holdout_case_sequence")

    def test_wrong_row_count_is_rejected(self):
        report = validate_holdout_template_v0_1(blank_template()[:-1])
        self.assertFalse(report.is_template_valid)
        self.assertIn("holdout_case_count", {issue.code for issue in report.issues})

    def test_unknown_status_is_rejected(self):
        rows = list(blank_template())
        rows[0] = row("TG-0101", status="LOCKED")
        report = validate_holdout_template_v0_1(tuple(rows))
        self.assertFalse(report.is_template_valid)
        self.assertEqual(report.issues[0].code, "invalid_annotation_status")

    def test_freeze_builder_refuses_any_remaining_draft(self):
        with self.assertRaises(TeacherGoldAdapterError) as context:
            build_frozen_holdout_reference_v0_1(blank_template())
        self.assertEqual(context.exception.code, "holdout_not_freeze_ready")

    def test_100_verified_rows_build_holdout_reference_cases_only(self):
        rows = tuple(verified_row(case_id) for case_id in HOLDOUT_V0_1_CASE_IDS)
        report = validate_holdout_template_v0_1(rows)
        self.assertTrue(report.is_freeze_ready)
        cases = build_frozen_holdout_reference_v0_1(rows)
        self.assertEqual(len(cases), 100)
        self.assertTrue(all(case.split is BenchmarkSplit.HOLDOUT for case in cases))
        self.assertEqual(tuple(case.case_id for case in cases), HOLDOUT_V0_1_CASE_IDS)

    def test_reference_only_identity_is_allowed_after_human_verification(self):
        rows = list(blank_template())
        rows[0] = row(
            "TG-0101",
            notes="C3,E3,G3,A3",
            state="AMBIGUOUS",
            alternatives="C6 | Am7/C",
            reason="Human verified ambiguity.",
            status="VERIFIED",
        )
        report = validate_holdout_template_v0_1(tuple(rows))
        self.assertTrue(report.is_template_valid)
        self.assertEqual(report.verified_count, 1)
        self.assertFalse(report.is_freeze_ready)

    def test_calibration_and_holdout_namespaces_are_disjoint(self):
        calibration = tuple(f"TG-{index:04d}" for index in range(1, 101))
        assert_disjoint_calibration_holdout_ids(calibration)
        with self.assertRaises(ValueError):
            assert_disjoint_calibration_holdout_ids(("TG-0101",))

    def test_repeated_template_validation_is_deterministic(self):
        target = blank_template()
        expected = validate_holdout_template_v0_1(target)
        for _ in range(10):
            self.assertEqual(validate_holdout_template_v0_1(target), expected)


if __name__ == "__main__":
    unittest.main()
