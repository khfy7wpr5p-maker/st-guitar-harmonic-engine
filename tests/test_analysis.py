import unittest

from st_guitar_harmonic_engine import (
    AnalysisStatus,
    ChordQuality,
    Inversion,
    Measure,
    NoteEvent,
    RationalBeat,
    TimeSignature,
    analyze_measure_exact,
)


def event(pitch, onset=0, duration=4, *, voice=1):
    return NoteEvent(
        measure_number=1,
        staff=1,
        voice=voice,
        midi_pitch=pitch,
        onset=RationalBeat(onset),
        duration=RationalBeat(duration),
    )


class ExactAnalysisOrchestrationTests(unittest.TestCase):
    def test_unique_major_carries_bass_and_inversion(self):
        measure = Measure(
            1,
            TimeSignature(4, 4),
            (event(52), event(60, voice=2), event(67, voice=3)),
        )
        result = analyze_measure_exact(measure)[0]
        self.assertEqual(result.status, AnalysisStatus.UNIQUE)
        self.assertEqual(result.candidates[0].candidate.root_pc, 0)
        self.assertEqual(result.candidates[0].candidate.quality, ChordQuality.MAJOR)
        self.assertEqual(result.candidates[0].bass.inversion, Inversion.FIRST)

    def test_symmetric_diminished_seventh_is_ambiguous(self):
        measure = Measure(
            1,
            TimeSignature(4, 4),
            (event(48), event(51, voice=2), event(54, voice=3), event(57, voice=4)),
        )
        result = analyze_measure_exact(measure)[0]
        self.assertEqual(result.status, AnalysisStatus.AMBIGUOUS)
        self.assertEqual(len(result.candidates), 4)

    def test_unknown_sonority_is_no_match(self):
        measure = Measure(
            1,
            TimeSignature(4, 4),
            (event(60), event(62, voice=2), event(67, voice=3)),
        )
        result = analyze_measure_exact(measure)[0]
        self.assertEqual(result.status, AnalysisStatus.NO_MATCH)
        self.assertEqual(result.candidates, ())

    def test_measure_with_note_change_returns_ordered_results(self):
        measure = Measure(
            1,
            TimeSignature(4, 4),
            (
                event(48, 0, 4, voice=1),
                event(64, 0, 2, voice=2),
                event(67, 0, 2, voice=3),
                event(65, 2, 2, voice=2),
                event(69, 2, 2, voice=3),
            ),
        )
        results = analyze_measure_exact(measure)
        self.assertEqual([(r.start, r.end) for r in results], [
            (RationalBeat(0), RationalBeat(2)),
            (RationalBeat(2), RationalBeat(4)),
        ])

    def test_empty_measure_returns_no_results(self):
        self.assertEqual(analyze_measure_exact(Measure(1, TimeSignature(4, 4))), ())


if __name__ == "__main__":
    unittest.main()
