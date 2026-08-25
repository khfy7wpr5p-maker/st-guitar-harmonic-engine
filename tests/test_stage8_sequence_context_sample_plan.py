import unittest

from st_guitar_harmonic_engine.stage8_sequence_context_sample_plan import (
    Stage8SampleSourcePlan,
    Stage8SequenceContextSamplePlan,
    Stage8SourceClass,
    canonical_stage8_sequence_context_sample_plan,
)


class Stage8SequenceContextSamplePlanTests(unittest.TestCase):
    def test_canonical_plan_freezes_1200_cases(self):
        plan = canonical_stage8_sequence_context_sample_plan()
        self.assertEqual(plan.target_train_cases, 800)
        self.assertEqual(plan.target_validation_cases, 200)
        self.assertEqual(plan.target_holdout_cases, 200)
        self.assertEqual(plan.total_cases, 1200)
        self.assertFalse(plan.model_training_authorized)
        self.assertFalse(plan.production_authority_granted)

    def test_source_mix_matches_frozen_allocations(self):
        plan = canonical_stage8_sequence_context_sample_plan()
        by_id = {item.source_id: item for item in plan.sources}
        self.assertEqual(by_id["openscore-string-quartets"].total_cases, 600)
        self.assertEqual(by_id["openscore-lieder"].total_cases, 300)
        self.assertEqual(by_id["owned-synthetic-guitar-context"].total_cases, 300)

    def test_noncommercial_and_mixed_sources_receive_zero_allocation(self):
        plan = canonical_stage8_sequence_context_sample_plan()
        blocked = [
            item
            for item in plan.sources
            if item.source_class
            in {
                Stage8SourceClass.NONCOMMERCIAL_REFERENCE_ONLY,
                Stage8SourceClass.MIXED_OR_PER_ITEM_REVIEW,
            }
        ]
        self.assertTrue(blocked)
        self.assertTrue(all(not item.training_eligible and item.total_cases == 0 for item in blocked))

    def test_unsafe_training_source_fails_closed(self):
        with self.assertRaises(ValueError):
            Stage8SampleSourcePlan(
                source_id="unsafe-nc",
                source_class=Stage8SourceClass.NONCOMMERCIAL_REFERENCE_ONLY,
                train_cases=1,
                validation_cases=0,
                holdout_cases=0,
                training_eligible=True,
            )

    def test_nontraining_source_cannot_receive_holdout_allocation(self):
        with self.assertRaises(ValueError):
            Stage8SampleSourcePlan(
                source_id="mixed-source",
                source_class=Stage8SourceClass.MIXED_OR_PER_ITEM_REVIEW,
                train_cases=0,
                validation_cases=0,
                holdout_cases=1,
                training_eligible=False,
            )

    def test_split_sums_fail_closed(self):
        safe = Stage8SampleSourcePlan(
            source_id="owned",
            source_class=Stage8SourceClass.OWNED_SYNTHETIC,
            train_cases=10,
            validation_cases=2,
            holdout_cases=2,
            training_eligible=True,
        )
        with self.assertRaises(ValueError):
            Stage8SequenceContextSamplePlan(
                sources=(safe,),
                target_train_cases=11,
                target_validation_cases=2,
                target_holdout_cases=2,
                group_disjoint_splits_required=True,
                holdout_frozen_before_model_selection=True,
                human_verification_required=True,
            )


if __name__ == "__main__":
    unittest.main()
