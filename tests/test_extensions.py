import unittest

from st_guitar_harmonic_engine import (
    AnalysisStatus,
    ChordQuality,
    ExtensionKind,
    HarmonicFrame,
    NoteEvent,
    RationalBeat,
    TieState,
    analyze_frame_exact,
    generate_extension_candidates,
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


class NaturalExtensionEvidenceTests(unittest.TestCase):
    def test_major_triad_plus_natural_ninth_is_detected(self):
        candidates = generate_extension_candidates(frame(48, 50, 52, 55))  # C D E G
        matching = tuple(
            item
            for item in candidates
            if item.root_pc == 0
            and item.base_quality is ChordQuality.MAJOR
            and item.extension is ExtensionKind.NATURAL_NINTH
        )
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].base_pitch_classes, (0, 4, 7))
        self.assertEqual(matching[0].extension_pc, 2)
        self.assertEqual(matching[0].observed_pitch_classes, (0, 2, 4, 7))

    def test_minor_triad_plus_natural_ninth_is_detected(self):
        candidates = generate_extension_candidates(frame(48, 50, 51, 55))  # C D Eb G
        self.assertIn(
            (0, ChordQuality.MINOR, ExtensionKind.NATURAL_NINTH),
            {(item.root_pc, item.base_quality, item.extension) for item in candidates},
        )

    def test_major_triad_plus_natural_eleventh_is_detected(self):
        candidates = generate_extension_candidates(frame(48, 52, 53, 55))  # C E F G
        self.assertIn(
            (0, ChordQuality.MAJOR, ExtensionKind.NATURAL_ELEVENTH),
            {(item.root_pc, item.base_quality, item.extension) for item in candidates},
        )

    def test_dominant_seventh_plus_natural_ninth_is_detected(self):
        candidates = generate_extension_candidates(frame(48, 50, 52, 55, 58))  # C D E G Bb
        matching = tuple(
            item
            for item in candidates
            if item.root_pc == 0
            and item.base_quality is ChordQuality.DOMINANT_SEVENTH
            and item.extension is ExtensionKind.NATURAL_NINTH
        )
        self.assertEqual(len(matching), 1)

    def test_exact_basic_match_suppresses_extension_inference(self):
        target = frame(48, 52, 55, 57)  # pitch set is exact A minor seventh
        self.assertEqual(analyze_frame_exact(target).status, AnalysisStatus.UNIQUE)
        self.assertEqual(generate_extension_candidates(target), ())

    def test_flat_ninth_is_not_supported(self):
        target = frame(48, 49, 52, 55, 58)  # C Db E G Bb
        self.assertEqual(generate_extension_candidates(target), ())

    def test_sharp_eleventh_is_not_supported(self):
        target = frame(48, 52, 54, 55, 58)  # C E F# G Bb
        self.assertEqual(generate_extension_candidates(target), ())

    def test_two_extensions_are_not_collapsed_into_one_candidate(self):
        target = frame(48, 50, 52, 53, 55, 58)  # C7 + D + F
        self.assertEqual(generate_extension_candidates(target), ())

    def test_missing_base_tone_plus_extension_is_not_inferred(self):
        target = frame(48, 50, 52)  # C D E, missing G
        self.assertEqual(generate_extension_candidates(target), ())

    def test_generator_preserves_all_valid_ambiguity_and_is_deterministic(self):
        target = frame(48, 50, 52, 55)
        expected = generate_extension_candidates(target)
        self.assertGreaterEqual(len(expected), 1)
        for _ in range(10):
            self.assertEqual(generate_extension_candidates(target), expected)

    def test_generator_does_not_change_exact_analysis(self):
        target = frame(48, 50, 52, 55)
        before = analyze_frame_exact(target)
        generate_extension_candidates(target)
        self.assertEqual(analyze_frame_exact(target), before)

    def test_rejects_non_frame_input(self):
        with self.assertRaises(TypeError):
            generate_extension_candidates(object())


if __name__ == "__main__":
    unittest.main()
