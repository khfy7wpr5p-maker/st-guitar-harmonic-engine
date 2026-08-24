import copy
import json
import unittest

from st_guitar_harmonic_engine.public_api import (
    PUBLIC_API_SCHEMA_NAME,
    PUBLIC_RESULT_SCHEMA_VERSION,
    PublicValidationError,
)
from st_guitar_harmonic_engine.public_api_v1_1 import validate_public_request_v1_1
from st_guitar_harmonic_engine.public_api_v1_2 import (
    PUBLIC_API_SCHEMA_VERSION_V1_2,
    execute_public_request_v1_2,
    validate_public_request_v1_2,
)


def beat(numerator, denominator=1):
    return {"numerator": numerator, "denominator": denominator}


def written(step, alter=0, octave=3):
    return {"step": step, "alter": alter, "octave": octave}


def event(pitch, voice, spelling=None):
    return {
        "staff": 1,
        "voice": voice,
        "midi_pitch": pitch,
        "onset": beat(0),
        "duration": beat(1),
        "tie": "none",
        "written_pitch": spelling,
    }


def frame(measure_number, events):
    return {
        "measure_number": measure_number,
        "start": beat(0),
        "end": beat(1),
        "events": events,
    }


def c6_frame(measure_number=1):
    return frame(
        measure_number,
        [event(48, 1), event(52, 2), event(55, 3), event(57, 4)],
    )


def c_major_frame(measure_number=2):
    return frame(measure_number, [event(48, 1), event(52, 2), event(55, 3)])


def request(frames=None, contexts=None, mode="batch", phrase_spans=None):
    return {
        "schema_name": PUBLIC_API_SCHEMA_NAME,
        "schema_version": PUBLIC_API_SCHEMA_VERSION_V1_2,
        "mode": mode,
        "frames": frames or [c6_frame()],
        "phrase_spans": phrase_spans,
        "tonal_context_spans": contexts,
    }


def context(start, end, tonic, mode):
    return {
        "start_index": start,
        "end_index": end,
        "tonic_pc": tonic,
        "mode": mode,
    }


class PublicApiV12Tests(unittest.TestCase):
    def test_no_context_preserves_collision_ambiguity(self):
        result = execute_public_request_v1_2(request(contexts=None))
        decision = result["results"][0]["decision"]
        self.assertEqual(decision["state"], "ambiguous")
        self.assertEqual(
            {(item["identity"]["root_pc"], item["identity"]["variant"]) for item in decision["candidates"]},
            {(0, "major_sixth"), (9, "minor_seventh")},
        )

    def test_explicit_c_major_context_resolves_c6(self):
        result = execute_public_request_v1_2(
            request(contexts=[context(0, 1, 0, "major")])
        )
        decision = result["results"][0]["decision"]
        self.assertEqual(decision["state"], "resolved")
        self.assertEqual(decision["candidates"][0]["identity"]["root_pc"], 0)
        self.assertEqual(decision["candidates"][0]["identity"]["variant"], "major_sixth")
        self.assertIn("tonal_context", decision["candidates"][0]["evidence"])
        self.assertEqual(result["schema_version"], PUBLIC_RESULT_SCHEMA_VERSION)

    def test_explicit_a_minor_context_resolves_competing_am7(self):
        result = execute_public_request_v1_2(
            request(contexts=[context(0, 1, 9, "minor")])
        )
        decision = result["results"][0]["decision"]
        self.assertEqual(decision["state"], "resolved")
        self.assertEqual(decision["candidates"][0]["identity"]["root_pc"], 9)
        self.assertEqual(decision["candidates"][0]["identity"]["variant"], "minor_seventh")

    def test_spelling_from_v1_1_is_preserved(self):
        payload = request(
            frames=[
                frame(
                    1,
                    [
                        event(50, 1, written("D", 0, 3)),
                        event(54, 2, written("F", 1, 3)),
                        event(58, 3, written("A", 1, 3)),
                    ],
                )
            ],
            contexts=None,
        )
        validated = validate_public_request_v1_2(payload)
        self.assertEqual(
            tuple(item.written_pitch.name for item in validated.request.frames[0].events),
            ("D3", "F#3", "A#3"),
        )

    def test_v1_1_remains_strict_and_rejects_v1_2_outer_shape(self):
        payload = request(contexts=None)
        payload["schema_version"] = "1.1"
        with self.assertRaises(PublicValidationError):
            validate_public_request_v1_1(payload)

    def test_invalid_context_shapes_fail_closed(self):
        base = request(contexts=[context(0, 1, 0, "major")])
        cases = []

        wrong_version = copy.deepcopy(base)
        wrong_version["schema_version"] = "2.0"
        cases.append(wrong_version)

        bad_tonic = copy.deepcopy(base)
        bad_tonic["tonal_context_spans"][0]["tonic_pc"] = 12
        cases.append(bad_tonic)

        bad_mode = copy.deepcopy(base)
        bad_mode["tonal_context_spans"][0]["mode"] = "dorian"
        cases.append(bad_mode)

        bool_index = copy.deepcopy(base)
        bool_index["tonal_context_spans"][0]["start_index"] = True
        cases.append(bool_index)

        empty_span = copy.deepcopy(base)
        empty_span["tonal_context_spans"][0]["end_index"] = 0
        cases.append(empty_span)

        extra = copy.deepcopy(base)
        extra["tonal_context_spans"][0]["confidence"] = 1
        cases.append(extra)

        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(PublicValidationError):
                    validate_public_request_v1_2(payload)

    def test_overlapping_or_out_of_bounds_context_spans_fail_closed(self):
        two_frames = [c6_frame(1), c_major_frame(2)]
        with self.assertRaises(PublicValidationError):
            validate_public_request_v1_2(
                request(
                    frames=two_frames,
                    contexts=[context(0, 2, 0, "major"), context(1, 2, 9, "minor")],
                )
            )
        with self.assertRaises(PublicValidationError):
            validate_public_request_v1_2(
                request(frames=two_frames, contexts=[context(0, 3, 0, "major")])
            )

    def test_context_indexes_apply_to_canonical_frame_order(self):
        validated = validate_public_request_v1_2(
            request(
                frames=[c_major_frame(2), c6_frame(1)],
                contexts=[context(0, 1, 0, "major")],
            )
        )
        self.assertEqual(
            tuple(item.measure_number for item in validated.request.frames),
            (1, 2),
        )
        contexts = validated.local_context.contexts_for(2)
        self.assertEqual(contexts[0].tonic_pc, 0)
        self.assertIsNone(contexts[1])

    def test_sequence_mode_uses_explicit_local_context(self):
        result = execute_public_request_v1_2(
            request(
                frames=[c6_frame(1), c_major_frame(2)],
                contexts=[context(0, 1, 0, "major")],
                mode="sequence",
                phrase_spans=None,
            )
        )
        self.assertEqual(result["results"][0]["decision"]["state"], "resolved")
        self.assertEqual(
            result["results"][0]["decision"]["candidates"][0]["identity"]["variant"],
            "major_sixth",
        )
        self.assertEqual(result["results"][1]["decision"]["state"], "resolved")

    def test_execution_is_deterministic(self):
        payload = request(contexts=[context(0, 1, 0, "major")])
        expected = json.dumps(
            execute_public_request_v1_2(payload),
            sort_keys=True,
            separators=(",", ":"),
        )
        for _ in range(10):
            self.assertEqual(
                json.dumps(
                    execute_public_request_v1_2(copy.deepcopy(payload)),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                expected,
            )


if __name__ == "__main__":
    unittest.main()
