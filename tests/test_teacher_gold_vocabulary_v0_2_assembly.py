import unittest

from st_guitar_harmonic_engine.calibration import BenchmarkSplit
from st_guitar_harmonic_engine.teacher_gold_benchmark_assembly import (
    assemble_frozen_teacher_gold_benchmark_v0_1,
)
from st_guitar_harmonic_engine.teacher_gold_reference import (
    adapt_teacher_gold_reference_row,
)
from st_guitar_harmonic_engine.teacher_gold_vocabulary_v0_2 import (
    assemble_frozen_teacher_gold_benchmark_v0_2,
)


def row(
    case_id,
    *,
    notes="C3,E3,G3",
    state="RESOLVED",
    primary="C major",
    alternatives="",
    inversion="root_position",
):
    return {
        "example_id": case_id,
        "input_notes": notes,
        "expected_state": state,
        "primary_candidate": primary,
        "acceptable_alternatives": alternatives,
        "inversion": inversion,
        "teacher_reason": "Synthetic contract fixture; not holdout musical content.",
        "annotation_status": "VERIFIED",
    }


def build_partition(start, end, split):
    return [
        adapt_teacher_gold_reference_row(
            row(f"TG-{index:04d}"),
            split=split,
        )
        for index in range(start, end + 1)
    ]


class TeacherGoldVocabularyV02AssemblyTests(unittest.TestCase):
    def test_v0_2_promotes_only_suspended_seventh_reference_gaps(self):
        calibration = build_partition(1, 100, BenchmarkSplit.CALIBRATION)
        holdout = build_partition(101, 200, BenchmarkSplit.HOLDOUT)

        calibration[0] = adapt_teacher_gold_reference_row(
            row(
                "TG-0001",
                notes="C3,F3,G3,Bb3",
                primary="C7sus4",
            ),
            split=BenchmarkSplit.CALIBRATION,
        )
        calibration[1] = adapt_teacher_gold_reference_row(
            row(
                "TG-0002",
                notes="C3,E3,G3,A3",
                state="AMBIGUOUS",
                primary="",
                alternatives="C6 | Am7/C",
                inversion="",
            ),
            split=BenchmarkSplit.CALIBRATION,
        )
        holdout[0] = adapt_teacher_gold_reference_row(
            row(
                "TG-0101",
                notes="G3,A3,D4,F4",
                primary="G7sus2",
            ),
            split=BenchmarkSplit.HOLDOUT,
        )
        holdout[1] = adapt_teacher_gold_reference_row(
            row(
                "TG-0102",
                notes="D3,F3,A3,B3",
                state="AMBIGUOUS",
                primary="",
                alternatives="Dm6 | Bm7b5/D",
                inversion="",
            ),
            split=BenchmarkSplit.HOLDOUT,
        )

        legacy = assemble_frozen_teacher_gold_benchmark_v0_1(calibration, holdout)
        upgraded = assemble_frozen_teacher_gold_benchmark_v0_2(calibration, holdout)

        self.assertEqual(legacy.reference_case_count, 200)
        self.assertEqual(legacy.executable_case_count, 196)
        self.assertEqual(
            legacy.reference_only_case_ids,
            ("TG-0001", "TG-0002", "TG-0101", "TG-0102"),
        )

        self.assertEqual(upgraded.reference_case_count, 200)
        self.assertEqual(upgraded.executable_case_count, 198)
        self.assertEqual(
            upgraded.reference_only_case_ids,
            ("TG-0002", "TG-0102"),
        )
        self.assertTrue(upgraded.is_full_reference_partition_ready)
        self.assertFalse(upgraded.is_fully_engine_executable)

    def test_v0_2_assembly_preserves_frozen_partition_guards(self):
        calibration = build_partition(1, 100, BenchmarkSplit.CALIBRATION)
        holdout = build_partition(101, 200, BenchmarkSplit.HOLDOUT)

        with self.assertRaises(ValueError):
            assemble_frozen_teacher_gold_benchmark_v0_2(calibration[:-1], holdout)

        wrong_split = list(holdout)
        wrong_split[0] = adapt_teacher_gold_reference_row(
            row("TG-0101"),
            split=BenchmarkSplit.CALIBRATION,
        )
        with self.assertRaises(ValueError):
            assemble_frozen_teacher_gold_benchmark_v0_2(calibration, wrong_split)


if __name__ == "__main__":
    unittest.main()
