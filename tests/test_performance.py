import unittest

from st_guitar_harmonic_engine.performance import (
    MAX_PERFORMANCE_REPEATS,
    PERFORMANCE_AUTHORITY,
    PERFORMANCE_CONTRACT_VERSION,
    profile_public_request,
)
from st_guitar_harmonic_engine.public_api import (
    MAX_PUBLIC_FRAMES,
    PUBLIC_API_SCHEMA_NAME,
    PUBLIC_API_SCHEMA_VERSION,
    PublicRequestMode,
    PublicValidationError,
)
from st_guitar_harmonic_engine.public_runtime import execute_public_request


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


def request(frames, mode="batch", phrase_spans=None):
    return {
        "schema_name": PUBLIC_API_SCHEMA_NAME,
        "schema_version": PUBLIC_API_SCHEMA_VERSION,
        "mode": mode,
        "frames": frames,
        "phrase_spans": phrase_spans,
    }


class PerformanceSafetyTests(unittest.TestCase):
    def test_batch_latency_and_memory_are_measured_without_semantic_change(self):
        payload = request([frame(1, [60, 64, 67]), frame(2, [67, 71, 74])])
        expected = execute_public_request(payload)
        profile = profile_public_request(payload, repeats=3)
        self.assertEqual(execute_public_request(payload), expected)
        self.assertEqual(profile.contract_version, PERFORMANCE_CONTRACT_VERSION)
        self.assertEqual(profile.authority, PERFORMANCE_AUTHORITY)
        self.assertIs(profile.mode, PublicRequestMode.BATCH)
        self.assertGreaterEqual(profile.median_latency_seconds, 0.0)
        self.assertGreaterEqual(profile.max_latency_seconds, profile.median_latency_seconds)
        self.assertIsInstance(profile.retained_bytes_delta, int)
        self.assertGreaterEqual(profile.peak_traced_bytes, 0)
        self.assertTrue(profile.outputs_stable)

    def test_sequence_latency_and_memory_are_measured(self):
        payload = request(
            [frame(1, [60, 64, 67]), frame(2, [65, 69, 72]), frame(3, [67, 71, 74])],
            mode="sequence",
            phrase_spans=[{"start_index": 0, "end_index": 3}],
        )
        profile = profile_public_request(payload, repeats=3)
        self.assertIs(profile.mode, PublicRequestMode.SEQUENCE)
        self.assertTrue(profile.outputs_stable)
        self.assertGreaterEqual(profile.median_latency_seconds, 0.0)
        self.assertGreaterEqual(profile.peak_traced_bytes, 0)

    def test_performance_numbers_have_no_authoritative_threshold(self):
        payload = request([frame(1, [60, 64, 67])])
        profile = profile_public_request(payload, repeats=1)
        self.assertEqual(profile.authority, "diagnostic_only")
        self.assertFalse(hasattr(profile, "passes_gate"))
        self.assertFalse(hasattr(profile, "confidence"))
        self.assertFalse(hasattr(profile, "decision"))

    def test_pathological_oversized_input_fails_validation_before_profiling(self):
        oversized = request(
            [frame(index + 1, [60, 64, 67]) for index in range(MAX_PUBLIC_FRAMES + 1)]
        )
        with self.assertRaises(PublicValidationError):
            profile_public_request(oversized, repeats=1)

    def test_repeat_count_is_bounded(self):
        payload = request([frame(1, [60, 64, 67])])
        for bad in (0, MAX_PERFORMANCE_REPEATS + 1, True):
            with self.subTest(bad=bad):
                with self.assertRaises((TypeError, ValueError)):
                    profile_public_request(payload, repeats=bad)


if __name__ == "__main__":
    unittest.main()
