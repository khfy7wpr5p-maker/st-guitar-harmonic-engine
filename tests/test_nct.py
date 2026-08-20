import unittest

from st_guitar_harmonic_engine import (
    ChordQuality,
    Measure,
    NCTKind,
    NoteEvent,
    RationalBeat,
    TimeSignature,
    detect_stepwise_ncts,
)


def event(pitch, onset, duration, *, voice, staff=1):
    return NoteEvent(
        measure_number=1,
        staff=staff,
        voice=voice,
        midi_pitch=pitch,
        onset=RationalBeat(onset),
        duration=RationalBeat(duration),
    )


def c_major_with_melody(first, middle, last, *, extra_middle=None):
    events = [
        event(48, 0, 3, voice=2),
        event(52, 0, 3, voice=3),
        event(55, 0, 3, voice=4),
        event(first, 0, 1, voice=1),
        event(middle, 1, 1, voice=1),
        event(last, 2, 1, voice=1),
    ]
    if extra_middle is not None:
        events.append(event(extra_middle, 1, 1, voice=5))
    return Measure(1, TimeSignature(3, 4), tuple(events))


class StepwiseNCTTests(unittest.TestCase):
    def test_ascending_passing_tone(self):
        observations = detect_stepwise_ncts(c_major_with_melody(60, 62, 64))
        self.assertEqual(len(observations), 1)
        obs = observations[0]
        self.assertEqual(obs.kind, NCTKind.PASSING)
        self.assertEqual((obs.midi_pitch, obs.pitch_class), (62, 2))
        self.assertEqual((obs.anchor_root_pc, obs.anchor_quality), (0, ChordQuality.MAJOR))

    def test_descending_passing_tone(self):
        observations = detect_stepwise_ncts(c_major_with_melody(64, 62, 60))
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0].kind, NCTKind.PASSING)

    def test_upper_neighbor_tone(self):
        observations = detect_stepwise_ncts(c_major_with_melody(64, 65, 64))
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0].kind, NCTKind.NEIGHBOR)

    def test_lower_neighbor_tone(self):
        observations = detect_stepwise_ncts(c_major_with_melody(67, 65, 67))
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0].kind, NCTKind.NEIGHBOR)

    def test_leap_is_not_classified_as_nct(self):
        self.assertEqual(detect_stepwise_ncts(c_major_with_melody(60, 65, 64)), ())

    def test_two_extra_pitch_classes_are_not_guessed(self):
        measure = c_major_with_melody(60, 62, 64, extra_middle=65)
        self.assertEqual(detect_stepwise_ncts(measure), ())

    def test_changing_anchor_harmony_is_not_classified(self):
        measure = Measure(
            1,
            TimeSignature(3, 4),
            (
                event(48, 0, 2, voice=2),
                event(52, 0, 2, voice=3),
                event(55, 0, 2, voice=4),
                event(60, 0, 1, voice=1),
                event(62, 1, 1, voice=1),
                event(43, 2, 1, voice=2),
                event(47, 2, 1, voice=3),
                event(50, 2, 1, voice=4),
                event(67, 2, 1, voice=1),
            ),
        )
        self.assertEqual(detect_stepwise_ncts(measure), ())

    def test_short_measure_without_three_frames_has_no_nct(self):
        measure = Measure(
            1,
            TimeSignature(2, 4),
            (
                event(48, 0, 2, voice=2),
                event(52, 0, 2, voice=3),
                event(55, 0, 2, voice=4),
            ),
        )
        self.assertEqual(detect_stepwise_ncts(measure), ())

    def test_rejects_non_measure_input(self):
        with self.assertRaises(TypeError):
            detect_stepwise_ncts(object())


if __name__ == "__main__":
    unittest.main()
