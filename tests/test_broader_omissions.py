import unittest

from st_guitar_harmonic_engine import (
    AnalysisStatus,
    ChordQuality,
    HarmonicFrame,
    NoteEvent,
    OmissionKind,
    RationalBeat,
    TieState,
    analyze_frame_exact,
    generate_fifth_omission_candidates,
    generate_incomplete_chord_candidates,
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


class BroaderIncompleteChordEvidenceTests(unittest.TestCase):
    def test_missing_third_preserves_major_minor_ambiguity(self):
        candidates = generate_incomplete_chord_candidates(frame(48, 55))  # C + G
        observed = {
            (item.root_pc, item.quality, item.omission, item.omitted_pc)
            for item in candidates
        }
        self.assertEqual(
            observed,
            {
                (0, ChordQuality.MAJOR, OmissionKind.THIRD, 4),
                (0, ChordQuality.MINOR, OmissionKind.THIRD, 3),
            },
        )

    def test_missing_root_and_missing_fifth_can_coexist_as_evidence(self):
        candidates = generate_incomplete_chord_candidates(frame(52, 55))  # E + G
        observed = {
            (item.root_pc, item.quality, item.omission, item.omitted_pc)
            for item in candidates
        }
        self.assertIn(
            (0, ChordQuality.MAJOR, OmissionKind.ROOT, 0),
            observed,
        )
        self.assertIn(
            (4, ChordQuality.MINOR, OmissionKind.FIFTH, 11),
            observed,
        )
        self.assertGreaterEqual(len(observed), 2)

    def test_dominant_seventh_missing_third_is_supported(self):
        candidates = generate_incomplete_chord_candidates(frame(48, 55, 58))  # C G Bb
        matching = tuple(
            item
            for item in candidates
            if item.root_pc == 0 and item.quality is ChordQuality.DOMINANT_SEVENTH
        )
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].omission, OmissionKind.THIRD)
        self.assertEqual(matching[0].omitted_pc, 4)
        self.assertEqual(matching[0].full_pitch_classes, (0, 4, 7, 10))

    def test_exact_match_suppresses_missing_seventh_interpretations(self):
        target = frame(48, 52, 55)  # exact C major
        self.assertEqual(analyze_frame_exact(target).status, AnalysisStatus.UNIQUE)
        self.assertEqual(generate_incomplete_chord_candidates(target), ())

    def test_legacy_fifth_only_surface_remains_fifth_only(self):
        target = frame(48, 52)  # C + E
        legacy = generate_fifth_omission_candidates(target)
        self.assertEqual(len(legacy), 1)
        self.assertEqual(
            (legacy[0].root_pc, legacy[0].quality, legacy[0].omission, legacy[0].omitted_pc),
            (0, ChordQuality.MAJOR, OmissionKind.FIFTH, 7),
        )
        broader = generate_incomplete_chord_candidates(target)
        self.assertIn(legacy[0], broader)
        self.assertTrue(all(item.omission is OmissionKind.FIFTH for item in legacy))

    def test_exact_diminished_triad_is_not_reinterpreted_as_incomplete_basic_chord(self):
        target = frame(48, 51, 54)
        self.assertEqual(analyze_frame_exact(target).status, AnalysisStatus.UNIQUE)
        self.assertEqual(generate_incomplete_chord_candidates(target), ())

    def test_candidates_never_introduce_unsupported_qualities(self):
        allowed = {
            ChordQuality.MAJOR,
            ChordQuality.MINOR,
            ChordQuality.DOMINANT_SEVENTH,
            ChordQuality.MAJOR_SEVENTH,
            ChordQuality.MINOR_SEVENTH,
        }
        for target in (frame(48, 55), frame(52, 55), frame(48, 55, 58)):
            self.assertTrue(
                all(item.quality in allowed for item in generate_incomplete_chord_candidates(target))
            )

    def test_generator_is_deterministic(self):
        target = frame(52, 55)
        expected = generate_incomplete_chord_candidates(target)
        for _ in range(10):
            self.assertEqual(generate_incomplete_chord_candidates(target), expected)

    def test_generator_does_not_change_exact_analysis(self):
        target = frame(48, 55)
        before = analyze_frame_exact(target)
        generate_incomplete_chord_candidates(target)
        self.assertEqual(analyze_frame_exact(target), before)

    def test_rejects_non_frame_input(self):
        with self.assertRaises(TypeError):
            generate_incomplete_chord_candidates(object())


if __name__ == "__main__":
    unittest.main()
