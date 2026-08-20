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
    detect_anticipations,
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


def anticipation_measure(*, tied=False, continue_note=True):
    events = [
        event(48, 0, RationalBeat(3, 2), voice=1),
        event(52, 0, 1, voice=2),
        event(55, 0, 2, voice=3),
        event(62, RationalBeat(3, 2), RationalBeat(1, 2), voice=5),
    ]
    if tied:
        events.extend(
            (
                event(59, 1, RationalBeat(1, 2), voice=4, tie=TieState.START),
                event(59, RationalBeat(3, 2), RationalBeat(1, 2), voice=4, tie=TieState.STOP),
            )
        )
    elif continue_note:
        events.append(event(59, 1, 1, voice=4))
    else:
        events.extend(
            (
                event(59, 1, RationalBeat(1, 2), voice=4),
                event(59, RationalBeat(3, 2), RationalBeat(1, 2), voice=4),
            )
        )
    return Measure(1, TimeSignature(2, 4), tuple(events))


class AnticipationEvidenceTests(unittest.TestCase):
    def test_future_chord_tone_arrives_early_and_is_detected(self):
        observations = detect_anticipations(anticipation_measure())
        self.assertEqual(len(observations), 1)
        item = observations[0]
        self.assertEqual(item.frame_index, 1)
        self.assertEqual((item.midi_pitch, item.pitch_class), (59, 11))
        self.assertEqual((item.source_root_pc, item.arrival_root_pc), (0, 7))
        self.assertEqual(item.start, RationalBeat(1))
        self.assertEqual(item.end, RationalBeat(3, 2))

    def test_explicit_tie_chain_is_accepted(self):
        observations = detect_anticipations(anticipation_measure(tied=True))
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0].midi_pitch, 59)

    def test_unrelated_rearticulation_without_tie_is_rejected(self):
        self.assertEqual(
            detect_anticipations(anticipation_measure(continue_note=False)),
            (),
        )

    def test_same_harmony_is_not_anticipation(self):
        measure = Measure(
            1,
            TimeSignature(2, 4),
            (
                event(48, 0, 2, voice=1),
                event(55, 0, 2, voice=2),
                event(52, 0, 1, voice=3),
                event(52, 1, 1, voice=3),
            ),
        )
        self.assertEqual(detect_anticipations(measure), ())

    def test_multiple_foreign_pitch_classes_are_rejected(self):
        base = anticipation_measure()
        measure = Measure(
            1,
            TimeSignature(2, 4),
            base.events
            + (event(61, 1, RationalBeat(1, 2), voice=8),),
        )
        self.assertEqual(detect_anticipations(measure), ())

    def test_silent_gap_before_arrival_harmony_is_rejected(self):
        measure = Measure(
            1,
            TimeSignature(3, 4),
            (
                event(48, 0, RationalBeat(3, 2), voice=1),
                event(52, 0, 1, voice=2),
                event(55, 0, RationalBeat(3, 2), voice=3),
                event(59, 1, RationalBeat(1, 2), voice=4),
                event(55, 2, 1, voice=10),
                event(59, 2, 1, voice=4),
                event(62, 2, 1, voice=11),
            ),
        )
        self.assertEqual(detect_anticipations(measure), ())

    def test_detector_is_deterministic(self):
        measure = anticipation_measure()
        expected = detect_anticipations(measure)
        for _ in range(10):
            self.assertEqual(detect_anticipations(measure), expected)

    def test_detector_does_not_change_existing_decisions(self):
        measure = anticipation_measure()
        context = TonalContext(0, TonalMode.MAJOR)
        exact_before = analyze_measure_exact(measure)
        context_before = analyze_measure_in_context(measure, context)
        structural_before = segment_measure_structurally(measure)
        suspension_before = detect_suspensions(measure)
        detect_anticipations(measure)
        self.assertEqual(analyze_measure_exact(measure), exact_before)
        self.assertEqual(analyze_measure_in_context(measure, context), context_before)
        self.assertEqual(segment_measure_structurally(measure), structural_before)
        self.assertEqual(detect_suspensions(measure), suspension_before)

    def test_rejects_non_measure_input(self):
        with self.assertRaises(TypeError):
            detect_anticipations(object())


if __name__ == "__main__":
    unittest.main()
