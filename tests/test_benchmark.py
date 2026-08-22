import json
import unittest

from st_guitar_harmonic_engine.benchmark import (
    BENCHMARK_ACCURACY_CLAIM,
    BENCHMARK_SCHEMA_NAME,
    BENCHMARK_SCHEMA_VERSION,
    BenchmarkCase,
    run_deterministic_benchmark,
    serialize_benchmark_report,
)
from st_guitar_harmonic_engine.public_api import PUBLIC_API_SCHEMA_NAME, PUBLIC_API_SCHEMA_VERSION


def beat(n):
    return {"numerator": n, "denominator": 1}


def frame(measure, pitches):
    return {
        "measure_number": measure,
        "start": beat(0),
        "end": beat(1),
        "events": [
            {
                "staff": 1,
                "voice": index + 1,
                "midi_pitch": pitch,
                "onset": beat(0),
                "duration": beat(1),
                "tie": "none",
            }
            for index, pitch in enumerate(pitches)
        ],
    }


def request(frames):
    return {
        "schema_name": PUBLIC_API_SCHEMA_NAME,
        "schema_version": PUBLIC_API_SCHEMA_VERSION,
        "mode": "batch",
        "frames": frames,
        "phrase_spans": None,
    }


class BenchmarkHarnessTests(unittest.TestCase):
    def test_counts_exact_ambiguity_and_no_forced_resolution(self):
        report = run_deterministic_benchmark(
            (
                BenchmarkCase("exact", request([frame(1, [60, 64, 67])])),
                BenchmarkCase("ambiguous", request([frame(2, [60, 63, 66, 69])])),
                BenchmarkCase("unknown", request([frame(3, [60, 61, 66])])),
            )
        )
        self.assertEqual(report.case_count, 3)
        self.assertEqual(report.frame_count, 3)
        self.assertEqual(report.exact_resolved_count, 1)
        self.assertGreaterEqual(report.ambiguous_count + report.abstain_count + report.no_match_count, 2)
        self.assertEqual(report.schema_valid_count, 3)
        self.assertEqual(report.validation_or_runtime_error_count, 0)
        self.assertTrue(report.deterministic_stable)

    def test_invalid_case_is_isolated_and_recorded(self):
        bad = request([frame(1, [60, 64, 67])])
        bad["schema_version"] = "99.0"
        report = run_deterministic_benchmark(
            (
                BenchmarkCase("good", request([frame(1, [60, 64, 67])])),
                BenchmarkCase("bad", bad),
            )
        )
        self.assertEqual(report.case_count, 2)
        self.assertEqual(report.validation_or_runtime_error_count, 1)
        self.assertFalse(report.deterministic_stable)
        failed = next(item for item in report.cases if item.case_id == "bad")
        self.assertIsNotNone(failed.error_type)
        self.assertIsNone(failed.output_sha256)

    def test_serialization_is_versioned_and_forbids_accuracy_claim(self):
        report = run_deterministic_benchmark(
            (BenchmarkCase("exact", request([frame(1, [60, 64, 67])])),)
        )
        payload = serialize_benchmark_report(report)
        self.assertEqual(payload["schema_name"], BENCHMARK_SCHEMA_NAME)
        self.assertEqual(payload["schema_version"], BENCHMARK_SCHEMA_VERSION)
        self.assertEqual(payload["musical_accuracy_claim"], BENCHMARK_ACCURACY_CLAIM)
        self.assertEqual(BENCHMARK_ACCURACY_CLAIM, "not_available_without_teacher_gold")
        self.assertNotIn("accuracy", {key for key in payload if key != "musical_accuracy_claim"})
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        for _ in range(10):
            current = serialize_benchmark_report(
                run_deterministic_benchmark(
                    (BenchmarkCase("exact", request([frame(1, [60, 64, 67])])),)
                )
            )
            self.assertEqual(json.dumps(current, sort_keys=True, separators=(",", ":")), encoded)

    def test_duplicate_case_ids_and_invalid_container_fail_closed(self):
        case = BenchmarkCase("same", request([frame(1, [60, 64, 67])]))
        with self.assertRaises(ValueError):
            run_deterministic_benchmark((case, case))
        with self.assertRaises(TypeError):
            run_deterministic_benchmark([case])


if __name__ == "__main__":
    unittest.main()
