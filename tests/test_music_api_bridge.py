import copy
import json
import unittest

from st_guitar_harmonic_engine.music_api_bridge import (
    MUSIC_API_BRIDGE_SCHEMA_NAME,
    MUSIC_API_BRIDGE_SCHEMA_VERSION,
    MUSIC_API_RESULT_SCHEMA_NAME,
    MUSIC_API_RESULT_SCHEMA_VERSION,
    MusicApiBridgeValidationError,
    execute_music_api_bridge_request,
    validate_music_api_bridge_request,
)
from st_guitar_harmonic_engine.public_api import (
    PUBLIC_API_SCHEMA_NAME,
    PublicValidationError,
)


def beat(numerator, denominator=1):
    return {"numerator": numerator, "denominator": denominator}


def event(pitch, voice, *, written_pitch=None):
    return {
        "staff": 1,
        "voice": voice,
        "midi_pitch": pitch,
        "onset": beat(0),
        "duration": beat(1),
        "tie": "none",
        "written_pitch": written_pitch,
    }


def frame(events):
    return {
        "measure_number": 1,
        "start": beat(0),
        "end": beat(1),
        "events": events,
    }


def harmonic_v1_2(*, contexts=None):
    return {
        "schema_name": PUBLIC_API_SCHEMA_NAME,
        "schema_version": "1.2",
        "mode": "batch",
        "frames": [
            frame(
                [
                    event(48, 1),
                    event(52, 2),
                    event(55, 3),
                    event(57, 4),
                ]
            )
        ],
        "phrase_spans": None,
        "tonal_context_spans": contexts,
    }


def bridge(harmonic_request=None, request_id="req-001"):
    return {
        "schema_name": MUSIC_API_BRIDGE_SCHEMA_NAME,
        "schema_version": MUSIC_API_BRIDGE_SCHEMA_VERSION,
        "request_id": request_id,
        "harmonic_request": harmonic_request or harmonic_v1_2(),
    }


class MusicApiBridgeTests(unittest.TestCase):
    def test_v1_2_request_runs_through_existing_deterministic_runtime(self):
        result = execute_music_api_bridge_request(bridge())
        self.assertEqual(result["schema_name"], MUSIC_API_RESULT_SCHEMA_NAME)
        self.assertEqual(result["schema_version"], MUSIC_API_RESULT_SCHEMA_VERSION)
        self.assertEqual(result["request_id"], "req-001")
        decision = result["harmonic_result"]["results"][0]["decision"]
        self.assertEqual(decision["state"], "ambiguous")
        self.assertEqual(
            {
                (item["identity"]["root_pc"], item["identity"]["variant"])
                for item in decision["candidates"]
            },
            {(0, "major_sixth"), (9, "minor_seventh")},
        )

    def test_explicit_v1_2_tonal_context_remains_bounded_st_evidence(self):
        payload = bridge(
            harmonic_v1_2(
                contexts=[
                    {
                        "start_index": 0,
                        "end_index": 1,
                        "tonic_pc": 0,
                        "mode": "major",
                    }
                ]
            )
        )
        result = execute_music_api_bridge_request(payload)
        decision = result["harmonic_result"]["results"][0]["decision"]
        self.assertEqual(decision["state"], "resolved")
        self.assertEqual(decision["candidates"][0]["identity"]["root_pc"], 0)
        self.assertEqual(decision["candidates"][0]["identity"]["variant"], "major_sixth")
        self.assertIn("tonal_context", decision["candidates"][0]["evidence"])

    def test_bridge_rejects_unknown_outer_fields_fail_closed(self):
        payload = bridge()
        payload["provider_confidence"] = 0.99
        with self.assertRaises(MusicApiBridgeValidationError):
            validate_music_api_bridge_request(payload)

    def test_nested_provider_authority_fields_are_rejected_by_st_contract(self):
        payload = bridge()
        payload["harmonic_request"]["provider_chord"] = "C6"
        with self.assertRaises(PublicValidationError):
            execute_music_api_bridge_request(payload)

    def test_unsupported_nested_version_fails_before_execution(self):
        payload = bridge()
        payload["harmonic_request"]["schema_version"] = "9.9"
        with self.assertRaises(MusicApiBridgeValidationError):
            validate_music_api_bridge_request(payload)

    def test_request_id_is_bounded_and_control_characters_are_rejected(self):
        for request_id in ("", "x" * 129, "bad\nrequest"):
            with self.subTest(request_id=request_id):
                with self.assertRaises(MusicApiBridgeValidationError):
                    validate_music_api_bridge_request(bridge(request_id=request_id))

    def test_execution_is_deterministic_and_does_not_mutate_input(self):
        payload = bridge()
        original = copy.deepcopy(payload)
        expected = json.dumps(
            execute_music_api_bridge_request(payload),
            sort_keys=True,
            separators=(",", ":"),
        )
        for _ in range(10):
            self.assertEqual(
                json.dumps(
                    execute_music_api_bridge_request(copy.deepcopy(payload)),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                expected,
            )
        self.assertEqual(payload, original)

    def test_result_does_not_add_probability_or_provider_score(self):
        serialized = json.dumps(execute_music_api_bridge_request(bridge()), sort_keys=True)
        self.assertNotIn("probability", serialized)
        self.assertNotIn("provider_score", serialized)


if __name__ == "__main__":
    unittest.main()
