import unittest

from st_guitar_harmonic_engine.abstention import FinalDecisionState
from st_guitar_harmonic_engine.calibration import BenchmarkSplit
from st_guitar_harmonic_engine.stage8_baseline_seal import (
    Stage8BaselineStatus,
    build_stage8_baseline_seal,
    serialize_stage8_baseline_seal,
)
from st_guitar_harmonic_engine.teacher_gold_evaluation import (
    TeacherGoldEvaluationCaseResult,
    TeacherGoldEvaluationReport,
)


ENGINE_SHA = "1" * 40
CALIBRATION_SHA = "2" * 64
HOLDOUT_SHA = "3" * 64


def _normal_case(case_id, split, *, correct=True):
    return TeacherGoldEvaluationCaseResult(
        case_id=case_id,
        split=split,
        reference_only=False,
        expected_state=FinalDecisionState.RESOLVED,
        actual_state=(
            FinalDecisionState.RESOLVED if correct else FinalDecisionState.AMBIGUOUS
        ),
        state_match=correct,
        identity_match=correct,
        schema_valid=True,
        deterministic_stable=True,
        output_sha256="a" * 64,
        error_type=None,
    )


def _reference_only_case(case_id, split):
    return TeacherGoldEvaluationCaseResult(
        case_id=case_id,
        split=split,
        reference_only=True,
        expected_state=FinalDecisionState.RESOLVED,
        actual_state=None,
        state_match=None,
        identity_match=None,
        schema_valid=False,
        deterministic_stable=False,
        output_sha256=None,
        error_type=None,
    )


def _error_case(case_id, split):
    return TeacherGoldEvaluationCaseResult(
        case_id=case_id,
        split=split,
        reference_only=False,
        expected_state=FinalDecisionState.RESOLVED,
        actual_state=None,
        state_match=None,
        identity_match=None,
        schema_valid=False,
        deterministic_stable=False,
        output_sha256=None,
        error_type="RuntimeError",
    )


def _report(*, incorrect_index=None, reference_only_index=None, error_index=None, total=200):
    cases = []
    for index in range(total):
        split = BenchmarkSplit.CALIBRATION if index < 100 else BenchmarkSplit.HOLDOUT
        case_id = f"TG-{index + 1:04d}"
        if index == reference_only_index:
            cases.append(_reference_only_case(case_id, split))
        elif index == error_index:
            cases.append(_error_case(case_id, split))
        else:
            cases.append(_normal_case(case_id, split, correct=index != incorrect_index))

    executable = sum(not item.reference_only for item in cases)
    reference_only = sum(item.reference_only for item in cases)
    correct = sum(item.is_correct for item in cases)
    state_matches = sum(item.state_match is True for item in cases)
    identity_applicable = sum(item.identity_match is not None for item in cases)
    identity_matches = sum(item.identity_match is True for item in cases)
    errors = sum(item.error_type is not None for item in cases)
    stable = all(item.reference_only or item.deterministic_stable for item in cases)
    if error_index is not None:
        stable = False

    return TeacherGoldEvaluationReport(
        reference_case_count=len(cases),
        executable_case_count=executable,
        reference_only_case_count=reference_only,
        correct_case_count=correct,
        state_match_count=state_matches,
        identity_applicable_count=identity_applicable,
        identity_match_count=identity_matches,
        validation_or_runtime_error_count=errors,
        deterministic_stable=stable,
        cases=tuple(cases),
    )


class Stage8BaselineSealTests(unittest.TestCase):
    def _seal(self, report):
        return build_stage8_baseline_seal(
            report,
            engine_commit_sha=ENGINE_SHA,
            calibration_source_sha256=CALIBRATION_SHA,
            holdout_source_sha256=HOLDOUT_SHA,
        )

    def test_complete_deterministic_200_case_report_is_ready(self):
        seal = self._seal(_report())
        self.assertIs(seal.status, Stage8BaselineStatus.READY)
        self.assertEqual(seal.blocking_reasons, ())
        self.assertEqual(seal.reference_case_count, 200)
        self.assertEqual(seal.executable_case_count, 200)
        self.assertEqual(seal.reference_only_case_count, 0)
        self.assertEqual(seal.calibration.reference_case_count, 100)
        self.assertEqual(seal.holdout.reference_case_count, 100)
        self.assertEqual(seal.musical_accuracy, 1.0)

    def test_accuracy_is_recorded_but_not_a_hidden_readiness_threshold(self):
        seal = self._seal(_report(incorrect_index=150))
        self.assertIs(seal.status, Stage8BaselineStatus.READY)
        self.assertEqual(seal.correct_case_count, 199)
        self.assertLess(seal.musical_accuracy, 1.0)
        self.assertEqual(seal.blocking_reasons, ())

    def test_reference_only_case_blocks_stage8_baseline(self):
        seal = self._seal(_report(reference_only_index=10))
        self.assertIs(seal.status, Stage8BaselineStatus.BLOCKED)
        self.assertIn("executable_case_count_not_200", seal.blocking_reasons)
        self.assertIn("reference_only_cases_present", seal.blocking_reasons)

    def test_runtime_error_blocks_stage8_baseline(self):
        seal = self._seal(_report(error_index=120))
        self.assertIs(seal.status, Stage8BaselineStatus.BLOCKED)
        self.assertIn("validation_or_runtime_errors_present", seal.blocking_reasons)
        self.assertIn("evaluation_not_deterministic", seal.blocking_reasons)

    def test_wrong_total_case_count_blocks_stage8_baseline(self):
        seal = self._seal(_report(total=199))
        self.assertIs(seal.status, Stage8BaselineStatus.BLOCKED)
        self.assertIn("reference_case_count_not_200", seal.blocking_reasons)
        self.assertIn("executable_case_count_not_200", seal.blocking_reasons)
        self.assertIn("holdout_case_count_not_100", seal.blocking_reasons)

    def test_invalid_commit_or_source_digest_fails_closed(self):
        report = _report()
        with self.assertRaises(ValueError):
            build_stage8_baseline_seal(
                report,
                engine_commit_sha="not-a-sha",
                calibration_source_sha256=CALIBRATION_SHA,
                holdout_source_sha256=HOLDOUT_SHA,
            )
        with self.assertRaises(ValueError):
            build_stage8_baseline_seal(
                report,
                engine_commit_sha=ENGINE_SHA,
                calibration_source_sha256=CALIBRATION_SHA,
                holdout_source_sha256=CALIBRATION_SHA,
            )

    def test_serialization_is_stable_and_self_hashing(self):
        first = self._seal(_report())
        second = self._seal(_report())
        self.assertEqual(first, second)
        self.assertEqual(first.seal_sha256, second.seal_sha256)
        payload = serialize_stage8_baseline_seal(first)
        self.assertEqual(payload["seal_sha256"], first.seal_sha256)
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["calibration"]["split"], "calibration")
        self.assertEqual(payload["holdout"]["split"], "holdout")


if __name__ == "__main__":
    unittest.main()
