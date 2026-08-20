import copy
import json
import unittest

from st_guitar_harmonic_engine import (
    EXPLAINABILITY_SCHEMA_NAME,
    EXPLAINABILITY_SCHEMA_V1,
    EXPLAINABILITY_SCHEMA_VERSION,
    Measure,
    NoteEvent,
    RationalBeat,
    TimeSignature,
    TonalContext,
    TonalMode,
    analyze_measure_exact,
    analyze_measure_in_context,
    build_measure_explainability,
    is_explainability_payload_compatible,
    serialize_measure_explainability,
    validate_explainability_payload,
)


def event(pitch, onset, duration, *, voice):
    return NoteEvent(
        measure_number=1,
        staff=1,
        voice=voice,
        midi_pitch=pitch,
        onset=RationalBeat(onset),
        duration=RationalBeat(duration),
    )


def passing_measure():
    return Measure(
        1,
        TimeSignature(3, 4),
        (
            event(48, 0, 3, voice=2),
            event(52, 0, 3, voice=3),
            event(55, 0, 3, voice=4),
            event(60, 0, 1, voice=1),
            event(62, 1, 1, voice=1),
            event(64, 2, 1, voice=1),
        ),
    )


def omission_measure():
    return Measure(
        1,
        TimeSignature(4, 4),
        (
            event(48, 0, 4, voice=1),
            event(52, 0, 4, voice=2),
        ),
    )


class ExplainabilitySchemaContractTests(unittest.TestCase):
    def payload_for(self, measure):
        return serialize_measure_explainability(
            build_measure_explainability(measure)
        )

    def test_schema_identity_and_compatibility_policy_are_frozen(self):
        self.assertEqual(
            EXPLAINABILITY_SCHEMA_NAME,
            "st-guitar-harmonic-engine.explainability",
        )
        self.assertEqual(EXPLAINABILITY_SCHEMA_VERSION, "1.0")
        self.assertEqual(EXPLAINABILITY_SCHEMA_V1["compatible_versions"], "1.x")
        self.assertEqual(EXPLAINABILITY_SCHEMA_V1["unknown_fields"], "allowed")
        self.assertEqual(
            EXPLAINABILITY_SCHEMA_V1["breaking_changes"],
            "require a new major version",
        )

    def test_nct_payload_field_contract_is_stable(self):
        payload = self.payload_for(passing_measure())
        self.assertEqual(
            set(payload),
            {"schema_name", "schema_version", "measure_number", "frames"},
        )
        middle = payload["frames"][1]
        self.assertEqual(
            set(middle),
            {"measure_number", "frame_index", "start", "end", "ncts", "omissions"},
        )
        self.assertEqual(len(middle["ncts"]), 1)
        nct = middle["ncts"][0]
        self.assertEqual(
            set(nct),
            {
                "measure_number",
                "frame_index",
                "start",
                "end",
                "staff",
                "voice",
                "midi_pitch",
                "pitch_class",
                "kind",
                "anchor_root_pc",
                "anchor_quality",
            },
        )
        self.assertEqual(nct["kind"], "passing")
        self.assertEqual((nct["midi_pitch"], nct["pitch_class"]), (62, 2))
        self.assertEqual((nct["anchor_root_pc"], nct["anchor_quality"]), (0, "major"))

    def test_omission_payload_field_contract_is_stable(self):
        payload = self.payload_for(omission_measure())
        omission = payload["frames"][0]["omissions"][0]
        self.assertEqual(
            set(omission),
            {
                "root_pc",
                "quality",
                "observed_pitch_classes",
                "omitted_pc",
                "omission",
            },
        )
        self.assertEqual(
            omission,
            {
                "root_pc": 0,
                "quality": "major",
                "observed_pitch_classes": [0, 4],
                "omitted_pc": 7,
                "omission": "fifth",
            },
        )

    def test_rational_time_is_json_safe_and_never_float(self):
        payload = self.payload_for(passing_measure())
        start = payload["frames"][0]["start"]
        end = payload["frames"][0]["end"]
        self.assertEqual(start, {"numerator": 0, "denominator": 1})
        self.assertEqual(end, {"numerator": 1, "denominator": 1})
        self.assertFalse(any(isinstance(value, float) for value in (*start.values(), *end.values())))

    def test_json_round_trip_preserves_v1_payload(self):
        payload = self.payload_for(passing_measure())
        round_trip = json.loads(json.dumps(payload, sort_keys=True))
        self.assertEqual(round_trip, payload)
        validate_explainability_payload(round_trip)

    def test_additive_1x_fields_remain_backward_compatible(self):
        payload = self.payload_for(passing_measure())
        payload["schema_version"] = "1.7"
        payload["future_metadata"] = {"source": "future"}
        payload["frames"][1]["future_frame_field"] = True
        payload["frames"][1]["ncts"][0]["future_nct_field"] = "ignored"
        self.assertTrue(is_explainability_payload_compatible(payload))

    def test_breaking_major_version_is_rejected(self):
        payload = self.payload_for(passing_measure())
        payload["schema_version"] = "2.0"
        self.assertFalse(is_explainability_payload_compatible(payload))

    def test_removing_required_v1_field_is_rejected(self):
        payload = self.payload_for(omission_measure())
        del payload["frames"][0]["omissions"][0]["omitted_pc"]
        self.assertFalse(is_explainability_payload_compatible(payload))

    def test_decision_bearing_fields_are_forbidden_in_v1(self):
        payload = self.payload_for(passing_measure())
        for field in EXPLAINABILITY_SCHEMA_V1["forbidden_decision_fields"]:
            candidate = copy.deepcopy(payload)
            candidate[field] = "not-allowed"
            self.assertFalse(
                is_explainability_payload_compatible(candidate),
                msg=field,
            )

    def test_serialization_does_not_change_exact_or_context_decisions(self):
        measure = passing_measure()
        context = TonalContext(0, TonalMode.MAJOR)
        exact_before = analyze_measure_exact(measure)
        context_before = analyze_measure_in_context(measure, context)

        self.payload_for(measure)

        self.assertEqual(analyze_measure_exact(measure), exact_before)
        self.assertEqual(analyze_measure_in_context(measure, context), context_before)

    def test_serializer_rejects_non_report_input(self):
        with self.assertRaises(TypeError):
            serialize_measure_explainability(object())


if __name__ == "__main__":
    unittest.main()
