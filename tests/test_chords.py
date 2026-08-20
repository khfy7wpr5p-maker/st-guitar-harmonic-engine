import unittest

from st_guitar_harmonic_engine import (
    ChordQuality,
    Measure,
    NoteEvent,
    RationalBeat,
    TimeSignature,
    build_harmonic_frames,
    generate_exact_chord_candidates,
)


def frame_for(*pitches):
    events = tuple(
        NoteEvent(
            measure_number=1,
            staff=1,
            voice=index + 1,
            midi_pitch=pitch,
            onset=RationalBeat(0),
            duration=RationalBeat(4),
        )
        for index, pitch in enumerate(pitches)
    )
    measure = Measure(1, TimeSignature(4, 4), events)
    return build_harmonic_frames(measure)[0]


class ExactChordCandidateTests(unittest.TestCase):
    def test_major_triad(self):
        candidates = generate_exact_chord_candidates(frame_for(60, 64, 67))
        self.assertEqual([(c.root_pc, c.quality) for c in candidates], [
            (0, ChordQuality.MAJOR),
        ])

    def test_minor_triad(self):
        candidates = generate_exact_chord_candidates(frame_for(57, 60, 64))
        self.assertEqual([(c.root_pc, c.quality) for c in candidates], [
            (9, ChordQuality.MINOR),
        ])

    def test_dominant_seventh(self):
        candidates = generate_exact_chord_candidates(frame_for(55, 59, 62, 65))
        self.assertEqual([(c.root_pc, c.quality) for c in candidates], [
            (7, ChordQuality.DOMINANT_SEVENTH),
        ])

    def test_octave_duplicates_do_not_change_candidate(self):
        candidates = generate_exact_chord_candidates(frame_for(48, 60, 64, 67))
        self.assertEqual([(c.root_pc, c.quality) for c in candidates], [
            (0, ChordQuality.MAJOR),
        ])

    def test_symmetric_diminished_seventh_preserves_all_roots(self):
        candidates = generate_exact_chord_candidates(frame_for(60, 63, 66, 69))
        self.assertEqual(
            [(c.root_pc, c.quality) for c in candidates],
            [
                (0, ChordQuality.DIMINISHED_SEVENTH),
                (3, ChordQuality.DIMINISHED_SEVENTH),
                (6, ChordQuality.DIMINISHED_SEVENTH),
                (9, ChordQuality.DIMINISHED_SEVENTH),
            ],
        )

    def test_non_template_sonority_returns_no_candidate(self):
        self.assertEqual(generate_exact_chord_candidates(frame_for(60, 62, 67)), ())


if __name__ == "__main__":
    unittest.main()
