import unittest
from dataclasses import replace

from st_guitar_harmonic_engine.stage8_feature_contract import (
    Stage8FeatureContractStatus,
    Stage8FeatureSchema,
    Stage8FeatureSource,
    Stage8FeatureSpec,
    assess_stage8_feature_schema,
    canonical_stage8_feature_schema,
)


class Stage8FeatureContractTests(unittest.TestCase):
    def test_canonical_schema_is_frozen_but_not_training_authority(self):
        schema = canonical_stage8_feature_schema()
        result = assess_stage8_feature_schema(schema)
        self.assertIs(result.status, Stage8FeatureContractStatus.FEATURE_SCHEMA_FROZEN)
        self.assertGreater(result.feature_count, 0)
        self.assertFalse(result.model_training_authorized)
        self.assertFalse(result.production_authority_granted)

    def test_schema_has_no_future_or_next_features(self):
        schema = canonical_stage8_feature_schema()
        ids = {item.feature_id for item in schema.features}
        self.assertFalse(any("future" in item or "next_" in item for item in ids))
        self.assertNotIn("phrase_length", ids)
        self.assertFalse(any("adjacent_context" in item for item in ids))
        self.assertFalse(any("voice_function" in item for item in ids))

    def test_previous_features_are_bounded_to_four_frames(self):
        schema = canonical_stage8_feature_schema()
        lookbacks = {
            item.lookback
            for item in schema.features
            if item.source is Stage8FeatureSource.PREVIOUS_FRAME
        }
        self.assertEqual(lookbacks, {1, 2, 3, 4})

    def test_teacher_gold_or_holdout_feature_fails_closed(self):
        schema = canonical_stage8_feature_schema()
        leaked = Stage8FeatureSpec(
            "teacher_gold_label",
            Stage8FeatureSource.CURRENT_FRAME,
            0,
            False,
        )
        result = assess_stage8_feature_schema(
            replace(schema, features=schema.features + (leaked,))
        )
        self.assertIs(result.status, Stage8FeatureContractStatus.BLOCKED_UNAPPROVED_FEATURE)
        self.assertIn(
            "teacher_gold_label:forbidden_leakage_surface",
            result.reasons,
        )

    def test_next_frame_proxy_feature_fails_closed(self):
        schema = canonical_stage8_feature_schema()
        leaked = Stage8FeatureSpec(
            "next_resolved_root_pc",
            Stage8FeatureSource.CURRENT_FRAME,
            0,
            False,
        )
        result = assess_stage8_feature_schema(
            replace(schema, features=schema.features + (leaked,))
        )
        self.assertIs(result.status, Stage8FeatureContractStatus.BLOCKED_UNAPPROVED_FEATURE)

    def test_existing_bidirectional_evidence_surfaces_are_forbidden(self):
        schema = canonical_stage8_feature_schema()
        leaked = Stage8FeatureSpec(
            "candidate_has_adjacent_context",
            Stage8FeatureSource.CURRENT_CANDIDATE,
            0,
            True,
        )
        result = assess_stage8_feature_schema(
            replace(schema, features=schema.features + (leaked,))
        )
        self.assertIs(result.status, Stage8FeatureContractStatus.BLOCKED_UNAPPROVED_FEATURE)

    def test_duplicate_feature_spec_is_blocked(self):
        schema = canonical_stage8_feature_schema()
        duplicated = replace(schema, features=schema.features + (schema.features[0],))
        result = assess_stage8_feature_schema(duplicated)
        self.assertIs(result.status, Stage8FeatureContractStatus.BLOCKED_DUPLICATE_FEATURE)

    def test_wrong_target_is_blocked(self):
        schema = replace(canonical_stage8_feature_schema(), target_id="other-target")
        result = assess_stage8_feature_schema(schema)
        self.assertIs(result.status, Stage8FeatureContractStatus.BLOCKED_TARGET_MISMATCH)

    def test_unfrozen_schema_is_blocked(self):
        schema = replace(canonical_stage8_feature_schema(), frozen_before_training=False)
        result = assess_stage8_feature_schema(schema)
        self.assertIs(result.status, Stage8FeatureContractStatus.BLOCKED_UNAPPROVED_FEATURE)

    def test_previous_feature_constructor_rejects_unbounded_lookback(self):
        with self.assertRaises(ValueError):
            Stage8FeatureSpec(
                "previous_state",
                Stage8FeatureSource.PREVIOUS_FRAME,
                5,
                False,
            )


if __name__ == "__main__":
    unittest.main()
