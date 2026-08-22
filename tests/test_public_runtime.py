import copy
import json
import unittest

from st_guitar_harmonic_engine.public_api import (
    PUBLIC_API_SCHEMA_NAME,
    PUBLIC_API_SCHEMA_VERSION,
    validate_public_request,
)
from st_guitar_harmonic_engine.public_runtime import (
    execute_public_request,
    resolve_validated_public_request,
)


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


class PublicRuntimeTests(unittest.TestCase):
    def test_batch_resolves_exact_frames_independently(self):
        payload = request([
            frame(2, [62, 66, 69]),  # D major
            frame(1, [60, 64, 67]),  # C major
        ])
        result = execute_public_request(payload)
        self.assertEqual([item["measure_number"] for item in result["results"]], [1, 2])
        first = result["results"][0]["decision"]
        second = result["results"][1]["decision"]
        self.assertEqual(first["state"], "resolved")
        self.assertEqual(first["candidates"][0]["identity"]["root_pc"], 0)
        self.assertEqual(second["state"], "resolved")
        self.assertEqual(second["candidates"][0]["identity"]["root_pc"], 2)

    def test_sequence_supports_multi_measure_phrase_scope_without_new_authority(self):
        payload = request(
            [frame(3, [67, 71, 74]), frame(1, [60, 64, 67]), frame(2, [65, 69, 72])],
            mode="sequence",
            phrase_spans=[{"start_index": 0, "end_index": 3}],
        )
        result = execute_public_request(payload)
        self.assertEqual([item["measure_number"] for item in result["results"]], [1, 2, 3])
        self.assertEqual([item["decision"]["state"] for item in result["results"]], ["resolved"] * 3)
        self.assertEqual(
            [item["decision"]["candidates"][0]["identity"]["root_pc"] for item in result["results"]],
            [0, 5, 7],
        )

    def test_sequence_without_phrase_plan_remains_isolated(self):
        payload = request(
            [frame(1, [60, 64, 67]), frame(2, [67, 71, 74])],
            mode="sequence",
            phrase_spans=None,
        )
        result = execute_public_request(payload)
        evidence = [
            item["decision"]["candidates"][0]["evidence"]
            for item in result["results"]
        ]
        self.assertEqual(evidence, [["exact", "bass_inversion"], ["exact", "bass_inversion"]])

    def test_exact_ambiguity_is_preserved_through_public_runtime(self):
        payload = request([frame(1, [60, 63, 66, 69])])
        decision = execute_public_request(payload)["results"][0]["decision"]
        self.assertEqual(decision["state"], "ambiguous")
        self.assertGreater(len(decision["candidates"]), 1)

    def test_unknown_sonority_does_not_get_forced_resolved(self):
        payload = request([frame(1, [60, 61, 66])])
        state = execute_public_request(payload)["results"][0]["decision"]["state"]
        self.assertIn(state, {"ambiguous", "abstain", "no_match"})
        self.assertNotEqual(state, "resolved")

    def test_resolve_validated_request_rejects_unvalidated_shapes(self):
        with self.assertRaises(TypeError):
            resolve_validated_public_request(object())

    def test_repeated_run_and_input_order_are_stable(self):
        values = [frame(2, [67, 71, 74]), frame(1, [60, 64, 67])]
        expected = execute_public_request(request(values))
        reversed_result = execute_public_request(request(list(reversed(values))))
        self.assertEqual(reversed_result, expected)
        encoded = json.dumps(expected, sort_keys=True, separators=(",", ":"))
        for _ in range(10):
            current = execute_public_request(request(copy.deepcopy(values)))
            self.assertEqual(json.dumps(current, sort_keys=True, separators=(",", ":")), encoded)

    def test_validated_and_direct_execution_match(self):
        payload = request([frame(1, [60, 64, 67])])
        validated = validate_public_request(payload)
        decisions = resolve_validated_public_request(validated)
        direct = execute_public_request(payload)
        self.assertEqual(direct["results"][0]["decision"]["state"], decisions[0].state.value)


if __name__ == "__main__":
    unittest.main()
