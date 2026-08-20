import unittest

from st_guitar_harmonic_engine import (
    Measure,
    NoteEvent,
    RationalBeat,
    TieState,
    TimeSignature,
)


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


class TimeSignatureTests(unittest.TestCase):
    def test_nominal_lengths_use_quarter_note_units(self):
        self.assertEqual(TimeSignature(4, 4).quarter_length, RationalBeat(4))
        self.assertEqual(TimeSignature(6, 8).quarter_length, RationalBeat(3))
        self.assertEqual(TimeSignature(3, 4).quarter_length, RationalBeat(3))

    def test_rejects_non_positive_values(self):
        for values in ((0, 4), (4, 0), (-3, 4)):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    TimeSignature(*values)


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


class MeasureTests(unittest.TestCase):
    def event(self, **overrides):
        values = {
            "measure_number": 2,
            "staff": 1,
            "voice": 1,
            "midi_pitch": 60,
            "onset": RationalBeat(0),
            "duration": RationalBeat(1),
        }
        values.update(overrides)
        return NoteEvent(**values)

    def test_defaults_to_nominal_meter_duration(self):
        measure = Measure(2, TimeSignature(6, 8))
        self.assertEqual(measure.duration, RationalBeat(3))

    def test_supports_explicit_pickup_duration(self):
        measure = Measure(
            2,
            TimeSignature(4, 4),
            events=(self.event(duration=RationalBeat(1)),),
            actual_duration=RationalBeat(1),
        )
        self.assertEqual(measure.duration, RationalBeat(1))

    def test_rejects_event_from_different_measure(self):
        with self.assertRaises(ValueError):
            Measure(2, TimeSignature(4, 4), events=(self.event(measure_number=3),))

    def test_rejects_event_overflow(self):
        with self.assertRaises(ValueError):
            Measure(
                2,
                TimeSignature(4, 4),
                events=(
                    self.event(onset=RationalBeat(7, 2), duration=RationalBeat(1)),
                ),
            )

    def test_events_are_canonicalized(self):
        later = self.event(onset=RationalBeat(2), midi_pitch=64)
        earlier_high = self.event(onset=RationalBeat(0), midi_pitch=67)
        earlier_low = self.event(onset=RationalBeat(0), midi_pitch=60)
        measure = Measure(2, TimeSignature(4, 4), (later, earlier_high, earlier_low))
        self.assertEqual(measure.events, (earlier_low, earlier_high, later))


if __name__ == "__main__":
    unittest.main()
