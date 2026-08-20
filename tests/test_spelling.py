import unittest

from st_guitar_harmonic_engine import (
    NoteEvent,
    PitchStep,
    RationalBeat,
    WrittenPitch,
)


class WrittenPitchTests(unittest.TestCase):
    def test_canonical_names_cover_accidentals(self):
        self.assertEqual(WrittenPitch(PitchStep.C, 1, 4).name, "C#4")
        self.assertEqual(WrittenPitch(PitchStep.B, -2, 3).name, "Bbb3")
        self.assertEqual(WrittenPitch(PitchStep.F, 0, 5).name, "F5")

    def test_rejects_untyped_step(self):
        with self.assertRaises(TypeError):
            WrittenPitch("C", 0, 4)  # type: ignore[arg-type]

    def test_rejects_unsupported_alter(self):
        with self.assertRaises(ValueError):
            WrittenPitch(PitchStep.C, 3, 4)

    def test_rejects_out_of_range_octave(self):
        with self.assertRaises(ValueError):
            WrittenPitch(PitchStep.C, 0, 10)

    def test_note_event_preserves_written_spelling_without_guessing_transposition(self):
        written = WrittenPitch(PitchStep.E, 0, 4)
        event = NoteEvent(
            measure_number=1,
            staff=1,
            voice=1,
            midi_pitch=52,
            onset=RationalBeat(0),
            duration=RationalBeat(1),
            written_pitch=written,
        )
        self.assertEqual(event.midi_pitch, 52)
        self.assertEqual(event.written_pitch, written)

    def test_note_event_rejects_invalid_written_pitch_type(self):
        with self.assertRaises(TypeError):
            NoteEvent(
                measure_number=1,
                staff=1,
                voice=1,
                midi_pitch=60,
                onset=RationalBeat(0),
                duration=RationalBeat(1),
                written_pitch="C4",  # type: ignore[arg-type]
            )


if __name__ == "__main__":
    unittest.main()
