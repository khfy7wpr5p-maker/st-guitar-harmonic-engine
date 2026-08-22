import json
import unittest

from st_guitar_harmonic_engine.guitar_voicing import (
    GUITAR_VOICING_AUTHORITY,
    GUITAR_VOICING_SCHEMA_NAME,
    GUITAR_VOICING_SCHEMA_VERSION,
    CandidateBassRelation,
    ContextualBassState,
    GuitarStringObservation,
    GuitarStringState,
    PitchClassMultiplicity,
    build_guitar_voicing_evidence,
    describe_bass_against_candidate,
    describe_candidate_tone_doubling,
    is_guitar_voicing_payload_compatible,
    serialize_guitar_voicing,
)


def sounding(string_number, fret, midi_pitch):
    return GuitarStringObservation(
        string_number,
        GuitarStringState.SOUNDING,
        fret,
        midi_pitch,
    )


def muted(string_number):
    return GuitarStringObservation(string_number, GuitarStringState.MUTED)


def missing(string_number):
    return GuitarStringObservation(string_number, GuitarStringState.MISSING)


class GuitarVoicingEvidenceTests(unittest.TestCase):
    def test_string_fret_pitch_open_muted_missing_and_span_are_descriptive(self):
        voicing = build_guitar_voicing_evidence(
            (
                muted(6),
                sounding(5, 3, 48),  # C
                sounding(4, 2, 52),  # E
                sounding(3, 0, 55),  # G open
                sounding(2, 1, 60),  # C duplicate
                sounding(1, 0, 64),  # E duplicate/open
            )
        )
        self.assertEqual(voicing.pitch_classes, (0, 4, 7))
        self.assertEqual(
            voicing.multiplicities,
            (
                PitchClassMultiplicity(0, 2),
                PitchClassMultiplicity(4, 2),
                PitchClassMultiplicity(7, 1),
            ),
        )
        self.assertEqual(voicing.repeated_pitch_classes, (0, 4))
        self.assertEqual(voicing.sounding_bass_pitch, 48)
        self.assertEqual(voicing.sounding_bass_pitch_class, 0)
        self.assertEqual(voicing.open_string_numbers, (1, 3))
        self.assertEqual(voicing.muted_string_numbers, (6,))
        self.assertEqual(voicing.missing_string_numbers, ())
        self.assertEqual(voicing.voicing_span_semitones, 16)
        self.assertEqual(voicing.sounding_occurrence_count, 5)

    def test_octave_and_open_string_doubling_does_not_change_pitch_class_identity(self):
        simple = build_guitar_voicing_evidence(
            (sounding(6, 8, 48), sounding(5, 7, 52), sounding(4, 5, 55))
        )
        doubled = build_guitar_voicing_evidence(
            (
                sounding(6, 8, 48),
                sounding(5, 7, 52),
                sounding(4, 5, 55),
                sounding(3, 0, 60),
                sounding(2, 0, 64),
            )
        )
        self.assertEqual(simple.pitch_classes, doubled.pitch_classes)
        self.assertEqual(simple.pitch_classes, (0, 4, 7))
        self.assertEqual(simple.repeated_pitch_classes, ())
        self.assertEqual(doubled.repeated_pitch_classes, (0, 4))
        self.assertEqual(simple.sounding_occurrence_count, 3)
        self.assertEqual(doubled.sounding_occurrence_count, 5)

    def test_root_third_and_fifth_doubling_is_reported_not_weighted(self):
        voicing = build_guitar_voicing_evidence(
            (
                sounding(6, 8, 48),  # root C
                sounding(5, 7, 52),  # third E
                sounding(4, 5, 55),  # fifth G
                sounding(3, 5, 60),  # root C duplicate
                sounding(2, 5, 64),  # third E duplicate
                sounding(1, 8, 67),  # fifth G duplicate
            )
        )
        doubled = describe_candidate_tone_doubling(voicing, (0, 4, 7))
        self.assertEqual(
            doubled,
            (
                PitchClassMultiplicity(0, 2),
                PitchClassMultiplicity(4, 2),
                PitchClassMultiplicity(7, 2),
            ),
        )
        serialized = serialize_guitar_voicing(voicing)
        self.assertNotIn("confidence", serialized)
        self.assertNotIn("score", serialized)
        self.assertNotIn("decision", serialized)
        self.assertEqual(serialized["authority"], GUITAR_VOICING_AUTHORITY)

    def test_sounding_bass_is_distinct_from_root_and_inversion_possibility(self):
        root_position = build_guitar_voicing_evidence(
            (sounding(6, 8, 48), sounding(5, 7, 52), sounding(4, 5, 55))
        )
        root_bass = describe_bass_against_candidate(
            root_position,
            root_pc=0,
            candidate_pitch_classes=(0, 4, 7),
        )
        self.assertIs(root_bass.candidate_relation, CandidateBassRelation.ROOT)
        self.assertFalse(root_bass.inversion_possible)
        self.assertFalse(root_bass.slash_chord_possible)
        self.assertIs(root_bass.pedal_bass_state, ContextualBassState.UNKNOWN)

        first_inversion = build_guitar_voicing_evidence(
            (sounding(6, 0, 40), sounding(5, 3, 48), sounding(4, 0, 55))
        )
        nonroot_bass = describe_bass_against_candidate(
            first_inversion,
            root_pc=0,
            candidate_pitch_classes=(0, 4, 7),
        )
        self.assertEqual(first_inversion.sounding_bass_pitch_class, 4)
        self.assertIs(
            nonroot_bass.candidate_relation,
            CandidateBassRelation.CHORD_TONE_NON_ROOT,
        )
        self.assertTrue(nonroot_bass.inversion_possible)
        self.assertTrue(nonroot_bass.slash_chord_possible)
        self.assertIs(nonroot_bass.pedal_bass_state, ContextualBassState.UNKNOWN)

    def test_outside_candidate_bass_stays_slash_or_pedal_possibility_not_identity(self):
        voicing = build_guitar_voicing_evidence(
            (sounding(6, 10, 50), sounding(5, 3, 48), sounding(4, 2, 52), sounding(3, 0, 55))
        )
        bass = describe_bass_against_candidate(
            voicing,
            root_pc=0,
            candidate_pitch_classes=(0, 4, 7),
            pedal_bass_state=ContextualBassState.POSSIBLE,
        )
        self.assertIs(bass.candidate_relation, CandidateBassRelation.OUTSIDE_CANDIDATE)
        self.assertFalse(bass.inversion_possible)
        self.assertTrue(bass.slash_chord_possible)
        self.assertIs(bass.pedal_bass_state, ContextualBassState.POSSIBLE)

    def test_silent_voicing_cannot_invent_bass(self):
        voicing = build_guitar_voicing_evidence((muted(6), missing(5)))
        self.assertEqual(voicing.pitch_classes, ())
        self.assertIsNone(voicing.sounding_bass_pitch)
        self.assertIsNone(voicing.voicing_span_semitones)
        bass = describe_bass_against_candidate(
            voicing,
            root_pc=0,
            candidate_pitch_classes=(0, 4, 7),
        )
        self.assertIs(bass.candidate_relation, CandidateBassRelation.SILENT)
        self.assertFalse(bass.inversion_possible)
        self.assertFalse(bass.slash_chord_possible)

    def test_input_order_is_canonical_and_repeated_runs_are_equal(self):
        values = (
            sounding(6, 8, 48),
            sounding(5, 7, 52),
            sounding(4, 5, 55),
            muted(3),
        )
        expected = build_guitar_voicing_evidence(values)
        self.assertEqual(
            build_guitar_voicing_evidence(tuple(reversed(values))),
            expected,
        )
        for _ in range(10):
            self.assertEqual(build_guitar_voicing_evidence(values), expected)

    def test_serialization_is_versioned_stable_and_non_authoritative(self):
        voicing = build_guitar_voicing_evidence(
            (sounding(6, 8, 48), sounding(5, 7, 52), sounding(4, 5, 55))
        )
        payload = serialize_guitar_voicing(voicing)
        self.assertEqual(payload["schema_name"], GUITAR_VOICING_SCHEMA_NAME)
        self.assertEqual(payload["schema_version"], GUITAR_VOICING_SCHEMA_VERSION)
        self.assertEqual(payload["authority"], GUITAR_VOICING_AUTHORITY)
        self.assertTrue(is_guitar_voicing_payload_compatible(payload))
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        for _ in range(10):
            self.assertEqual(
                json.dumps(
                    serialize_guitar_voicing(voicing),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                encoded,
            )

    def test_malformed_string_observations_fail_closed(self):
        with self.assertRaises(ValueError):
            sounding(0, 0, 40)
        with self.assertRaises(ValueError):
            sounding(1, 37, 64)
        with self.assertRaises(ValueError):
            GuitarStringObservation(1, GuitarStringState.MUTED, 0, 64)
        with self.assertRaises(TypeError):
            GuitarStringObservation(True, GuitarStringState.MISSING)
        duplicate = (sounding(1, 0, 64), sounding(1, 1, 65))
        with self.assertRaises(ValueError):
            build_guitar_voicing_evidence(duplicate)
        with self.assertRaises(TypeError):
            build_guitar_voicing_evidence((object(),))

    def test_candidate_relative_helpers_reject_invalid_domains(self):
        voicing = build_guitar_voicing_evidence((sounding(1, 0, 64),))
        with self.assertRaises(ValueError):
            describe_candidate_tone_doubling(voicing, (7, 0, 4))
        with self.assertRaises(ValueError):
            describe_bass_against_candidate(
                voicing,
                root_pc=1,
                candidate_pitch_classes=(0, 4, 7),
            )
        with self.assertRaises(TypeError):
            describe_bass_against_candidate(
                voicing,
                root_pc=0,
                candidate_pitch_classes=(0, 4, 7),
                pedal_bass_state="possible",
            )


if __name__ == "__main__":
    unittest.main()
