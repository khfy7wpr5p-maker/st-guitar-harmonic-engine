import unittest

from st_guitar_harmonic_engine import NoteEvent, RationalBeat, TieState


class RationalBeatTests(unittest.TestCase):
    def test_reduces_fraction_deterministically(self):
        beat = RationalBeat(6, 8)
        self.assertEqual((beat.numerator, beat.denominator), (3, 4))

    def test_rejects_non_positive_denominator(self):
        with self.assertRaises(ValueError):
            RationalBeat(1, 0)

    def test_rejects_boolean_as_integer(self):
        with self.assertRaises(TypeError):
            RationalBeat(True, 1)


class NoteEventTests(unittest.TestCase):
    def make_event(self, **overrides):
        values = {
            "measure_number": 1,
            "staff": 1,
            "voice": 1,
            "midi_pitch": 60,
            "onset": RationalBeat(1, 2),
            "duration": RationalBeat(1, 4),
            "tie": TieState.NONE,
        }
        values.update(overrides)
        return NoteEvent(**values)

    def test_valid_event_has_exact_end(self):
        event = self.make_event()
        self.assertEqual(event.end, RationalBeat(3, 4))

    def test_accepts_midi_boundaries(self):
        self.make_event(midi_pitch=0)
        self.make_event(midi_pitch=127)

    def test_rejects_out_of_range_midi(self):
        with self.assertRaises(ValueError):
            self.make_event(midi_pitch=128)

    def test_rejects_invalid_location_identifiers(self):
        for field in ("measure_number", "staff", "voice"):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    self.make_event(**{field: 0})

    def test_rejects_negative_onset(self):
        with self.assertRaises(ValueError):
            self.make_event(onset=RationalBeat(-1, 4))

    def test_rejects_zero_duration(self):
        with self.assertRaises(ValueError):
            self.make_event(duration=RationalBeat(0, 1))


if __name__ == "__main__":
    unittest.main()
