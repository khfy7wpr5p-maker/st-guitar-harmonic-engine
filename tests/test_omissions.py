import unittest

from st_guitar_harmonic_engine import (
    ChordQuality,
    Measure,
    NoteEvent,
    OmissionKind,
    RationalBeat,
    TimeSignature,
    build_harmonic_frames,
    generate_fifth_omission_candidates,
)


def frame_for(*pitches):
    measure = Measure(
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
    return build_harmonic_frames(measure)[0]


class FifthOmissionCandidateTests(unittest.TestCase):
    def test_major_triad_missing_fifth(self):
        candidates = generate_fifth_omission_candidates(frame_for(48, 52))
        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual((candidate.root_pc, candidate.quality), (0, ChordQuality.MAJOR))
        self.assertEqual(candidate.omitted_pc, 7)
        self.assertEqual(candidate.omission, OmissionKind.FIFTH)
        self.assertEqual(candidate.full_pitch_classes, (0, 4, 7))

    def test_minor_triad_missing_fifth(self):
        candidates = generate_fifth_omission_candidates(frame_for(48, 51))
        self.assertEqual([(c.root_pc, c.quality) for c in candidates], [
            (0, ChordQuality.MINOR),
        ])

    def test_dominant_seventh_missing_fifth(self):
        candidates = generate_fifth_omission_candidates(frame_for(55, 59, 65))
        self.assertEqual([(c.root_pc, c.quality, c.omitted_pc) for c in candidates], [
            (7, ChordQuality.DOMINANT_SEVENTH, 2),
        ])

    def test_major_seventh_missing_fifth(self):
        candidates = generate_fifth_omission_candidates(frame_for(48, 52, 59))
        self.assertEqual([(c.root_pc, c.quality) for c in candidates], [
            (0, ChordQuality.MAJOR_SEVENTH),
        ])

    def test_minor_seventh_missing_fifth(self):
        candidates = generate_fifth_omission_candidates(frame_for(48, 51, 58))
        self.assertEqual([(c.root_pc, c.quality) for c in candidates], [
            (0, ChordQuality.MINOR_SEVENTH),
        ])

    def test_missing_third_is_not_inferred(self):
        self.assertEqual(generate_fifth_omission_candidates(frame_for(48, 55)), ())

    def test_exact_match_suppresses_incomplete_inference(self):
        self.assertEqual(generate_fifth_omission_candidates(frame_for(48, 52, 55)), ())

    def test_octave_duplicates_do_not_change_missing_fifth_evidence(self):
        candidates = generate_fifth_omission_candidates(frame_for(48, 60, 64))
        self.assertEqual([(c.root_pc, c.quality) for c in candidates], [
            (0, ChordQuality.MAJOR),
        ])

    def test_rejects_non_frame_input(self):
        with self.assertRaises(TypeError):
            generate_fifth_omission_candidates(object())


if __name__ == "__main__":
    unittest.main()
