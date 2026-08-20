import unittest

from st_guitar_harmonic_engine import (
    Measure,
    NoteEvent,
    RationalBeat,
    TieState,
    TimeSignature,
    TonalContext,
    TonalMode,
    analyze_measure_exact,
    analyze_measure_in_context,
    detect_suspensions,
    segment_measure_structurally,
)


def beat(value):
    return value if isinstance(value, RationalBeat) else RationalBeat(value)


def event(pitch, onset, duration, *, voice, tie=TieState.NONE):
    return NoteEvent(
        measure_number=1,
        staff=1,
        voice=voice,
        midi_pitch=pitch,
        onset=beat(onset),
        duration=beat(duration),
        tie=tie,
    )


def suspension_measure(*, resolution_pitch=59, prepared=True):
    events = [
        event(48, 0, 1, voice=2),
        event(52, 0, 1, voice=3),
        event(55, 0, 2, voice=4),
        event(62, 1, 1, voice=5),
        event(resolution_pitch, RationalBeat(3, 2), RationalBeat(1, 2), voice=1),
    ]
    if prepared:
        events.append(event(60, 0, RationalBeat(3, 2), voice=1))
    else:
        events.append(event(60, 1, RationalBeat(1, 2), voice=1))
    return Measure(1, TimeSignature(2, 4), tuple(events))


def explicit_tie_suspension_measure():
    return Measure(
        1,
        TimeSignature(2, 4),
        (
            event(48, 0, 1, voice=2),
            event(52, 0, 1, voice=3),
            event(55, 0, 2, voice=4),
            event(60, 0, 1, voice=1, tie=TieState.START),
            event(60, 1, RationalBeat(1, 2), voice=1, tie=TieState.STOP),
            event(62, 1, 1, voice=5),
            event(59, RationalBeat(3, 2), RationalBeat(1, 2), voice=1),
        ),
    )


class SuspensionEvidenceTests(unittest.TestCase):
    def test_prepared_four_three_like_suspension_is_detected(self):
        observations = detect_suspensions(suspension_measure())
        self.assertEqual(len(observations), 1)
        item = observations[0]
        self.assertEqual(item.frame_index, 1)
        self.assertEqual((item.midi_pitch, item.pitch_class), (60, 0))
        self.assertEqual((item.resolution_midi_pitch, item.resolution_pitch_class), (59, 11))
        self.assertEqual((item.preparation_root_pc, item.resolution_root_pc), (0, 7))
        self.assertEqual(item.start, RationalBeat(1))
        self.assertEqual(item.end, RationalBeat(3, 2))

    def test_explicit_tie_chain_is_accepted(self):
        observations = detect_suspensions(explicit_tie_suspension_measure())
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0].midi_pitch, 60)

    def test_unprepared_foreign_tone_is_rejected(self):
        self.assertEqual(detect_suspensions(suspension_measure(prepared=False)), ())

    def test_large_downward_resolution_is_rejected(self):
        # B2 has the target B pitch class but is a 13-semitone leap from C4.
        self.assertEqual(detect_suspensions(suspension_measure(resolution_pitch=47)), ())

    def test_upward_resolution_is_rejected(self):
        # B5 preserves the target pitch class but moves upward from the suspended C4.
        self.assertEqual(detect_suspensions(suspension_measure(resolution_pitch=71)), ())

    def test_ambiguous_resolution_anchor_is_rejected(self):
        measure = Measure(
            1,
            TimeSignature(2, 4),
            (
                event(48, 0, 1, voice=2),
                event(52, 0, 1, voice=3),
                event(55, 0, 1, voice=4),
                event(60, 0, RationalBeat(3, 2), voice=1),
                event(51, 1, 1, voice=5),
                event(54, 1, 1, voice=6),
                event(57, 1, 1, voice=7),
                event(48, RationalBeat(3, 2), RationalBeat(1, 2), voice=1),
            ),
        )
        self.assertEqual(detect_suspensions(measure), ())

    def test_detector_is_deterministic(self):
        measure = suspension_measure()
        expected = detect_suspensions(measure)
        for _ in range(10):
            self.assertEqual(detect_suspensions(measure), expected)

    def test_detector_does_not_change_existing_decisions(self):
        measure = suspension_measure()
        context = TonalContext(0, TonalMode.MAJOR)
        exact_before = analyze_measure_exact(measure)
        context_before = analyze_measure_in_context(measure, context)
        structural_before = segment_measure_structurally(measure)
        detect_suspensions(measure)
        self.assertEqual(analyze_measure_exact(measure), exact_before)
        self.assertEqual(analyze_measure_in_context(measure, context), context_before)
        self.assertEqual(segment_measure_structurally(measure), structural_before)

    def test_rejects_non_measure_input(self):
        with self.assertRaises(TypeError):
            detect_suspensions(object())


if __name__ == "__main__":
    unittest.main()
