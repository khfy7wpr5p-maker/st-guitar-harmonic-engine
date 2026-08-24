import unittest

from st_guitar_harmonic_engine.stage8_model_entry_gate import (
    Stage8DeterministicSummary,
    Stage8ModelEntryStatus,
    Stage8ResearchTarget,
    assess_stage8_model_entry,
)


def solved_summary():
    return Stage8DeterministicSummary(200, 200, 200, 0, True)


def imperfect_summary():
    return Stage8DeterministicSummary(200, 200, 192, 0, True)


class Stage8ModelEntryGateTests(unittest.TestCase):
    def test_fully_solved_teacher_gold_blocks_model_target_inference(self):
        result = assess_stage8_model_entry(solved_summary())
        self.assertIs(result.status, Stage8ModelEntryStatus.BLOCKED_DETERMINISTIC_SUFFICIENT)
        self.assertFalse(result.model_training_authorized)
        self.assertFalse(result.production_authority_granted)

    def test_imperfect_reference_still_requires_separate_disjoint_target(self):
        result = assess_stage8_model_entry(imperfect_summary())
        self.assertIs(result.status, Stage8ModelEntryStatus.BLOCKED_NO_DISJOINT_TARGET)

    def test_teacher_gold_or_holdout_overlap_fails_closed(self):
        target = Stage8ResearchTarget(
            target_id="context-hard-v1",
            case_count=50,
            preregistered=True,
            authorized_source=True,
            teacher_gold_overlap_count=1,
            holdout_overlap_count=1,
            derived_from_holdout_labels=True,
        )
        result = assess_stage8_model_entry(imperfect_summary(), target)
        self.assertIs(result.status, Stage8ModelEntryStatus.BLOCKED_DATA_LEAKAGE)
        self.assertEqual(
            result.reasons,
            (
                "holdout_overlap_present",
                "target_derived_from_holdout_labels",
                "teacher_gold_overlap_present",
            ),
        )

    def test_unregistered_or_unauthorized_target_is_blocked(self):
        target = Stage8ResearchTarget(
            target_id="context-hard-v1",
            case_count=50,
            preregistered=False,
            authorized_source=False,
            teacher_gold_overlap_count=0,
            holdout_overlap_count=0,
            derived_from_holdout_labels=False,
        )
        result = assess_stage8_model_entry(imperfect_summary(), target)
        self.assertIs(result.status, Stage8ModelEntryStatus.BLOCKED_TARGET_NOT_READY)
        self.assertEqual(
            result.reasons,
            ("target_not_preregistered", "target_source_not_authorized"),
        )

    def test_disjoint_authorized_target_only_allows_research_design(self):
        target = Stage8ResearchTarget(
            target_id="context-hard-v1",
            case_count=50,
            preregistered=True,
            authorized_source=True,
            teacher_gold_overlap_count=0,
            holdout_overlap_count=0,
            derived_from_holdout_labels=False,
        )
        result = assess_stage8_model_entry(imperfect_summary(), target)
        self.assertIs(result.status, Stage8ModelEntryStatus.SHADOW_RESEARCH_DESIGN_ELIGIBLE)
        self.assertEqual(result.reasons, ())
        self.assertFalse(result.model_training_authorized)
        self.assertFalse(result.production_authority_granted)

    def test_incomplete_deterministic_evidence_blocks_everything(self):
        incomplete = Stage8DeterministicSummary(199, 199, 199, 0, True)
        target = Stage8ResearchTarget(
            target_id="context-hard-v1",
            case_count=10,
            preregistered=True,
            authorized_source=True,
            teacher_gold_overlap_count=0,
            holdout_overlap_count=0,
            derived_from_holdout_labels=False,
        )
        result = assess_stage8_model_entry(incomplete, target)
        self.assertIs(
            result.status,
            Stage8ModelEntryStatus.BLOCKED_DETERMINISTIC_EVIDENCE_INCOMPLETE,
        )


if __name__ == "__main__":
    unittest.main()
