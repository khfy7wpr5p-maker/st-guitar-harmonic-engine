import unittest
from dataclasses import replace

from st_guitar_harmonic_engine.stage8_feature_contract import STAGE8_FEATURE_CONTRACT_VERSION
from st_guitar_harmonic_engine.stage8_sequence_context_corpus import (
    Stage8CorpusAnnotationStatus,
    Stage8CorpusSplit,
    Stage8SequenceContextCorpusCase,
    Stage8SequenceContextCorpusStatus,
    assess_sequence_context_corpus,
)
from st_guitar_harmonic_engine.stage8_sequence_context_target import (
    STAGE8_SEQUENCE_CONTEXT_TARGET_ID,
)


ENGINE_SHA = "b9438eca34fbaa570ff51415bdc7c8ed129a5b85"
CANDIDATES = ("0:basic:major_sixth", "9:basic:minor_seventh")


def make_case(
    case_id: str,
    split: Stage8CorpusSplit,
    source_group_id: str,
    source_item_char: str,
    *,
    preferred: str | None = CANDIDATES[0],
    no_preference: bool = False,
    status: Stage8CorpusAnnotationStatus = Stage8CorpusAnnotationStatus.VERIFIED,
) -> Stage8SequenceContextCorpusCase:
    return Stage8SequenceContextCorpusCase(
        case_id=case_id,
        target_id=STAGE8_SEQUENCE_CONTEXT_TARGET_ID,
        split=split,
        source_id="owned-research-source",
        source_group_id=source_group_id,
        source_item_sha256=source_item_char * 64,
        candidate_set_sha256=("f" if source_item_char != "f" else "e") * 64,
        candidate_ids=CANDIDATES,
        preferred_candidate_id=preferred,
        no_preference=no_preference,
        annotation_status=status,
        rights_governance_passed=True,
        teacher_gold_overlap=False,
        holdout_overlap=False,
        derived_from_holdout_labels=False,
        feature_contract_version=STAGE8_FEATURE_CONTRACT_VERSION,
        deterministic_engine_sha=ENGINE_SHA,
    )


class Stage8SequenceContextCorpusTests(unittest.TestCase):
    def test_verified_disjoint_train_validation_metadata_is_ready_but_not_training_authority(self):
        cases = (
            make_case("SC-00001", Stage8CorpusSplit.TRAIN, "group-train-a", "a"),
            make_case("SC-00002", Stage8CorpusSplit.VALIDATION, "group-val-a", "b"),
        )
        result = assess_sequence_context_corpus(cases)
        self.assertIs(result.status, Stage8SequenceContextCorpusStatus.CORPUS_DESIGN_READY)
        self.assertEqual(result.train_case_count, 1)
        self.assertEqual(result.validation_case_count, 1)
        self.assertFalse(result.model_training_authorized)
        self.assertFalse(result.production_authority_granted)

    def test_no_preference_is_valid_human_outcome(self):
        cases = (
            make_case(
                "SC-00001",
                Stage8CorpusSplit.TRAIN,
                "group-train-a",
                "a",
                preferred=None,
                no_preference=True,
            ),
            make_case("SC-00002", Stage8CorpusSplit.VALIDATION, "group-val-a", "b"),
        )
        result = assess_sequence_context_corpus(cases)
        self.assertIs(result.status, Stage8SequenceContextCorpusStatus.CORPUS_DESIGN_READY)
        self.assertEqual(result.no_preference_case_count, 1)

    def test_teacher_gold_or_holdout_overlap_fails_closed(self):
        leaked = replace(
            make_case("SC-00001", Stage8CorpusSplit.TRAIN, "group-train-a", "a"),
            teacher_gold_overlap=True,
            holdout_overlap=True,
            derived_from_holdout_labels=True,
        )
        result = assess_sequence_context_corpus((leaked,))
        self.assertIs(result.status, Stage8SequenceContextCorpusStatus.BLOCKED_DATA_LEAKAGE)

    def test_unverified_human_annotation_is_not_ready(self):
        cases = (
            make_case(
                "SC-00001",
                Stage8CorpusSplit.TRAIN,
                "group-train-a",
                "a",
                preferred=None,
                status=Stage8CorpusAnnotationStatus.DRAFT,
            ),
            make_case("SC-00002", Stage8CorpusSplit.VALIDATION, "group-val-a", "b"),
        )
        result = assess_sequence_context_corpus(cases)
        self.assertIs(result.status, Stage8SequenceContextCorpusStatus.BLOCKED_ANNOTATION)

    def test_source_group_cannot_cross_train_and_validation(self):
        cases = (
            make_case("SC-00001", Stage8CorpusSplit.TRAIN, "same-group", "a"),
            make_case("SC-00002", Stage8CorpusSplit.VALIDATION, "same-group", "b"),
        )
        result = assess_sequence_context_corpus(cases)
        self.assertIs(result.status, Stage8SequenceContextCorpusStatus.BLOCKED_SPLIT_LEAKAGE)

    def test_both_partitions_are_required(self):
        cases = (
            make_case("SC-00001", Stage8CorpusSplit.TRAIN, "group-train-a", "a"),
            make_case("SC-00002", Stage8CorpusSplit.TRAIN, "group-train-b", "b"),
        )
        result = assess_sequence_context_corpus(cases)
        self.assertIs(result.status, Stage8SequenceContextCorpusStatus.BLOCKED_SPLIT_LEAKAGE)

    def test_duplicate_source_item_is_blocked(self):
        first = make_case("SC-00001", Stage8CorpusSplit.TRAIN, "group-train-a", "a")
        second = replace(
            make_case("SC-00002", Stage8CorpusSplit.VALIDATION, "group-val-a", "b"),
            source_item_sha256=first.source_item_sha256,
        )
        result = assess_sequence_context_corpus((first, second))
        self.assertIs(result.status, Stage8SequenceContextCorpusStatus.BLOCKED_DUPLICATE)

    def test_verified_case_must_choose_candidate_or_explicit_no_preference(self):
        with self.assertRaises(ValueError):
            make_case(
                "SC-00001",
                Stage8CorpusSplit.TRAIN,
                "group-train-a",
                "a",
                preferred=None,
                no_preference=False,
            )

    def test_preferred_candidate_must_be_from_deterministic_candidate_set(self):
        with self.assertRaises(ValueError):
            make_case(
                "SC-00001",
                Stage8CorpusSplit.TRAIN,
                "group-train-a",
                "a",
                preferred="5:basic:major",
            )


if __name__ == "__main__":
    unittest.main()
