import unittest

from st_guitar_harmonic_engine.abstention import FinalDecisionState
from st_guitar_harmonic_engine.calibration import (
    CALIBRATION_SEMANTICS,
    BenchmarkSplit,
    CalibrationReadiness,
    TeacherGoldBenchmark,
    TeacherGoldCase,
    calibration_readiness,
)
from st_guitar_harmonic_engine.resolver import CandidateFamily, HarmonicIdentity


def identity(root):
    return HarmonicIdentity(root, CandidateFamily.BASIC, "major")


class CalibrationInfrastructureTests(unittest.TestCase):
    def test_semantics_forbid_probability_claim(self):
        self.assertEqual(
            CALIBRATION_SEMANTICS,
            "requires_teacher_gold_benchmark_no_probability_claim",
        )

    def test_empty_benchmark_is_explicitly_uncalibrated(self):
        benchmark = TeacherGoldBenchmark(())
        self.assertIs(calibration_readiness(benchmark), CalibrationReadiness.UNCALIBRATED)

    def test_one_partition_is_incomplete_not_calibrated(self):
        benchmark = TeacherGoldBenchmark(
            (
                TeacherGoldCase(
                    "case-001",
                    BenchmarkSplit.CALIBRATION,
                    FinalDecisionState.RESOLVED,
                    (identity(0),),
                ),
            )
        )
        self.assertIs(
            calibration_readiness(benchmark),
            CalibrationReadiness.INCOMPLETE_BENCHMARK,
        )

    def test_separate_calibration_and_holdout_partitions_are_benchmark_ready(self):
        benchmark = TeacherGoldBenchmark(
            (
                TeacherGoldCase(
                    "case-001",
                    BenchmarkSplit.CALIBRATION,
                    FinalDecisionState.RESOLVED,
                    (identity(0),),
                ),
                TeacherGoldCase(
                    "case-002",
                    BenchmarkSplit.HOLDOUT,
                    FinalDecisionState.ABSTAIN,
                    (),
                ),
            )
        )
        self.assertIs(calibration_readiness(benchmark), CalibrationReadiness.BENCHMARK_READY)
        self.assertEqual(len(benchmark.cases_for(BenchmarkSplit.CALIBRATION)), 1)
        self.assertEqual(len(benchmark.cases_for(BenchmarkSplit.HOLDOUT)), 1)

    def test_gold_cardinality_matches_expected_state(self):
        with self.assertRaises(ValueError):
            TeacherGoldCase(
                "resolved-bad",
                BenchmarkSplit.CALIBRATION,
                FinalDecisionState.RESOLVED,
                (),
            )
        with self.assertRaises(ValueError):
            TeacherGoldCase(
                "ambiguous-bad",
                BenchmarkSplit.HOLDOUT,
                FinalDecisionState.AMBIGUOUS,
                (identity(0),),
            )
        with self.assertRaises(ValueError):
            TeacherGoldCase(
                "abstain-bad",
                BenchmarkSplit.HOLDOUT,
                FinalDecisionState.ABSTAIN,
                (identity(0),),
            )

    def test_duplicate_unsorted_and_noncanonical_cases_are_rejected(self):
        case = TeacherGoldCase(
            "case-001",
            BenchmarkSplit.CALIBRATION,
            FinalDecisionState.RESOLVED,
            (identity(0),),
        )
        with self.assertRaises(ValueError):
            TeacherGoldBenchmark((case, case))
        later = TeacherGoldCase(
            "case-002",
            BenchmarkSplit.HOLDOUT,
            FinalDecisionState.NO_MATCH,
            (),
        )
        with self.assertRaises(ValueError):
            TeacherGoldBenchmark((later, case))
        with self.assertRaises(ValueError):
            TeacherGoldCase(
                " case-003 ",
                BenchmarkSplit.HOLDOUT,
                FinalDecisionState.NO_MATCH,
                (),
            )

    def test_ambiguous_identity_order_is_canonical(self):
        with self.assertRaises(ValueError):
            TeacherGoldCase(
                "case-amb",
                BenchmarkSplit.HOLDOUT,
                FinalDecisionState.AMBIGUOUS,
                (identity(7), identity(0)),
            )

    def test_repeated_readiness_is_deterministic(self):
        benchmark = TeacherGoldBenchmark(
            (
                TeacherGoldCase(
                    "case-001",
                    BenchmarkSplit.CALIBRATION,
                    FinalDecisionState.RESOLVED,
                    (identity(0),),
                ),
                TeacherGoldCase(
                    "case-002",
                    BenchmarkSplit.HOLDOUT,
                    FinalDecisionState.NO_MATCH,
                    (),
                ),
            )
        )
        expected = calibration_readiness(benchmark)
        for _ in range(10):
            self.assertIs(calibration_readiness(benchmark), expected)

    def test_invalid_types_are_rejected(self):
        with self.assertRaises(TypeError):
            calibration_readiness(object())
        with self.assertRaises(TypeError):
            TeacherGoldBenchmark((object(),))


if __name__ == "__main__":
    unittest.main()
