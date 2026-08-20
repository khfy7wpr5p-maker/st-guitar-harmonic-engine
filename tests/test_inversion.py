import unittest

from st_guitar_harmonic_engine import (
    ChordCandidate,
    ChordQuality,
    Inversion,
    Measure,
    NoteEvent,
    RationalBeat,
    TimeSignature,
    analyze_bass_and_inversion,
    build_harmonic_frames,
    generate_exact_chord_candidates,
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


def only_candidate(frame):
    candidates = generate_exact_chord_candidates(frame)
    if len(candidates) != 1:
        raise AssertionError(f"expected one candidate, got {candidates!r}")
    return candidates[0]


class BassAndInversionTests(unittest.TestCase):
    def test_root_position_major(self):
        frame = frame_for(48, 55, 64)
        analysis = analyze_bass_and_inversion(frame, only_candidate(frame))
        self.assertEqual((analysis.bass_midi, analysis.bass_pc), (48, 0))
        self.assertEqual(analysis.inversion, Inversion.ROOT_POSITION)

    def test_first_inversion_major(self):
        frame = frame_for(52, 60, 67)
        analysis = analyze_bass_and_inversion(frame, only_candidate(frame))
        self.assertEqual(analysis.inversion, Inversion.FIRST)

    def test_second_inversion_major(self):
        frame = frame_for(55, 60, 64)
        analysis = analyze_bass_and_inversion(frame, only_candidate(frame))
        self.assertEqual(analysis.inversion, Inversion.SECOND)

    def test_third_inversion_dominant_seventh(self):
        frame = frame_for(53, 55, 59, 62)
        analysis = analyze_bass_and_inversion(frame, only_candidate(frame))
        self.assertEqual(analysis.inversion, Inversion.THIRD)

    def test_octave_duplicates_do_not_hide_literal_bass(self):
        frame = frame_for(36, 48, 52, 55)
        analysis = analyze_bass_and_inversion(frame, only_candidate(frame))
        self.assertEqual(analysis.bass_midi, 36)
        self.assertEqual(analysis.inversion, Inversion.ROOT_POSITION)

    def test_rejects_candidate_for_different_evidence(self):
        frame = frame_for(60, 64, 67)
        wrong = ChordCandidate(9, ChordQuality.MINOR, (0, 4, 9))
        with self.assertRaises(ValueError):
            analyze_bass_and_inversion(frame, wrong)


if __name__ == "__main__":
    unittest.main()
