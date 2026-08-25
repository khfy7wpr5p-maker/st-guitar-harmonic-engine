import hashlib
import unittest

from st_guitar_harmonic_engine.stage8_feature_contract import STAGE8_FEATURE_CONTRACT_VERSION
from st_guitar_harmonic_engine.stage8_sequence_context_holdout import (
    Stage8HoldoutAnnotationStatus,
    Stage8SequenceContextHoldoutCase,
    Stage8SequenceContextHoldoutStatus,
    assess_sequence_context_holdout,
)
from st_guitar_harmonic_engine.stage8_sequence_context_target import STAGE8_SEQUENCE_CONTEXT_TARGET_ID


ENGINE_SHA = "a" * 40


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _source_for(index: int) -> str:
    if index <= 100:
        return "openscore-string-quartets"
    if index <= 150:
        return "openscore-lieder"
    return "owned-synthetic-guitar-context"


def _cases() -> tuple[Stage8SequenceContextHoldoutCase, ...]:
    result = []
    for index in range(1, 201):
        source = _source_for(index)
        result.append(
            Stage8SequenceContextHoldoutCase(
                case_id=f"SCH-{index:05d}",
                target_id=STAGE8_SEQUENCE_CONTEXT_TARGET_ID,
                source_id=source,
                source_group_id=f"holdout-group-{index:05d}",
                source_item_sha256=_sha(f"source-{index}"),
                candidate_set_sha256=_sha(f"candidates-{index}"),
                candidate_ids=("candidate-a", "candidate-b"),
                preferred_candidate_id="candidate-a",
                no_preference=False,
                annotation_status=Stage8HoldoutAnnotationStatus.VERIFIED,
                rights_governance_passed=True,
                teacher_gold_overlap=False,
                teacher_gold_holdout_overlap=False,
                training_corpus_overlap=False,
                derived_from_teacher_gold_or_holdout_labels=False,
                feature_contract_version=STAGE8_FEATURE_CONTRACT_VERSION,
                deterministic_engine_sha=ENGINE_SHA,
            )
        )
    return tuple(result)


class Stage8SequenceContextHoldoutTests(unittest.TestCase):
    def test_canonical_200_case_holdout_is_freeze_ready(self):
        result = assess_sequence_context_holdout(
            _cases(),
            training_source_group_ids=frozenset({"train-group"}),
            validation_source_group_ids=frozenset({"validation-group"}),
        )
        self.assertIs(result.status, Stage8SequenceContextHoldoutStatus.HOLDOUT_FREEZE_READY)
        self.assertEqual(result.case_count, 200)
        self.assertEqual(result.verified_case_count, 200)
        self.assertFalse(result.model_selection_authorized)
        self.assertFalse(result.model_training_authorized)
        self.assertFalse(result.production_authority_granted)

    def test_wrong_count_fails_closed(self):
        result = assess_sequence_context_holdout(
            _cases()[:-1],
            training_source_group_ids=frozenset(),
            validation_source_group_ids=frozenset(),
        )
        self.assertIs(result.status, Stage8SequenceContextHoldoutStatus.BLOCKED_COUNT_OR_NAMESPACE)

    def test_group_overlap_fails_closed(self):
        cases = _cases()
        result = assess_sequence_context_holdout(
            cases,
            training_source_group_ids=frozenset({cases[0].source_group_id}),
            validation_source_group_ids=frozenset(),
        )
        self.assertIs(result.status, Stage8SequenceContextHoldoutStatus.BLOCKED_SPLIT_LEAKAGE)

    def test_reference_leakage_fails_closed(self):
        cases = list(_cases())
        first = cases[0]
        cases[0] = Stage8SequenceContextHoldoutCase(
            **{**first.__dict__, "teacher_gold_holdout_overlap": True}
        )
        result = assess_sequence_context_holdout(
            tuple(cases),
            training_source_group_ids=frozenset(),
            validation_source_group_ids=frozenset(),
        )
        self.assertIs(result.status, Stage8SequenceContextHoldoutStatus.BLOCKED_DATA_LEAKAGE)

    def test_wrong_source_allocation_fails_closed(self):
        cases = list(_cases())
        first = cases[0]
        cases[0] = Stage8SequenceContextHoldoutCase(
            **{**first.__dict__, "source_id": "owned-synthetic-guitar-context"}
        )
        result = assess_sequence_context_holdout(
            tuple(cases),
            training_source_group_ids=frozenset(),
            validation_source_group_ids=frozenset(),
        )
        self.assertIs(result.status, Stage8SequenceContextHoldoutStatus.BLOCKED_SOURCE_ALLOCATION)

    def test_draft_case_blocks_freeze(self):
        cases = list(_cases())
        first = cases[0]
        cases[0] = Stage8SequenceContextHoldoutCase(
            **{
                **first.__dict__,
                "annotation_status": Stage8HoldoutAnnotationStatus.DRAFT,
                "preferred_candidate_id": None,
            }
        )
        result = assess_sequence_context_holdout(
            tuple(cases),
            training_source_group_ids=frozenset(),
            validation_source_group_ids=frozenset(),
        )
        self.assertIs(result.status, Stage8SequenceContextHoldoutStatus.BLOCKED_ANNOTATION)


if __name__ == "__main__":
    unittest.main()
