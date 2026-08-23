import unittest
from unittest.mock import patch

from st_guitar_harmonic_engine.abstention import FinalDecisionState
from st_guitar_harmonic_engine.calibration import BenchmarkSplit
from st_guitar_harmonic_engine.public_api import (
    PUBLIC_RESULT_SCHEMA_NAME,
    PUBLIC_RESULT_SCHEMA_VERSION,
)
from st_guitar_harmonic_engine.resolver import CandidateFamily, HarmonicIdentity
from st_guitar_harmonic_engine.teacher_gold_benchmark_assembly import (
    CALIBRATION_V0_1_CASE_IDS,
    assemble_frozen_teacher_gold_benchmark_v0_1,
)
from st_guitar_harmonic_engine.teacher_gold_evaluation import (
    TEACHER_GOLD_ACCURACY_DENOMINATOR,
    TEACHER_GOLD_INVERSION_ACCURACY_CLAIM,
    evaluate_teacher_gold_assembly,
    serialize_teacher_gold_evaluation,
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
    return TeacherGoldReferenceCase(
        case_id=case_id,
        split=split,
        expected_state=state,
        expected_candidates=tuple(candidates),
        public_request={"case_id": case_id},
        expected_inversion="root_position" if state is FinalDecisionState.RESOLVED else None,
        teacher_reason="Human verified frozen reference.",
    )


def calibration_cases():
    return tuple(
        reference_case(case_id, BenchmarkSplit.CALIBRATION)
        for case_id in CALIBRATION_V0_1_CASE_IDS
    )


def holdout_cases():
    return tuple(
        reference_case(case_id, BenchmarkSplit.HOLDOUT)
        for case_id in HOLDOUT_V0_1_CASE_IDS
    )


def assembly(calibration=None, holdout=None):
    return assemble_frozen_teacher_gold_benchmark_v0_1(
        calibration if calibration is not None else calibration_cases(),
        holdout if holdout is not None else holdout_cases(),
    )


def identity_payload(identity):
    return {
        "root_pc": identity.root_pc,
        "family": identity.family.value,
        "variant": identity.variant,
    }


def public_result(
    *,
    state="resolved",
    identities=(C_MAJOR,),
    marker=None,
):
    result = {
        "schema_name": PUBLIC_RESULT_SCHEMA_NAME,
        "schema_version": PUBLIC_RESULT_SCHEMA_VERSION,
        "results": [
            {
                "measure_number": 1,
                "start": {"numerator": 0, "denominator": 1},
                "end": {"numerator": 1, "denominator": 1},
                "decision": {
                    "state": state,
                    "source_status": "resolved" if state in {"resolved", "abstain"} else state,
                    "candidates": [
                        {
                            "identity": identity_payload(identity),
                            "evidence": ["exact"],
                        }
                        for identity in identities
                    ],
                    "confidence": None,
                    "abstention_reason": None,
                },
            }
        ],
    }
    if marker is not None:
        result["results"][0]["measure_number"] = marker
    return result


class TeacherGoldEvaluationTests(unittest.TestCase):
    def test_all_supported_cases_can_score_perfectly(self):
        target = assembly()
        with patch(
            "st_guitar_harmonic_engine.teacher_gold_evaluation.execute_public_request",
            return_value=public_result(),
        ) as executor:
            report = evaluate_teacher_gold_assembly(target)

        self.assertEqual(report.reference_case_count, 200)
        self.assertEqual(report.executable_case_count, 200)
        self.assertEqual(report.reference_only_case_count, 0)
        self.assertEqual(report.correct_case_count, 200)
        self.assertEqual(report.state_match_count, 200)
        self.assertEqual(report.identity_applicable_count, 200)
        self.assertEqual(report.identity_match_count, 200)
        self.assertEqual(report.validation_or_runtime_error_count, 0)
        self.assertTrue(report.deterministic_stable)
        self.assertEqual(report.executable_coverage, 1.0)
        self.assertEqual(report.musical_accuracy, 1.0)
        self.assertEqual(report.state_accuracy, 1.0)
        self.assertEqual(report.identity_accuracy, 1.0)
        self.assertEqual(executor.call_count, 400)

    def test_reference_only_case_is_preserved_and_never_executed(self):
        calibration = list(calibration_cases())
        calibration[0] = reference_case(
            "TG-0001",
            BenchmarkSplit.CALIBRATION,
            candidates=(candidate("C6", None),),
        )
        target = assembly(tuple(calibration))
        executed_ids = []

        def execute(payload):
            executed_ids.append(payload["case_id"])
            return public_result()

        with patch(
            "st_guitar_harmonic_engine.teacher_gold_evaluation.execute_public_request",
            side_effect=execute,
        ):
            report = evaluate_teacher_gold_assembly(target)

        self.assertEqual(report.reference_case_count, 200)
        self.assertEqual(report.executable_case_count, 199)
        self.assertEqual(report.reference_only_case_count, 1)
        self.assertEqual(report.correct_case_count, 199)
        self.assertEqual(report.executable_coverage, 199 / 200)
        self.assertEqual(report.musical_accuracy, 1.0)
        self.assertNotIn("TG-0001", executed_ids)
        first = report.cases[0]
        self.assertTrue(first.reference_only)
        self.assertIsNone(first.actual_state)
        self.assertIsNone(first.state_match)
        self.assertIsNone(first.identity_match)

    def test_state_mismatch_counts_as_incorrect(self):
        target = assembly()

        def execute(payload):
            if payload["case_id"] == "TG-0001":
                return public_result(state="abstain", identities=(C_MAJOR,))
            return public_result()

        with patch(
            "st_guitar_harmonic_engine.teacher_gold_evaluation.execute_public_request",
            side_effect=execute,
        ):
            report = evaluate_teacher_gold_assembly(target)

        first = report.cases[0]
        self.assertFalse(first.state_match)
        self.assertTrue(first.identity_match)
        self.assertFalse(first.is_correct)
        self.assertEqual(report.correct_case_count, 199)
        self.assertEqual(report.state_match_count, 199)
        self.assertEqual(report.musical_accuracy, 199 / 200)

    def test_identity_mismatch_counts_as_incorrect_even_when_state_matches(self):
        target = assembly()

        def execute(payload):
            if payload["case_id"] == "TG-0001":
                return public_result(identities=(D_MAJOR,))
            return public_result()

        with patch(
            "st_guitar_harmonic_engine.teacher_gold_evaluation.execute_public_request",
            side_effect=execute,
        ):
            report = evaluate_teacher_gold_assembly(target)

        first = report.cases[0]
        self.assertTrue(first.state_match)
        self.assertFalse(first.identity_match)
        self.assertFalse(first.is_correct)
        self.assertEqual(report.state_match_count, 200)
        self.assertEqual(report.identity_match_count, 199)
        self.assertEqual(report.correct_case_count, 199)

    def test_abstain_and_no_match_are_scored_by_state_only(self):
        holdout = list(holdout_cases())
        holdout[0] = reference_case(
            "TG-0101",
            BenchmarkSplit.HOLDOUT,
            state=FinalDecisionState.ABSTAIN,
            candidates=(),
        )
        holdout[1] = reference_case(
            "TG-0102",
            BenchmarkSplit.HOLDOUT,
            state=FinalDecisionState.NO_MATCH,
            candidates=(),
        )
        target = assembly(holdout=tuple(holdout))

        def execute(payload):
            if payload["case_id"] == "TG-0101":
                return public_result(state="abstain", identities=())
            if payload["case_id"] == "TG-0102":
                return public_result(state="no_match", identities=())
            return public_result()

        with patch(
            "st_guitar_harmonic_engine.teacher_gold_evaluation.execute_public_request",
            side_effect=execute,
        ):
            report = evaluate_teacher_gold_assembly(target)

        by_id = {item.case_id: item for item in report.cases}
        self.assertTrue(by_id["TG-0101"].is_correct)
        self.assertTrue(by_id["TG-0102"].is_correct)
        self.assertIsNone(by_id["TG-0101"].identity_match)
        self.assertIsNone(by_id["TG-0102"].identity_match)
        self.assertEqual(report.identity_applicable_count, 198)
        self.assertEqual(report.correct_case_count, 200)

    def test_nondeterministic_case_is_isolated_and_counts_against_accuracy(self):
        target = assembly()
        calls = {}

        def execute(payload):
            case_id = payload["case_id"]
            calls[case_id] = calls.get(case_id, 0) + 1
            if case_id == "TG-0001":
                return public_result(marker=calls[case_id])
            return public_result()

        with patch(
            "st_guitar_harmonic_engine.teacher_gold_evaluation.execute_public_request",
            side_effect=execute,
        ):
            report = evaluate_teacher_gold_assembly(target)

        first = report.cases[0]
        self.assertEqual(first.error_type, "NondeterministicOutput")
        self.assertFalse(first.deterministic_stable)
        self.assertFalse(report.deterministic_stable)
        self.assertEqual(report.validation_or_runtime_error_count, 1)
        self.assertEqual(report.correct_case_count, 199)
        self.assertEqual(len(report.cases), 200)

    def test_runtime_failure_is_isolated_and_later_cases_still_execute(self):
        target = assembly()
        calls = []

        def execute(payload):
            case_id = payload["case_id"]
            calls.append(case_id)
            if case_id == "TG-0001":
                raise RuntimeError("isolated benchmark failure")
            return public_result()

        with patch(
            "st_guitar_harmonic_engine.teacher_gold_evaluation.execute_public_request",
            side_effect=execute,
        ):
            report = evaluate_teacher_gold_assembly(target)

        self.assertEqual(report.cases[0].error_type, "RuntimeError")
        self.assertIn("TG-0200", calls)
        self.assertEqual(report.validation_or_runtime_error_count, 1)
        self.assertFalse(report.deterministic_stable)
        self.assertEqual(report.correct_case_count, 199)

    def test_serializer_exposes_denominator_and_inversion_limit(self):
        target = assembly()
        with patch(
            "st_guitar_harmonic_engine.teacher_gold_evaluation.execute_public_request",
            return_value=public_result(),
        ):
            report = evaluate_teacher_gold_assembly(target)
        payload = serialize_teacher_gold_evaluation(report)

        self.assertEqual(payload["accuracy_denominator"], TEACHER_GOLD_ACCURACY_DENOMINATOR)
        self.assertEqual(payload["inversion_accuracy_claim"], TEACHER_GOLD_INVERSION_ACCURACY_CLAIM)
        self.assertEqual(payload["reference_case_count"], 200)
        self.assertEqual(payload["executable_case_count"], 200)
        self.assertEqual(len(payload["cases"]), 200)

    def test_repeated_evaluation_is_deterministic(self):
        target = assembly()
        with patch(
            "st_guitar_harmonic_engine.teacher_gold_evaluation.execute_public_request",
            return_value=public_result(),
        ):
            first = evaluate_teacher_gold_assembly(target)
            second = evaluate_teacher_gold_assembly(target)
        self.assertEqual(first, second)
        self.assertEqual(
            serialize_teacher_gold_evaluation(first),
            serialize_teacher_gold_evaluation(second),
        )


if __name__ == "__main__":
    unittest.main()
