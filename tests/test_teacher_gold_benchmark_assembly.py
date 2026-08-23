import unittest

from st_guitar_harmonic_engine.abstention import FinalDecisionState
from st_guitar_harmonic_engine.calibration import BenchmarkSplit, CalibrationReadiness
from st_guitar_harmonic_engine.resolver import CandidateFamily, HarmonicIdentity
from st_guitar_harmonic_engine.teacher_gold_benchmark_assembly import (
    CALIBRATION_V0_1_CASE_IDS,
    TEACHER_GOLD_V0_1_REFERENCE_CASE_COUNT,
    assemble_frozen_teacher_gold_benchmark_v0_1,
)
from st_guitar_harmonic_engine.teacher_gold_holdout import HOLDOUT_V0_1_CASE_IDS
from st_guitar_harmonic_engine.teacher_gold_reference import (
    TeacherGoldReferenceCandidate,
    TeacherGoldReferenceCase,
)


C_MAJOR = HarmonicIdentity(0, CandidateFamily.BASIC, "major")
D_MAJOR = HarmonicIdentity(2, CandidateFamily.BASIC, "major")


def candidate(label="C major", identity=C_MAJOR):
    return TeacherGoldReferenceCandidate(label, identity)


def reference_case(
    case_id,
    split,
    *,
    state=FinalDecisionState.RESOLVED,
    candidates=None,
):
    if candidates is None:
        candidates = (candidate(),)
    inversion = "root_position" if state is FinalDecisionState.RESOLVED else None
    return TeacherGoldReferenceCase(
        case_id=case_id,
        split=split,
        expected_state=state,
        expected_candidates=tuple(candidates),
        public_request={},
        expected_inversion=inversion,
        teacher_reason="Human verified frozen reference.",
    )


def calibration_cases():
    return tuple(reference_case(case_id, BenchmarkSplit.CALIBRATION) for case_id in CALIBRATION_V0_1_CASE_IDS)


def holdout_cases():
    return tuple(reference_case(case_id, BenchmarkSplit.HOLDOUT) for case_id in HOLDOUT_V0_1_CASE_IDS)


class TeacherGoldBenchmarkAssemblyTests(unittest.TestCase):
    def test_exact_frozen_partitions_become_benchmark_ready(self):
        assembly = assemble_frozen_teacher_gold_benchmark_v0_1(
            calibration_cases(), holdout_cases()
        )
        self.assertEqual(assembly.reference_case_count, TEACHER_GOLD_V0_1_REFERENCE_CASE_COUNT)
        self.assertEqual(assembly.executable_case_count, 200)
        self.assertEqual(assembly.reference_only_case_count, 0)
        self.assertEqual(assembly.calibration_executable_count, 100)
        self.assertEqual(assembly.holdout_executable_count, 100)
        self.assertTrue(assembly.is_full_reference_partition_ready)
        self.assertTrue(assembly.is_fully_engine_executable)
        self.assertIs(assembly.readiness, CalibrationReadiness.BENCHMARK_READY)

    def test_reference_only_resolved_case_is_preserved_but_not_scored(self):
        calibration = list(calibration_cases())
        calibration[8] = reference_case(
            "TG-0009",
            BenchmarkSplit.CALIBRATION,
            candidates=(candidate("C6", None),),
        )
        assembly = assemble_frozen_teacher_gold_benchmark_v0_1(
            tuple(calibration), holdout_cases()
        )
        self.assertEqual(assembly.reference_case_count, 200)
        self.assertEqual(assembly.executable_case_count, 199)
        self.assertEqual(assembly.reference_only_case_ids, ("TG-0009",))
        self.assertFalse(assembly.is_fully_engine_executable)
        self.assertNotIn("TG-0009", {case.case_id for case in assembly.benchmark.cases})
        self.assertIs(assembly.readiness, CalibrationReadiness.BENCHMARK_READY)

    def test_partially_representable_ambiguity_excludes_the_whole_case(self):
        holdout = list(holdout_cases())
        holdout[0] = reference_case(
            "TG-0101",
            BenchmarkSplit.HOLDOUT,
            state=FinalDecisionState.AMBIGUOUS,
            candidates=(candidate("C major", C_MAJOR), candidate("C6", None)),
        )
        assembly = assemble_frozen_teacher_gold_benchmark_v0_1(
            calibration_cases(), tuple(holdout)
        )
        self.assertIn("TG-0101", assembly.reference_only_case_ids)
        self.assertNotIn("TG-0101", {case.case_id for case in assembly.benchmark.cases})
        self.assertEqual(assembly.holdout_executable_count, 99)

    def test_engine_identity_collision_remains_reference_only(self):
        holdout = list(holdout_cases())
        holdout[0] = reference_case(
            "TG-0101",
            BenchmarkSplit.HOLDOUT,
            state=FinalDecisionState.AMBIGUOUS,
            candidates=(candidate("C major", C_MAJOR), candidate("C major alias", C_MAJOR)),
        )
        assembly = assemble_frozen_teacher_gold_benchmark_v0_1(
            calibration_cases(), tuple(holdout)
        )
        self.assertEqual(assembly.reference_only_case_ids, ("TG-0101",))
        self.assertNotIn("TG-0101", {case.case_id for case in assembly.benchmark.cases})

    def test_incomplete_partition_is_rejected(self):
        with self.assertRaises(ValueError):
            assemble_frozen_teacher_gold_benchmark_v0_1(
                calibration_cases()[:-1], holdout_cases()
            )

    def test_wrong_split_is_rejected(self):
        holdout = list(holdout_cases())
        holdout[0] = reference_case("TG-0101", BenchmarkSplit.CALIBRATION)
        with self.assertRaises(ValueError):
            assemble_frozen_teacher_gold_benchmark_v0_1(
                calibration_cases(), tuple(holdout)
            )

    def test_wrong_namespace_is_rejected(self):
        holdout = list(holdout_cases())
        holdout[0] = reference_case("TG-9999", BenchmarkSplit.HOLDOUT)
        with self.assertRaises(ValueError):
            assemble_frozen_teacher_gold_benchmark_v0_1(
                calibration_cases(), tuple(holdout)
            )

    def test_abstain_and_no_match_remain_engine_executable_without_identities(self):
        holdout = list(holdout_cases())
        holdout[0] = reference_case(
            "TG-0101", BenchmarkSplit.HOLDOUT, state=FinalDecisionState.ABSTAIN, candidates=()
        )
        holdout[1] = reference_case(
            "TG-0102", BenchmarkSplit.HOLDOUT, state=FinalDecisionState.NO_MATCH, candidates=()
        )
        assembly = assemble_frozen_teacher_gold_benchmark_v0_1(
            calibration_cases(), tuple(holdout)
        )
        by_id = {case.case_id: case for case in assembly.benchmark.cases}
        self.assertEqual(by_id["TG-0101"].acceptable_identities, ())
        self.assertEqual(by_id["TG-0102"].acceptable_identities, ())
        self.assertEqual(assembly.reference_only_case_count, 0)

    def test_repeated_assembly_is_deterministic(self):
        calibration = calibration_cases()
        holdout = holdout_cases()
        expected = assemble_frozen_teacher_gold_benchmark_v0_1(calibration, holdout)
        for _ in range(10):
            self.assertEqual(
                assemble_frozen_teacher_gold_benchmark_v0_1(calibration, holdout),
                expected,
            )


if __name__ == "__main__":
    unittest.main()
