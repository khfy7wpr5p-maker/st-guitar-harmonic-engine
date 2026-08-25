import unittest

from st_guitar_harmonic_engine.stage8_research_preregistration import (
    Stage8PrimaryMetric,
    Stage8PreregistrationStatus,
    Stage8ResearchPreregistration,
    assess_stage8_research_preregistration,
)


DATASET_SHA = "a" * 64
ENGINE_SHA = "b" * 40


def preregistration(**overrides):
    values = {
        "target_id": "context-hard-v1",
        "objective_id": "candidate-disambiguation-v1",
        "primary_metric": Stage8PrimaryMetric.FALSE_RESOLUTION_RATE,
        "dataset_manifest_sha256": DATASET_SHA,
        "deterministic_engine_sha": ENGINE_SHA,
        "train_case_count": 80,
        "validation_case_count": 20,
        "teacher_gold_overlap_count": 0,
        "holdout_overlap_count": 0,
        "uses_holdout_for_model_selection": False,
        "derived_from_holdout_labels": False,
        "data_governance_passed": True,
        "target_authorized": True,
        "frozen_before_training": True,
    }
    values.update(overrides)
    return Stage8ResearchPreregistration(**values)


class Stage8ResearchPreregistrationTests(unittest.TestCase):
    def test_valid_preregistration_is_design_only(self):
        item = preregistration()
        result = assess_stage8_research_preregistration(item)
        self.assertIs(
            result.status,
            Stage8PreregistrationStatus.RESEARCH_DESIGN_PREREGISTERED,
        )
        self.assertEqual(result.reasons, ())
        self.assertEqual(result.preregistration_sha256, item.canonical_sha256)
        self.assertFalse(result.model_training_authorized)
        self.assertFalse(result.production_authority_granted)

    def test_empty_training_partition_fails_closed(self):
        result = assess_stage8_research_preregistration(
            preregistration(train_case_count=0, validation_case_count=20)
        )
        self.assertIs(result.status, Stage8PreregistrationStatus.BLOCKED_INCOMPLETE)

    def test_teacher_gold_and_holdout_leakage_fail_closed(self):
        result = assess_stage8_research_preregistration(
            preregistration(
                teacher_gold_overlap_count=1,
                holdout_overlap_count=1,
                uses_holdout_for_model_selection=True,
                derived_from_holdout_labels=True,
            )
        )
        self.assertIs(result.status, Stage8PreregistrationStatus.BLOCKED_DATA_LEAKAGE)
        self.assertEqual(
            result.reasons,
            (
                "holdout_overlap_present",
                "holdout_used_for_model_selection",
                "target_derived_from_holdout_labels",
                "teacher_gold_overlap_present",
            ),
        )

    def test_governance_and_target_authorization_are_both_required(self):
        result = assess_stage8_research_preregistration(
            preregistration(data_governance_passed=False, target_authorized=False)
        )
        self.assertIs(result.status, Stage8PreregistrationStatus.BLOCKED_GOVERNANCE)
        self.assertEqual(
            result.reasons,
            ("data_governance_not_passed", "research_target_not_authorized"),
        )

    def test_preregistration_must_be_frozen_before_training(self):
        result = assess_stage8_research_preregistration(
            preregistration(frozen_before_training=False)
        )
        self.assertIs(result.status, Stage8PreregistrationStatus.BLOCKED_NOT_FROZEN)

    def test_digest_changes_when_metric_changes(self):
        first = preregistration(primary_metric=Stage8PrimaryMetric.FALSE_RESOLUTION_RATE)
        second = preregistration(primary_metric=Stage8PrimaryMetric.AMBIGUITY_RECALL)
        self.assertNotEqual(first.canonical_sha256, second.canonical_sha256)

    def test_digest_is_deterministic(self):
        first = preregistration()
        second = preregistration()
        self.assertEqual(first.canonical_sha256, second.canonical_sha256)


if __name__ == "__main__":
    unittest.main()
