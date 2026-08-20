import unittest

from st_guitar_harmonic_engine import (
    AnalysisStatus,
    HarmonicRole,
    Measure,
    NoteEvent,
    RationalBeat,
    ResolutionStatus,
    TimeSignature,
    TonalContext,
    TonalMode,
    analyze_measure_in_context,
)


def measure_for(*pitches):
    return Measure(
        1,
        TimeSignature(4, 4),
        tuple(
            NoteEvent(
                measure_number=1,
                staff=1,
                voice=index + 1,
                midi_pitch=pitch,
                onset=RationalBeat(0),
                duration=RationalBeat(4),
            )
            for index, pitch in enumerate(pitches)
        ),
    )


class TonalContextTests(unittest.TestCase):
    def test_rejects_invalid_tonic(self):
        with self.assertRaises(ValueError):
            TonalContext(12, TonalMode.MAJOR)
        with self.assertRaises(TypeError):
            TonalContext(True, TonalMode.MAJOR)

    def test_rejects_untyped_mode(self):
        with self.assertRaises(TypeError):
            TonalContext(0, "major")


class ContextResolverTests(unittest.TestCase):
    def test_major_tonic_is_annotated(self):
        result = analyze_measure_in_context(
            measure_for(48, 52, 55),
            TonalContext(0, TonalMode.MAJOR),
        )[0]
        self.assertEqual(result.status, ResolutionStatus.RESOLVED)
        selected = result.selected[0]
        self.assertTrue(selected.in_context)
        self.assertEqual(selected.scale_degree, 1)
        self.assertEqual(selected.role, HarmonicRole.TONIC)

    def test_major_dominant_seventh_is_dominant(self):
        result = analyze_measure_in_context(
            measure_for(55, 59, 62, 65),
            TonalContext(0, TonalMode.MAJOR),
        )[0]
        selected = result.selected[0]
        self.assertEqual(selected.scale_degree, 5)
        self.assertEqual(selected.role, HarmonicRole.DOMINANT)

    def test_minor_major_dominant_variant_is_in_context(self):
        result = analyze_measure_in_context(
            measure_for(52, 56, 59),
            TonalContext(9, TonalMode.MINOR),
        )[0]
        selected = result.selected[0]
        self.assertTrue(selected.in_context)
        self.assertEqual(selected.scale_degree, 5)
        self.assertEqual(selected.role, HarmonicRole.DOMINANT)

    def test_context_resolves_symmetric_leading_tone_diminished_seventh(self):
        result = analyze_measure_in_context(
            measure_for(59, 62, 65, 68),
            TonalContext(0, TonalMode.MINOR),
        )[0]
        self.assertEqual(result.exact.status, AnalysisStatus.AMBIGUOUS)
        self.assertEqual(len(result.candidates), 4)
        self.assertEqual(result.status, ResolutionStatus.RESOLVED)
        self.assertEqual(len(result.selected), 1)
        selected = result.selected[0]
        self.assertEqual(selected.analysis.candidate.root_pc, 11)
        self.assertEqual(selected.scale_degree, 7)
        self.assertEqual(selected.role, HarmonicRole.DOMINANT)

    def test_context_cannot_force_unsupported_augmented_ambiguity(self):
        result = analyze_measure_in_context(
            measure_for(60, 64, 68),
            TonalContext(0, TonalMode.MAJOR),
        )[0]
        self.assertEqual(result.exact.status, AnalysisStatus.AMBIGUOUS)
        self.assertEqual(result.status, ResolutionStatus.AMBIGUOUS)
        self.assertEqual(len(result.selected), 3)
        self.assertTrue(all(not item.in_context for item in result.selected))

    def test_unique_chromatic_candidate_is_preserved_not_rejected(self):
        result = analyze_measure_in_context(
            measure_for(50, 54, 57),
            TonalContext(0, TonalMode.MAJOR),
        )[0]
        self.assertEqual(result.status, ResolutionStatus.RESOLVED)
        self.assertEqual(len(result.selected), 1)
        self.assertFalse(result.selected[0].in_context)
        self.assertEqual(result.selected[0].role, HarmonicRole.CHROMATIC)

    def test_no_match_remains_no_match(self):
        result = analyze_measure_in_context(
            measure_for(60, 62, 67),
            TonalContext(0, TonalMode.MAJOR),
        )[0]
        self.assertEqual(result.exact.status, AnalysisStatus.NO_MATCH)
        self.assertEqual(result.status, ResolutionStatus.NO_MATCH)
        self.assertEqual(result.candidates, ())
        self.assertEqual(result.selected, ())


if __name__ == "__main__":
    unittest.main()
