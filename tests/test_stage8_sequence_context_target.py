import unittest
from dataclasses import replace

from st_guitar_harmonic_engine.stage8_sequence_context_target import (
    Stage8SequenceContextTargetStatus,
    approved_sequence_context_target,
    assess_sequence_context_target,
)


class Stage8SequenceContextTargetTests(unittest.TestCase):
    def test_canonical_target_is_design_eligible_but_not_training_authority(self):
        result = assess_sequence_context_target(approved_sequence_context_target())
        self.assertIs(result.status, Stage8SequenceContextTargetStatus.TARGET_DESIGN_ELIGIBLE)
        self.assertTrue(result.research_design_authorized)
        self.assertFalse(result.model_training_authorized)
        self.assertFalse(result.production_authority_granted)

    def test_future_frame_access_fails_closed(self):
        unsafe = replace(approved_sequence_context_target(), uses_future_frames=True)
        result = assess_sequence_context_target(unsafe)
        self.assertIs(result.status, Stage8SequenceContextTargetStatus.BLOCKED_NONCAUSAL_CONTEXT)

    def test_candidate_generation_or_authority_change_is_blocked(self):
        unsafe = replace(
            approved_sequence_context_target(),
            may_generate_candidates=True,
            may_change_authoritative_state=True,
        )
        result = assess_sequence_context_target(unsafe)
        self.assertIs(result.status, Stage8SequenceContextTargetStatus.BLOCKED_AUTHORITY_RISK)
        self.assertEqual(
            result.reasons,
            ("authoritative_state_change_forbidden", "candidate_generation_forbidden"),
        )

    def test_non_ambiguous_source_scope_is_blocked(self):
        unsafe = replace(
            approved_sequence_context_target(),
            requires_source_state_ambiguous=False,
        )
        result = assess_sequence_context_target(unsafe)
        self.assertIs(result.status, Stage8SequenceContextTargetStatus.BLOCKED_AUTHORITY_RISK)

    def test_teacher_gold_or_holdout_labels_are_blocked(self):
        unsafe = replace(
            approved_sequence_context_target(),
            teacher_gold_labels_available_to_model=True,
            holdout_labels_available_to_model=True,
            derived_from_holdout_labels=True,
        )
        result = assess_sequence_context_target(unsafe)
        self.assertIs(result.status, Stage8SequenceContextTargetStatus.BLOCKED_LABEL_LEAKAGE)
        self.assertEqual(
            result.reasons,
            (
                "holdout_derived_target_forbidden",
                "holdout_labels_forbidden",
                "teacher_gold_labels_forbidden",
            ),
        )

    def test_target_identity_is_fixed(self):
        wrong = replace(approved_sequence_context_target(), target_id="other-target")
        result = assess_sequence_context_target(wrong)
        self.assertIs(result.status, Stage8SequenceContextTargetStatus.BLOCKED_TARGET_MISMATCH)

    def test_previous_context_is_bounded_by_constructor(self):
        with self.assertRaises(ValueError):
            replace(approved_sequence_context_target(), previous_frame_limit=5)


if __name__ == "__main__":
    unittest.main()
