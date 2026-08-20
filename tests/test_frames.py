import unittest

from st_guitar_harmonic_engine import (
    Measure,
    NoteEvent,
    RationalBeat,
    TimeSignature,
    build_harmonic_frames,
)


def note(pitch, onset, duration, *, voice=1, measure=1):
    return NoteEvent(
        measure_number=measure,
        staff=1,
        voice=voice,
        midi_pitch=pitch,
        onset=RationalBeat(*onset),
        duration=RationalBeat(*duration),
    )


class HarmonicFrameBuilderTests(unittest.TestCase):
    def test_sustained_triad_is_one_frame(self):
        measure = Measure(
            1,
            TimeSignature(4, 4),
            (
                note(60, (0, 1), (4, 1)),
                note(64, (0, 1), (4, 1), voice=2),
                note(67, (0, 1), (4, 1), voice=3),
            ),
        )
        frames = build_harmonic_frames(measure)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].pitch_classes, (0, 4, 7))
        self.assertEqual(frames[0].duration, RationalBeat(4))

    def test_note_change_splits_frames_at_exact_boundary(self):
        measure = Measure(
            1,
            TimeSignature(4, 4),
            (
                note(48, (0, 1), (4, 1), voice=2),
                note(60, (0, 1), (2, 1)),
                note(62, (2, 1), (2, 1)),
            ),
        )
        frames = build_harmonic_frames(measure)
        self.assertEqual([(f.start, f.end) for f in frames], [
            (RationalBeat(0), RationalBeat(2)),
            (RationalBeat(2), RationalBeat(4)),
        ])
        self.assertEqual(frames[0].pitch_classes, (0,))
        self.assertEqual(frames[1].pitch_classes, (0, 2))

    def test_overlapping_voices_produce_constant_active_sets(self):
        measure = Measure(
            1,
            TimeSignature(4, 4),
            (
                note(48, (0, 1), (4, 1), voice=2),
                note(64, (1, 1), (2, 1), voice=1),
            ),
        )
        frames = build_harmonic_frames(measure)
        self.assertEqual([(f.start, f.end, len(f.events)) for f in frames], [
            (RationalBeat(0), RationalBeat(1), 1),
            (RationalBeat(1), RationalBeat(3), 2),
            (RationalBeat(3), RationalBeat(4), 1),
        ])

    def test_silent_gap_is_not_fabricated_as_harmony(self):
        measure = Measure(
            1,
            TimeSignature(4, 4),
            (
                note(60, (0, 1), (1, 1)),
                note(67, (3, 1), (1, 1)),
            ),
        )
        frames = build_harmonic_frames(measure)
        self.assertEqual([(f.start, f.end) for f in frames], [
            (RationalBeat(0), RationalBeat(1)),
            (RationalBeat(3), RationalBeat(4)),
        ])

    def test_empty_measure_has_no_frames(self):
        self.assertEqual(build_harmonic_frames(Measure(1, TimeSignature(3, 4))), ())


if __name__ == "__main__":
    unittest.main()
