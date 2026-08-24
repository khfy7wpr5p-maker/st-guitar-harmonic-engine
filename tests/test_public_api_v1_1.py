import copy
import json
import unittest

from st_guitar_harmonic_engine.public_api import (
    PUBLIC_API_SCHEMA_NAME,
    PUBLIC_RESULT_SCHEMA_VERSION,
    PublicValidationError,
    validate_public_request,
)
from st_guitar_harmonic_engine.public_api_v1_1 import (
    PUBLIC_API_SCHEMA_VERSION_V1_1,
    execute_public_request_v1_1,
    validate_public_request_v1_1,
)
from st_guitar_harmonic_engine.public_runtime import resolve_validated_public_request
from st_guitar_harmonic_engine.abstention import FinalDecisionState
from st_guitar_harmonic_engine.resolver import ResolverStatus


def beat(numerator, denominator=1):
    return {"numerator": numerator, "denominator": denominator}


def written(step, alter=0, octave=3):
    return {"step": step, "alter": alter, "octave": octave}


def event(pitch, spelling, voice, onset=0, duration=1):
    return {
        "staff": 1,
        "voice": voice,
        "midi_pitch": pitch,
        "onset": beat(onset),
        "duration": beat(duration),
        "tie": "none",
        "written_pitch": spelling,
    }


def frame(events):
    return {
        "measure_number": 1,
        "start": beat(0),
        "end": beat(1),
        "events": events,
    }


def request(events):
    return {
        "schema_name": PUBLIC_API_SCHEMA_NAME,
        "schema_version": PUBLIC_API_SCHEMA_VERSION_V1_1,
        "mode": "batch",
        "frames": [frame(events)],
        "phrase_spans": None,
    }


class PublicApiV11Tests(unittest.TestCase):
    def test_written_spelling_is_preserved_on_canonical_core_events(self):
        payload = request(
            [
                event(58, written("A", 1, 3), 3),
                event(50, written("D", 0, 3), 1),
                event(54, written("F", 1, 3), 2),
            ]
        )
        validated = validate_public_request_v1_1(payload)
        self.assertEqual(
            tuple(item.written_pitch.name for item in validated.frames[0].events),
            ("D3", "F#3", "A#3"),
        )
        self.assertEqual(validated.frames[0].pitch_classes, (2, 6, 10))

    def test_spelling_aware_augmented_root_resolves_without_model_or_context(self):
        validated = validate_public_request_v1_1(
            request(
                [
                    event(50, written("D", 0, 3), 1),
                    event(54, written("F", 1, 3), 2),
                    event(58, written("A", 1, 3), 3),
                ]
            )
        )
        decisions = resolve_validated_public_request(validated)
        self.assertEqual(len(decisions), 1)
        self.assertIs(decisions[0].state, FinalDecisionState.RESOLVED)
        source = decisions[0].source_decision
        self.assertIs(source.status, ResolverStatus.RESOLVED)
        self.assertEqual(source.candidates[0].identity.root_pc, 2)
        self.assertEqual(source.candidates[0].identity.variant, "augmented")

    def test_null_spelling_is_explicit_and_preserves_existing_ambiguity(self):
        validated = validate_public_request_v1_1(
            request([event(50, None, 1), event(54, None, 2), event(58, None, 3)])
        )
        decisions = resolve_validated_public_request(validated)
        self.assertIs(decisions[0].state, FinalDecisionState.AMBIGUOUS)
        self.assertEqual(len(decisions[0].source_decision.candidates), 3)

    def test_pitch_class_inconsistent_spelling_is_accepted_as_source_data_but_fails_closed(self):
        validated = validate_public_request_v1_1(
            request(
                [
                    event(50, written("E", -1, 3), 1),  # sounding D, written Eb
                    event(54, written("F", 1, 3), 2),
                    event(58, written("A", 1, 3), 3),
                ]
            )
        )
        decisions = resolve_validated_public_request(validated)
        self.assertIs(decisions[0].state, FinalDecisionState.AMBIGUOUS)

    def test_invalid_written_pitch_shapes_fail_closed(self):
        base = request(
            [
                event(50, written("D", 0, 3), 1),
                event(54, written("F", 1, 3), 2),
                event(58, written("A", 1, 3), 3),
            ]
        )
        cases = []

        bad_step = copy.deepcopy(base)
        bad_step["frames"][0]["events"][0]["written_pitch"]["step"] = "H"
        cases.append(bad_step)

        bad_alter = copy.deepcopy(base)
        bad_alter["frames"][0]["events"][0]["written_pitch"]["alter"] = 3
        cases.append(bad_alter)

        bad_octave = copy.deepcopy(base)
        bad_octave["frames"][0]["events"][0]["written_pitch"]["octave"] = 10
        cases.append(bad_octave)

        bool_alter = copy.deepcopy(base)
        bool_alter["frames"][0]["events"][0]["written_pitch"]["alter"] = True
        cases.append(bool_alter)

        extra = copy.deepcopy(base)
        extra["frames"][0]["events"][0]["written_pitch"]["cents"] = 0
        cases.append(extra)

        missing_field = copy.deepcopy(base)
        del missing_field["frames"][0]["events"][0]["written_pitch"]["octave"]
        cases.append(missing_field)

        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(PublicValidationError):
                    validate_public_request_v1_1(payload)

    def test_v1_0_remains_strict_and_does_not_silently_accept_v1_1_event_shape(self):
        payload = request([event(60, written("C", 0, 4), 1), event(64, written("E", 0, 4), 2), event(67, written("G", 0, 4), 3)])
        payload["schema_version"] = "1.0"
        with self.assertRaises(PublicValidationError):
            validate_public_request(payload)

    def test_v1_1_wrong_schema_extra_event_fields_and_missing_written_field_fail_closed(self):
        base = request([event(60, written("C", 0, 4), 1), event(64, written("E", 0, 4), 2), event(67, written("G", 0, 4), 3)])

        wrong_version = copy.deepcopy(base)
        wrong_version["schema_version"] = "2.0"
        with self.assertRaises(PublicValidationError):
            validate_public_request_v1_1(wrong_version)

        extra_event = copy.deepcopy(base)
        extra_event["frames"][0]["events"][0]["velocity"] = 90
        with self.assertRaises(PublicValidationError):
            validate_public_request_v1_1(extra_event)

        missing_written = copy.deepcopy(base)
        del missing_written["frames"][0]["events"][0]["written_pitch"]
        with self.assertRaises(PublicValidationError):
            validate_public_request_v1_1(missing_written)

    def test_execution_reuses_frozen_result_v1_0_and_is_deterministic(self):
        payload = request(
            [
                event(50, written("D", 0, 3), 1),
                event(54, written("F", 1, 3), 2),
                event(58, written("A", 1, 3), 3),
            ]
        )
        first = execute_public_request_v1_1(payload)
        self.assertEqual(first["schema_version"], PUBLIC_RESULT_SCHEMA_VERSION)
        encoded = json.dumps(first, sort_keys=True, separators=(",", ":"))
        for _ in range(10):
            self.assertEqual(
                json.dumps(
                    execute_public_request_v1_1(copy.deepcopy(payload)),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                encoded,
            )

    def test_input_event_order_does_not_change_validated_request(self):
        events = [
            event(50, written("D", 0, 3), 3),
            event(54, written("F", 1, 3), 1),
            event(58, written("A", 1, 3), 2),
        ]
        left = validate_public_request_v1_1(request(events))
        right = validate_public_request_v1_1(request(list(reversed(events))))
        self.assertEqual(left, right)


if __name__ == "__main__":
    unittest.main()
