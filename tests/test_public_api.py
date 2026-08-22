import copy
import json
import unittest

from st_guitar_harmonic_engine.abstention import apply_abstention_policy
from st_guitar_harmonic_engine.public_api import (
    MAX_EVENTS_PER_FRAME,
    MAX_PUBLIC_FRAMES,
    PUBLIC_API_SCHEMA_NAME,
    PUBLIC_API_SCHEMA_VERSION,
    PUBLIC_RESULT_SCHEMA_NAME,
    PUBLIC_RESULT_SCHEMA_VERSION,
    PublicRequestMode,
    PublicValidationError,
    is_public_result_payload_compatible,
    serialize_public_result,
    validate_public_request,
)
from st_guitar_harmonic_engine.resolver import (
    CandidateFamily,
    EvidenceSource,
    HarmonicIdentity,
    ResolverCandidate,
    ResolverDecision,
    ResolverStatus,
)


def beat(numerator, denominator=1):
    return {"numerator": numerator, "denominator": denominator}


def event(pitch, onset=0, duration=1, staff=1, voice=1, tie="none"):
    return {
        "staff": staff,
        "voice": voice,
        "midi_pitch": pitch,
        "onset": beat(onset),
        "duration": beat(duration),
        "tie": tie,
    }


def frame(measure, start, end, pitches):
    return {
        "measure_number": measure,
        "start": beat(start),
        "end": beat(end),
        "events": [event(pitch, onset=start, duration=end - start) for pitch in pitches],
    }


def request(frames, mode="batch", phrase_spans=None):
    return {
        "schema_name": PUBLIC_API_SCHEMA_NAME,
        "schema_version": PUBLIC_API_SCHEMA_VERSION,
        "mode": mode,
        "frames": frames,
        "phrase_spans": phrase_spans,
    }


class PublicApiValidationTests(unittest.TestCase):
    def test_valid_batch_is_canonical_and_repeatable(self):
        payload = request([
            frame(2, 0, 1, [67, 64, 60]),
            frame(1, 0, 1, [67, 60, 64]),
        ])
        first = validate_public_request(payload)
        second = validate_public_request(copy.deepcopy(payload))
        self.assertEqual(first, second)
        self.assertIs(first.mode, PublicRequestMode.BATCH)
        self.assertEqual(tuple(item.measure_number for item in first.frames), (1, 2))
        self.assertEqual(first.frames[0].pitch_classes, (0, 4, 7))

    def test_sequence_phrase_plan_is_validated_against_canonical_frames(self):
        payload = request(
            [frame(2, 0, 1, [62, 65, 69]), frame(1, 0, 1, [60, 64, 67])],
            mode="sequence",
            phrase_spans=[{"start_index": 0, "end_index": 2}],
        )
        validated = validate_public_request(payload)
        self.assertIs(validated.mode, PublicRequestMode.SEQUENCE)
        self.assertEqual(tuple(item.measure_number for item in validated.frames), (1, 2))
        self.assertEqual(validated.phrase_plan.spans[0].start_index, 0)
        self.assertEqual(validated.phrase_plan.spans[0].end_index, 2)

    def test_wrong_schema_unknown_mode_and_extra_fields_fail_closed(self):
        base = request([frame(1, 0, 1, [60, 64, 67])])
        cases = []
        wrong_name = copy.deepcopy(base)
        wrong_name["schema_name"] = "unknown"
        cases.append(wrong_name)
        wrong_version = copy.deepcopy(base)
        wrong_version["schema_version"] = "2.0"
        cases.append(wrong_version)
        wrong_mode = copy.deepcopy(base)
        wrong_mode["mode"] = "stream"
        cases.append(wrong_mode)
        extra = copy.deepcopy(base)
        extra["unexpected"] = True
        cases.append(extra)
        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(PublicValidationError):
                    validate_public_request(payload)

    def test_invalid_pitch_duration_boundary_and_enum_fail_closed(self):
        base = request([frame(1, 0, 1, [60, 64, 67])])
        invalid_pitch = copy.deepcopy(base)
        invalid_pitch["frames"][0]["events"][0]["midi_pitch"] = 128
        invalid_duration = copy.deepcopy(base)
        invalid_duration["frames"][0]["events"][0]["duration"] = beat(0)
        invalid_boundary = copy.deepcopy(base)
        invalid_boundary["frames"][0]["end"] = beat(0)
        invalid_tie = copy.deepcopy(base)
        invalid_tie["frames"][0]["events"][0]["tie"] = "maybe"
        for payload in (invalid_pitch, invalid_duration, invalid_boundary, invalid_tie):
            with self.assertRaises(PublicValidationError):
                validate_public_request(payload)

    def test_duplicate_events_and_frames_fail_closed(self):
        duplicate_event_frame = frame(1, 0, 1, [60, 64, 67])
        duplicate_event_frame["events"].append(copy.deepcopy(duplicate_event_frame["events"][0]))
        with self.assertRaises(PublicValidationError):
            validate_public_request(request([duplicate_event_frame]))

        duplicate_frame = frame(1, 0, 1, [60, 64, 67])
        with self.assertRaises(PublicValidationError):
            validate_public_request(request([duplicate_frame, copy.deepcopy(duplicate_frame)]))

    def test_batch_rejects_phrase_spans_and_sequence_rejects_bad_spans(self):
        one = frame(1, 0, 1, [60, 64, 67])
        with self.assertRaises(PublicValidationError):
            validate_public_request(request([one], phrase_spans=[{"start_index": 0, "end_index": 1}]))
        with self.assertRaises(PublicValidationError):
            validate_public_request(
                request([one], mode="sequence", phrase_spans=[{"start_index": 0, "end_index": 2}])
            )

    def test_oversized_frame_and_request_are_rejected_before_core_policy(self):
        oversized_events = [event(60 + (index % 12), voice=index + 1) for index in range(MAX_EVENTS_PER_FRAME + 1)]
        oversized_frame = {
            "measure_number": 1,
            "start": beat(0),
            "end": beat(1),
            "events": oversized_events,
        }
        with self.assertRaises(PublicValidationError):
            validate_public_request(request([oversized_frame]))

        frames = [frame(index + 1, 0, 1, [60, 64, 67]) for index in range(MAX_PUBLIC_FRAMES + 1)]
        with self.assertRaises(PublicValidationError):
            validate_public_request(request(frames))

    def test_non_json_shapes_and_boolean_integers_fail_closed(self):
        with self.assertRaises(PublicValidationError):
            validate_public_request([])
        payload = request([frame(1, 0, 1, [60, 64, 67])])
        payload["frames"][0]["measure_number"] = True
        with self.assertRaises(PublicValidationError):
            validate_public_request(payload)


class PublicApiSerializationTests(unittest.TestCase):
    def test_result_serialization_is_versioned_stable_and_categorical(self):
        validated = validate_public_request(request([frame(1, 0, 1, [60, 64, 67])]))
        candidate = ResolverCandidate(
            HarmonicIdentity(0, CandidateFamily.BASIC, "major"),
            (EvidenceSource.EXACT,),
        )
        decision = apply_abstention_policy(
            ResolverDecision(ResolverStatus.RESOLVED, (candidate,))
        )
        payload = serialize_public_result(validated.frames, (decision,))
        self.assertEqual(payload["schema_name"], PUBLIC_RESULT_SCHEMA_NAME)
        self.assertEqual(payload["schema_version"], PUBLIC_RESULT_SCHEMA_VERSION)
        self.assertTrue(is_public_result_payload_compatible(payload))
        self.assertEqual(payload["results"][0]["decision"]["confidence"]["state"], "strong")
        self.assertNotIn("probability", json.dumps(payload))
        self.assertNotIn("score", json.dumps(payload))
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        for _ in range(10):
            self.assertEqual(
                json.dumps(
                    serialize_public_result(validated.frames, (decision,)),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                encoded,
            )

    def test_serialization_rejects_mismatched_counts_and_wrong_types(self):
        validated = validate_public_request(request([frame(1, 0, 1, [60, 64, 67])]))
        with self.assertRaises(ValueError):
            serialize_public_result(validated.frames, ())
        with self.assertRaises(TypeError):
            serialize_public_result(validated.frames, (object(),))


if __name__ == "__main__":
    unittest.main()
