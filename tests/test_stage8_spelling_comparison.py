import unittest

from st_guitar_harmonic_engine.calibration import BenchmarkSplit
from st_guitar_harmonic_engine.public_api_v1_1 import (
    PUBLIC_API_SCHEMA_VERSION_V1_1,
    execute_public_request_v1_1,
)
from st_guitar_harmonic_engine.public_runtime import execute_public_request
from st_guitar_harmonic_engine.stage8_spelling_comparison import (
    STAGE8_SPELLING_COMPARISON_PROFILE,
    build_teacher_gold_public_request_v1_1,
    evaluate_teacher_gold_rows_v1_1,
)
from st_guitar_harmonic_engine.teacher_gold_vocabulary_v0_3 import (
    adapt_teacher_gold_reference_row_v0_3,
)


def _row(case_id, notes="C4,E4,G4", primary="C major", inversion="root_position", status="VERIFIED"):
    return {
        "example_id": case_id,
        "input_notes": notes,
        "expected_state": "RESOLVED",
        "primary_candidate": primary,
        "acceptable_alternatives": "",
        "inversion": inversion,
        "teacher_reason": "Synthetic Stage 8 comparison fixture.",
        "annotation_status": status,
    }


def _partition(start):
    return [_row(f"TG-{index:04d}") for index in range(start, start + 100)]


class Stage8SpellingComparisonTests(unittest.TestCase):
    def test_profile_and_request_preserve_spelling(self):
        self.assertEqual(STAGE8_SPELLING_COMPARISON_PROFILE, "public_v1_1_spelling")
        row = _row("TG-0001", notes="C3,E3,G#3", primary="C augmented")
        request = build_teacher_gold_public_request_v1_1(row, split=BenchmarkSplit.CALIBRATION)
        self.assertEqual(request["schema_version"], PUBLIC_API_SCHEMA_VERSION_V1_1)
        spellings = [event["written_pitch"] for event in request["frames"][0]["events"]]
        self.assertEqual(spellings[2], {"step": "G", "alter": 1, "octave": 3})

    def test_v1_1_resolves_symmetric_spelling_without_mutating_v1_0(self):
        row = _row("TG-0001", notes="C3,E3,G#3", primary="C augmented")
        reference = adapt_teacher_gold_reference_row_v0_3(row, split=BenchmarkSplit.CALIBRATION)
        baseline = execute_public_request(reference.public_request)
        self.assertEqual(baseline["results"][0]["decision"]["state"], "ambiguous")
        request = build_teacher_gold_public_request_v1_1(row, split=BenchmarkSplit.CALIBRATION)
        comparison = execute_public_request_v1_1(request)
        decision = comparison["results"][0]["decision"]
        self.assertEqual(decision["state"], "resolved")
        self.assertEqual(decision["candidates"][0]["identity"]["root_pc"], 0)
        self.assertEqual(decision["candidates"][0]["identity"]["variant"], "augmented")

    def test_200_case_comparison_is_deterministic_and_correct_for_fixture(self):
        calibration = _partition(1)
        holdout = _partition(101)
        calibration[0] = _row("TG-0001", notes="C3,E3,G#3", primary="C augmented")
        holdout[0] = _row("TG-0101", notes="B3,D4,F4,Ab4", primary="Bdim7")
        first = evaluate_teacher_gold_rows_v1_1(calibration, holdout)
        second = evaluate_teacher_gold_rows_v1_1(calibration, holdout)
        self.assertEqual(first, second)
        self.assertEqual(first.reference_case_count, 200)
        self.assertEqual(first.executable_case_count, 200)
        self.assertEqual(first.reference_only_case_count, 0)
        self.assertEqual(first.correct_case_count, 200)
        self.assertEqual(first.state_match_count, 200)
        self.assertEqual(first.identity_match_count, first.identity_applicable_count)
        self.assertEqual(first.validation_or_runtime_error_count, 0)
        self.assertTrue(first.deterministic_stable)

    def test_draft_row_fails_closed(self):
        calibration = _partition(1)
        holdout = _partition(101)
        calibration[0] = _row("TG-0001", status="DRAFT")
        with self.assertRaises(ValueError):
            evaluate_teacher_gold_rows_v1_1(calibration, holdout)


if __name__ == "__main__":
    unittest.main()
