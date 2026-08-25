import hashlib
import unittest

from st_guitar_harmonic_engine.stage8_sequence_context_sampling_leakage_guard import (
    Stage8SamplingLeakageRecord,
    Stage8SamplingLeakageStatus,
    Stage8SamplingPartition,
    assess_sampling_leakage,
)


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _record(
    name,
    *,
    source_id="openscore-lieder",
    group="openscore-lieder:group-a",
    path="scores/Composer/Cycle/Song/lc1.mscx",
    score_sha=None,
    partition=Stage8SamplingPartition.TRAIN,
):
    return Stage8SamplingLeakageRecord(
        candidate_uid=_sha(f"uid:{name}"),
        source_id=source_id,
        source_group_id=group,
        score_relative_path=path,
        source_score_sha256=score_sha or _sha(f"score:{path}"),
        current_frame_sha256=_sha(f"frame:{name}"),
        candidate_set_sha256=_sha("shared-candidate-set"),
        partition=partition,
    )


class Stage8SequenceContextSamplingLeakageGuardTests(unittest.TestCase):
    def test_clean_partial_assignment_passes_without_authority(self):
        records = (
            _record("a"),
            _record(
                "b",
                group="openscore-lieder:group-b",
                path="scores/Composer_B/Cycle_B/Song/lc2.mscx",
                partition=Stage8SamplingPartition.VALIDATION,
            ),
            _record(
                "c",
                group="openscore-lieder:group-c",
                path="scores/Composer_C/Cycle_C/Song/lc3.mscx",
                partition=Stage8SamplingPartition.HOLDOUT,
            ),
        )
        assessment = assess_sampling_leakage(records)
        self.assertIs(assessment.status, Stage8SamplingLeakageStatus.LEAKAGE_GUARD_PASS)
        self.assertFalse(assessment.model_selection_authorized)
        self.assertFalse(assessment.model_training_authorized)
        self.assertFalse(assessment.production_authority_granted)

    def test_multiple_cases_from_same_score_are_allowed_inside_one_partition(self):
        score_sha = _sha("same-score")
        records = (
            _record("a", score_sha=score_sha),
            _record("b", score_sha=score_sha),
        )
        assessment = assess_sampling_leakage(records)
        self.assertIs(assessment.status, Stage8SamplingLeakageStatus.LEAKAGE_GUARD_PASS)

    def test_source_group_crossing_partitions_fails_closed(self):
        records = (
            _record("a"),
            _record(
                "b",
                group="openscore-lieder:group-a",
                path="scores/Composer/Cycle/Other/lc2.mscx",
                partition=Stage8SamplingPartition.HOLDOUT,
            ),
        )
        assessment = assess_sampling_leakage(records)
        self.assertIs(assessment.status, Stage8SamplingLeakageStatus.BLOCKED_CROSS_SPLIT)
        self.assertTrue(any("source_group" in reason for reason in assessment.reasons))

    def test_same_score_crossing_partitions_fails_closed(self):
        score_sha = _sha("same-score")
        records = (
            _record("a", score_sha=score_sha),
            _record(
                "b",
                group="openscore-lieder:group-b",
                score_sha=score_sha,
                partition=Stage8SamplingPartition.VALIDATION,
            ),
        )
        assessment = assess_sampling_leakage(records)
        self.assertIs(assessment.status, Stage8SamplingLeakageStatus.BLOCKED_CROSS_SPLIT)

    def test_duplicate_exact_frame_fails_closed(self):
        first = _record("a")
        second = Stage8SamplingLeakageRecord(
            candidate_uid=_sha("uid:other"),
            source_id=first.source_id,
            source_group_id=first.source_group_id,
            score_relative_path=first.score_relative_path,
            source_score_sha256=first.source_score_sha256,
            current_frame_sha256=first.current_frame_sha256,
            candidate_set_sha256=first.candidate_set_sha256,
            partition=first.partition,
        )
        assessment = assess_sampling_leakage((first, second))
        self.assertIs(assessment.status, Stage8SamplingLeakageStatus.BLOCKED_DUPLICATE)
        self.assertIn("duplicate_current_frame_sha256", assessment.reasons)

    def test_same_source_bytes_under_two_paths_fails_closed(self):
        score_sha = _sha("aliased-score")
        records = (
            _record("a", score_sha=score_sha),
            _record(
                "b",
                group="openscore-lieder:group-b",
                path="scores/Composer_B/Cycle_B/Song/lc2.mscx",
                score_sha=score_sha,
            ),
        )
        assessment = assess_sampling_leakage(records)
        self.assertIs(assessment.status, Stage8SamplingLeakageStatus.BLOCKED_DUPLICATE)
        self.assertTrue(any("multiple_score_paths" in reason for reason in assessment.reasons))

    def test_unapproved_source_fails_closed(self):
        record = _record("a", source_id="unapproved-source", group="unapproved-source:group-a")
        assessment = assess_sampling_leakage((record,))
        self.assertIs(assessment.status, Stage8SamplingLeakageStatus.BLOCKED_SOURCE)

    def test_complete_allocation_mode_rejects_partial_assignment(self):
        assessment = assess_sampling_leakage(
            (_record("a"),),
            require_complete_allocation=True,
        )
        self.assertIs(assessment.status, Stage8SamplingLeakageStatus.BLOCKED_ALLOCATION)

    def test_complete_frozen_1200_case_allocation_passes(self):
        allocations = (
            ("openscore-string-quartets", Stage8SamplingPartition.TRAIN, 400),
            ("openscore-string-quartets", Stage8SamplingPartition.VALIDATION, 100),
            ("openscore-string-quartets", Stage8SamplingPartition.HOLDOUT, 100),
            ("openscore-lieder", Stage8SamplingPartition.TRAIN, 200),
            ("openscore-lieder", Stage8SamplingPartition.VALIDATION, 50),
            ("openscore-lieder", Stage8SamplingPartition.HOLDOUT, 50),
            ("owned-synthetic-guitar-context", Stage8SamplingPartition.TRAIN, 200),
            ("owned-synthetic-guitar-context", Stage8SamplingPartition.VALIDATION, 50),
            ("owned-synthetic-guitar-context", Stage8SamplingPartition.HOLDOUT, 50),
        )
        records = []
        ordinal = 0
        for source_id, partition, count in allocations:
            for index in range(count):
                ordinal += 1
                name = f"{source_id}:{partition.value}:{index}"
                records.append(
                    Stage8SamplingLeakageRecord(
                        candidate_uid=_sha(f"uid:{name}"),
                        source_id=source_id,
                        source_group_id=f"{source_id}:group-{partition.value}-{index}",
                        score_relative_path=f"sampling/{source_id}/{partition.value}/{index}.item",
                        source_score_sha256=_sha(f"score:{name}"),
                        current_frame_sha256=_sha(f"frame:{name}"),
                        candidate_set_sha256=_sha("shared-candidate-set"),
                        partition=partition,
                    )
                )
        assessment = assess_sampling_leakage(
            tuple(records),
            require_complete_allocation=True,
        )
        self.assertEqual(assessment.record_count, 1200)
        self.assertEqual(assessment.train_count, 800)
        self.assertEqual(assessment.validation_count, 200)
        self.assertEqual(assessment.holdout_count, 200)
        self.assertIs(assessment.status, Stage8SamplingLeakageStatus.LEAKAGE_GUARD_PASS)


if __name__ == "__main__":
    unittest.main()
