import copy
import json
import unittest

from st_guitar_harmonic_engine import (
    BoundaryDisposition,
    BoundaryReason,
    Measure,
    NoteEvent,
    RationalBeat,
    STRUCTURAL_EXPLAINABILITY_SCHEMA_VERSION,
    TimeSignature,
    TonalContext,
    TonalMode,
    analyze_measure_exact,
    analyze_measure_in_context,
    build_measure_explainability,
    is_explainability_payload_compatible,
    is_structural_explainability_payload_compatible,
    segment_measure_structurally,
    serialize_measure_explainability,
    serialize_structural_explainability,
    validate_structural_explainability_payload,
)


def event(pitch, onset, duration, *, voice, staff=1):
    return NoteEvent(
        measure_number=1,
        staff=staff,
        voice=voice,
        midi_pitch=pitch,
        onset=RationalBeat(onset),
        duration=RationalBeat(duration),
    )


def two_frame_measure(left, right):
    events = []
    for index, pitch in enumerate(left):
        events.append(event(pitch, 0, 1, voice=index + 1))
    for index, pitch in enumerate(right):
        events.append(event(pitch, 1, 1, voice=index + 10))
    return Measure(1, TimeSignature(2, 4), tuple(events))


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


def silence_measure():
    return Measure(
        1,
        TimeSignature(4, 4),
        (
            event(48, 0, 1, voice=1),
            event(52, 0, 1, voice=2),
            event(55, 0, 1, voice=3),
            event(48, 2, 1, voice=10),
            event(52, 2, 1, voice=11),
            event(55, 2, 1, voice=12),
        ),
    )


class StructuralSegmentationTests(unittest.TestCase):
    def test_same_exact_harmony_continues_across_inversion_change(self):
        measure = two_frame_measure((48, 52, 55), (52, 55, 60))
        result = segment_measure_structurally(measure)
        self.assertEqual(len(result.transitions), 1)
        transition = result.transitions[0]
        self.assertEqual(transition.disposition, BoundaryDisposition.CONTINUATION)
        self.assertEqual(transition.reason, BoundaryReason.SAME_EXACT_HARMONY)
        self.assertEqual(len(result.segments), 1)
        self.assertEqual(
            (result.segments[0].first_frame_index, result.segments[0].last_frame_index),
            (0, 1),
        )

    def test_different_unique_exact_harmony_is_boundary(self):
        measure = two_frame_measure((48, 52, 55), (55, 59, 62))
        result = segment_measure_structurally(measure)
        transition = result.transitions[0]
        self.assertEqual(transition.disposition, BoundaryDisposition.BOUNDARY)
        self.assertEqual(transition.reason, BoundaryReason.EXACT_HARMONY_CHANGE)
        self.assertEqual(len(result.segments), 2)

    def test_silence_has_priority_over_same_harmony(self):
        result = segment_measure_structurally(silence_measure())
        transition = result.transitions[0]
        self.assertEqual(transition.disposition, BoundaryDisposition.BOUNDARY)
        self.assertEqual(transition.reason, BoundaryReason.SILENCE_GAP)
        self.assertEqual(transition.position, RationalBeat(2))
        self.assertEqual(len(result.segments), 2)

    def test_verified_passing_tone_bridges_both_transitions(self):
        result = segment_measure_structurally(passing_measure())
        self.assertEqual(len(result.transitions), 2)
        self.assertEqual(
            tuple(item.disposition for item in result.transitions),
            (BoundaryDisposition.CONTINUATION, BoundaryDisposition.CONTINUATION),
        )
        self.assertEqual(
            tuple(item.reason for item in result.transitions),
            (BoundaryReason.NCT_BRIDGE, BoundaryReason.NCT_BRIDGE),
        )
        self.assertEqual(len(result.segments), 1)

    def test_exact_anchor_bridges_unique_missing_fifth(self):
        measure = two_frame_measure((48, 52, 55), (48, 52))
        result = segment_measure_structurally(measure)
        transition = result.transitions[0]
        self.assertEqual(transition.disposition, BoundaryDisposition.CONTINUATION)
        self.assertEqual(transition.reason, BoundaryReason.MATCHING_FIFTH_OMISSION)
        self.assertEqual(len(result.segments), 1)

    def test_two_omission_only_frames_remain_unresolved(self):
        measure = two_frame_measure((48, 52), (48, 52))
        result = segment_measure_structurally(measure)
        transition = result.transitions[0]
        self.assertEqual(transition.disposition, BoundaryDisposition.UNRESOLVED)
        self.assertEqual(transition.reason, BoundaryReason.INSUFFICIENT_EVIDENCE)
        self.assertEqual(len(result.segments), 2)

    def test_ambiguous_diminished_seventh_remains_unresolved(self):
        measure = two_frame_measure((48, 51, 54, 57), (48, 51, 54, 57))
        result = segment_measure_structurally(measure)
        transition = result.transitions[0]
        self.assertEqual(transition.disposition, BoundaryDisposition.UNRESOLVED)
        self.assertEqual(transition.reason, BoundaryReason.INSUFFICIENT_EVIDENCE)
        self.assertEqual(len(result.segments), 2)

    def test_empty_measure_has_no_fabricated_segments(self):
        result = segment_measure_structurally(Measure(1, TimeSignature(4, 4), ()))
        self.assertEqual(result.transitions, ())
        self.assertEqual(result.segments, ())

    def test_every_frame_is_covered_once_and_unresolved_cuts(self):
        measure = two_frame_measure((48, 52), (48, 52))
        result = segment_measure_structurally(measure)
        covered = []
        for segment in result.segments:
            covered.extend(range(segment.first_frame_index, segment.last_frame_index + 1))
        self.assertEqual(covered, [0, 1])
        self.assertEqual(len(covered), len(set(covered)))

    def test_segmentation_is_deterministic_across_repeated_runs(self):
        measure = passing_measure()
        expected = segment_measure_structurally(measure)
        for _ in range(10):
            self.assertEqual(segment_measure_structurally(measure), expected)

    def test_segmentation_does_not_change_exact_or_context_decisions(self):
        measure = two_frame_measure((48, 52, 55), (55, 59, 62))
        context = TonalContext(0, TonalMode.MAJOR)
        exact_before = analyze_measure_exact(measure)
        context_before = analyze_measure_in_context(measure, context)
        segment_measure_structurally(measure)
        self.assertEqual(analyze_measure_exact(measure), exact_before)
        self.assertEqual(analyze_measure_in_context(measure, context), context_before)

    def test_rejects_non_measure_input(self):
        with self.assertRaises(TypeError):
            segment_measure_structurally(object())


class StructuralExplainabilityTests(unittest.TestCase):
    def test_default_schema_1_0_output_is_unchanged(self):
        report = build_measure_explainability(passing_measure())
        payload = serialize_measure_explainability(report)
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertNotIn("structural_boundary_evidence", payload)

    def test_structural_extension_is_additive_schema_1_1(self):
        measure = passing_measure()
        report = build_measure_explainability(measure)
        base = serialize_measure_explainability(report)
        segmentation = segment_measure_structurally(measure)
        payload = serialize_structural_explainability(report, segmentation)

        self.assertEqual(STRUCTURAL_EXPLAINABILITY_SCHEMA_VERSION, "1.1")
        self.assertEqual(payload["schema_version"], "1.1")
        self.assertEqual(payload["frames"], base["frames"])
        self.assertEqual(len(payload["structural_boundary_evidence"]), 2)
        self.assertTrue(is_explainability_payload_compatible(payload))
        self.assertTrue(is_structural_explainability_payload_compatible(payload))

    def test_structural_evidence_contains_no_authoritative_decision_fields(self):
        measure = two_frame_measure((48, 52, 55), (55, 59, 62))
        payload = serialize_structural_explainability(
            build_measure_explainability(measure),
            segment_measure_structurally(measure),
        )
        item = payload["structural_boundary_evidence"][0]
        for forbidden in (
            "status",
            "selected",
            "decision",
            "resolution",
            "authoritative",
            "disposition",
        ):
            self.assertNotIn(forbidden, item)
        self.assertEqual(item["signals"], ["exact_harmony_change"])

    def test_structural_position_remains_exact_rational_json(self):
        measure = two_frame_measure((48, 52, 55), (55, 59, 62))
        payload = serialize_structural_explainability(
            build_measure_explainability(measure),
            segment_measure_structurally(measure),
        )
        position = payload["structural_boundary_evidence"][0]["position"]
        self.assertEqual(position, {"numerator": 1, "denominator": 1})
        self.assertFalse(any(isinstance(value, float) for value in position.values()))

    def test_json_round_trip_preserves_structural_payload(self):
        measure = passing_measure()
        payload = serialize_structural_explainability(
            build_measure_explainability(measure),
            segment_measure_structurally(measure),
        )
        decoded = json.loads(json.dumps(payload, sort_keys=True))
        self.assertEqual(decoded, payload)
        validate_structural_explainability_payload(decoded)

    def test_structural_validator_rejects_decision_field(self):
        measure = two_frame_measure((48, 52, 55), (55, 59, 62))
        payload = serialize_structural_explainability(
            build_measure_explainability(measure),
            segment_measure_structurally(measure),
        )
        invalid = copy.deepcopy(payload)
        invalid["structural_boundary_evidence"][0]["disposition"] = "boundary"
        self.assertFalse(is_structural_explainability_payload_compatible(invalid))
        with self.assertRaises(ValueError):
            validate_structural_explainability_payload(invalid)

    def test_structural_validator_requires_1_1_or_later_1x(self):
        measure = two_frame_measure((48, 52, 55), (55, 59, 62))
        payload = serialize_structural_explainability(
            build_measure_explainability(measure),
            segment_measure_structurally(measure),
        )
        invalid = copy.deepcopy(payload)
        invalid["schema_version"] = "1.0"
        self.assertFalse(is_structural_explainability_payload_compatible(invalid))

    def test_structural_serializer_requires_same_measure(self):
        measure = two_frame_measure((48, 52, 55), (55, 59, 62))
        report = build_measure_explainability(measure)
        other = Measure(2, TimeSignature(4, 4), ())
        segmentation = segment_measure_structurally(other)
        with self.assertRaises(ValueError):
            serialize_structural_explainability(report, segmentation)


if __name__ == "__main__":
    unittest.main()
