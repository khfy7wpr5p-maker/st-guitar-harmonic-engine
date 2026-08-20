import unittest

from st_guitar_harmonic_engine import (
    AlterationKind,
    ChordQuality,
    HarmonicFrame,
    NoteEvent,
    RationalBeat,
    SuspendedChordKind,
    TieState,
    analyze_frame_exact,
    generate_altered_tension_candidates,
    generate_suspended_chord_candidates,
)


def frame(*pitches):
    events = tuple(
        NoteEvent(
            measure_number=1,
            staff=1,
            voice=index + 1,
            midi_pitch=pitch,
            onset=RationalBeat(0),
            duration=RationalBeat(1),
            tie=TieState.NONE,
        )
        for index, pitch in enumerate(pitches)
    )
    return HarmonicFrame(1, RationalBeat(0), RationalBeat(1), events)


class SuspendedChordEvidenceTests(unittest.TestCase):
    def test_sus2_pitch_set_preserves_dual_root_ambiguity(self):
        candidates = generate_suspended_chord_candidates(frame(48, 50, 55))  # C D G
        observed = {(item.root_pc, item.kind) for item in candidates}
        self.assertEqual(
            observed,
            {
                (0, SuspendedChordKind.SUS2),
                (7, SuspendedChordKind.SUS4),
            },
        )

    def test_sus4_pitch_set_preserves_dual_root_ambiguity(self):
        candidates = generate_suspended_chord_candidates(frame(48, 53, 55))  # C F G
        observed = {(item.root_pc, item.kind) for item in candidates}
        self.assertEqual(
            observed,
            {
                (0, SuspendedChordKind.SUS4),
                (5, SuspendedChordKind.SUS2),
            },
        )

    def test_exact_basic_chord_suppresses_suspended_inference(self):
        target = frame(48, 52, 55)
        self.assertTrue(analyze_frame_exact(target).candidates)
        self.assertEqual(generate_suspended_chord_candidates(target), ())

    def test_non_triad_cardinality_is_rejected(self):
        self.assertEqual(generate_suspended_chord_candidates(frame(48, 50)), ())
        self.assertEqual(generate_suspended_chord_candidates(frame(48, 49, 50, 55)), ())

    def test_octave_duplicates_do_not_change_suspended_pitch_set(self):
        self.assertEqual(
            generate_suspended_chord_candidates(frame(48, 50, 55, 60)),
            generate_suspended_chord_candidates(frame(48, 50, 55)),
        )

    def test_suspended_generator_is_deterministic_and_non_mutating(self):
        target = frame(48, 50, 55)
        before = analyze_frame_exact(target)
        expected = generate_suspended_chord_candidates(target)
        for _ in range(10):
            self.assertEqual(generate_suspended_chord_candidates(target), expected)
        self.assertEqual(analyze_frame_exact(target), before)

    def test_suspended_generator_rejects_non_frame_input(self):
        with self.assertRaises(TypeError):
            generate_suspended_chord_candidates(object())


class AlteredTensionEvidenceTests(unittest.TestCase):
    def _assert_c_dominant_alteration(self, pitches, kind, alteration_pc):
        candidates = generate_altered_tension_candidates(frame(*pitches))
        matching = tuple(
            item
            for item in candidates
            if item.root_pc == 0 and item.alteration is kind
        )
        self.assertEqual(len(matching), 1)
        item = matching[0]
        self.assertIs(item.base_quality, ChordQuality.DOMINANT_SEVENTH)
        self.assertEqual(item.base_pitch_classes, (0, 4, 7, 10))
        self.assertEqual(item.alteration_pc, alteration_pc)

    def test_flat_ninth_over_complete_dominant_seventh(self):
        self._assert_c_dominant_alteration(
            (48, 49, 52, 55, 58), AlterationKind.FLAT_NINTH, 1
        )

    def test_sharp_ninth_over_complete_dominant_seventh(self):
        self._assert_c_dominant_alteration(
            (48, 51, 52, 55, 58), AlterationKind.SHARP_NINTH, 3
        )

    def test_sharp_eleventh_over_complete_dominant_seventh(self):
        self._assert_c_dominant_alteration(
            (48, 52, 54, 55, 58), AlterationKind.SHARP_ELEVENTH, 6
        )

    def test_flat_thirteenth_over_complete_dominant_seventh(self):
        self._assert_c_dominant_alteration(
            (48, 52, 55, 56, 58), AlterationKind.FLAT_THIRTEENTH, 8
        )

    def test_natural_ninth_is_not_an_alteration(self):
        self.assertEqual(
            generate_altered_tension_candidates(frame(48, 50, 52, 55, 58)),
            (),
        )

    def test_missing_dominant_base_tone_plus_alteration_is_rejected(self):
        self.assertEqual(
            generate_altered_tension_candidates(frame(48, 49, 52, 58)),
            (),
        )

    def test_multiple_alterations_are_rejected(self):
        self.assertEqual(
            generate_altered_tension_candidates(frame(48, 49, 51, 52, 55, 58)),
            (),
        )

    def test_non_dominant_base_is_not_colored_as_altered_dominant(self):
        self.assertEqual(
            generate_altered_tension_candidates(frame(48, 49, 52, 55, 59)),
            (),
        )

    def test_altered_generator_is_deterministic_and_non_mutating(self):
        target = frame(48, 49, 52, 55, 58)
        before = analyze_frame_exact(target)
        expected = generate_altered_tension_candidates(target)
        for _ in range(10):
            self.assertEqual(generate_altered_tension_candidates(target), expected)
        self.assertEqual(analyze_frame_exact(target), before)

    def test_altered_generator_rejects_non_frame_input(self):
        with self.assertRaises(TypeError):
            generate_altered_tension_candidates(object())


if __name__ == "__main__":
    unittest.main()
