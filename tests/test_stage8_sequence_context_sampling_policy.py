import unittest

from st_guitar_harmonic_engine.stage8_sequence_context_sampling_policy import (
    Stage8OpenScorePilotEvidence,
    Stage8SamplingSourcePolicy,
    Stage8SequenceContextSamplingPolicy,
    canonical_stage8_sequence_context_sampling_policy,
)


class Stage8SequenceContextSamplingPolicyTests(unittest.TestCase):
    def test_canonical_policy_preserves_frozen_1200_case_target(self):
        policy = canonical_stage8_sequence_context_sampling_policy()
        self.assertEqual(policy.final_case_target, 1200)
        self.assertEqual(policy.review_pool_target, 2400)
        self.assertFalse(policy.model_training_authorized)
        self.assertFalse(policy.production_authority_granted)

    def test_review_buffers_and_diversity_caps_are_frozen(self):
        policy = canonical_stage8_sequence_context_sampling_policy()
        by_id = {item.source_id: item for item in policy.sources}

        quartets = by_id["openscore-string-quartets"]
        self.assertEqual(quartets.final_case_target, 600)
        self.assertEqual(quartets.review_pool_target, 1200)
        self.assertEqual(quartets.max_cases_per_source_item, 20)
        self.assertEqual(quartets.max_cases_per_composer, 100)
        self.assertEqual(quartets.min_distinct_composers, 6)

        lieder = by_id["openscore-lieder"]
        self.assertEqual(lieder.final_case_target, 300)
        self.assertEqual(lieder.review_pool_target, 600)
        self.assertEqual(lieder.max_cases_per_source_item, 10)
        self.assertEqual(lieder.max_cases_per_composer, 45)
        self.assertEqual(lieder.min_distinct_composers, 7)

    def test_pilot_evidence_is_aggregate_and_never_auto_included(self):
        policy = canonical_stage8_sequence_context_sampling_policy()
        evidence = {item.source_id: item for item in policy.pilot_evidence}

        quartets = evidence["openscore-string-quartets"]
        self.assertEqual(quartets.harmonic_frame_count, 52209)
        self.assertEqual(quartets.ambiguous_candidate_count, 1755)
        self.assertEqual(
            quartets.output_sha256,
            "12d6af3b3796c932295bfc61482e2d6d00f7c38c199b21dd2c0f1be78bfd9a46",
        )
        self.assertTrue(quartets.pipeline_evidence_only)
        self.assertFalse(quartets.auto_inclusion_in_final_corpus)

        lieder = evidence["openscore-lieder"]
        self.assertEqual(lieder.harmonic_frame_count, 4047)
        self.assertEqual(lieder.ambiguous_candidate_count, 235)
        self.assertEqual(
            lieder.output_sha256,
            "b52fff82e8082046c831cd67bb9bbc2e565372f6279b9129001aea761882952e",
        )

    def test_buffer_smaller_than_2x_fails_closed(self):
        with self.assertRaises(ValueError):
            Stage8SamplingSourcePolicy(
                source_id="openscore-lieder",
                final_case_target=300,
                review_pool_target=599,
                max_cases_per_source_item=10,
                max_cases_per_source_group=20,
                max_cases_per_candidate_set=45,
                min_distinct_source_groups=15,
                max_cases_per_composer=45,
                min_distinct_composers=7,
            )

    def test_weak_group_diversity_floor_fails_closed(self):
        with self.assertRaises(ValueError):
            Stage8SamplingSourcePolicy(
                source_id="openscore-string-quartets",
                final_case_target=600,
                review_pool_target=1200,
                max_cases_per_source_item=20,
                max_cases_per_source_group=20,
                max_cases_per_candidate_set=90,
                min_distinct_source_groups=29,
                max_cases_per_composer=100,
                min_distinct_composers=6,
            )

    def test_pilot_cannot_authorize_training_or_auto_inclusion(self):
        kwargs = dict(
            source_id="openscore-lieder",
            source_item_count=10,
            harmonic_frame_count=4047,
            ambiguous_candidate_count=235,
            manifest_sha256="1" * 64,
            candidate_pool_sha256="2" * 64,
            output_sha256="3" * 64,
        )
        with self.assertRaises(ValueError):
            Stage8OpenScorePilotEvidence(**kwargs, auto_inclusion_in_final_corpus=True)
        with self.assertRaises(ValueError):
            Stage8OpenScorePilotEvidence(**kwargs, model_training_authorized=True)

    def test_policy_targets_cannot_drift_from_sample_plan(self):
        safe = Stage8SamplingSourcePolicy(
            source_id="openscore-string-quartets",
            final_case_target=599,
            review_pool_target=1198,
            max_cases_per_source_item=20,
            max_cases_per_source_group=20,
            max_cases_per_candidate_set=90,
            min_distinct_source_groups=30,
            max_cases_per_composer=100,
            min_distinct_composers=6,
        )
        with self.assertRaises(ValueError):
            Stage8SequenceContextSamplingPolicy(
                sources=(safe,),
                pilot_evidence=(),
                deterministic_selection_required=True,
                group_disjoint_partitions_required=True,
                holdout_selected_without_model_feedback=True,
                human_verification_required=True,
                pilot_auto_inclusion_forbidden=True,
            )


if __name__ == "__main__":
    unittest.main()
