import unittest

from st_guitar_harmonic_engine import (
    Measure,
    NoteEvent,
    OrnamentalNCTKind,
    RationalBeat,
    TimeSignature,
    TonalContext,
    TonalMode,
    analyze_measure_exact,
    analyze_measure_in_context,
    detect_anticipations,
    detect_ornamental_ncts,
    detect_suspensions,
    segment_measure_structurally,
)


def event(pitch, onset, duration, *, voice):
    return NoteEvent(
        measure_number=1,
        staff=1,
        voice=voice,
        midi_pitch=pitch,
        onset=RationalBeat(onset),
        duration=RationalBeat(duration),
    )


def appoggiatura_measure():
    return Measure(
        1,
        TimeSignature(3, 4),
        (
            event(48, 0, 3, voice=2),
            event(52, 0, 3, voice=3),
            event(55, 0, 1, voice=4),
            event(72, 0, 1, voice=1),
            event(66, 1, 1, voice=1),
            event(67, 2, 1, voice=1),
        ),
    )


def escape_measure():
    return Measure(
        1,
        TimeSignature(3, 4),
        (
            event(48, 0, 3, voice=2),
            event(52, 0, 3, voice=3),
            event(67, 0, 1, voice=1),
            event(66, 1, 1, voice=1),
            event(72, 2, 1, voice=1),
            event(55, 2, 1, voice=4),
        ),
    )


class OrnamentalNCTEvidenceTests(unittest.TestCase):
    def test_appoggiatura_leap_in_step_out_is_detected(self):
        observations = detect_ornamental_ncts(appoggiatura_measure())
        self.assertEqual(len(observations), 1)
        item = observations[0]
        self.assertEqual(item.kind, OrnamentalNCTKind.APPOGGIATURA)
        self.assertEqual((item.midi_pitch, item.pitch_class), (66, 6))
        self.assertEqual(item.approach_semitones, -6)
        self.assertEqual(item.resolution_semitones, 1)
        self.assertEqual(item.anchor_root_pc, 0)

    def test_escape_step_in_leap_out_is_detected(self):
        observations = detect_ornamental_ncts(escape_measure())
        self.assertEqual(len(observations), 1)
        item = observations[0]
        self.assertEqual(item.kind, OrnamentalNCTKind.ESCAPE)
        self.assertEqual((item.midi_pitch, item.pitch_class), (66, 6))
        self.assertEqual(item.approach_semitones, -1)
        self.assertEqual(item.resolution_semitones, 6)
        self.assertEqual(item.anchor_root_pc, 0)

    def test_same_direction_motion_is_rejected(self):
        measure = Measure(
            1,
            TimeSignature(3, 4),
            (
                event(48, 0, 3, voice=2),
                event(52, 0, 3, voice=3),
                event(55, 0, 1, voice=4),
                event(72, 0, 1, voice=1),
                event(70, 1, 1, voice=1),
                event(67, 2, 1, voice=1),
            ),
        )
        self.assertEqual(detect_ornamental_ncts(measure), ())

    def test_step_in_step_out_is_not_reclassified(self):
        measure = Measure(
            1,
            TimeSignature(3, 4),
            (
                event(48, 0, 3, voice=2),
                event(52, 0, 3, voice=3),
                event(55, 0, 1, voice=4),
                event(64, 0, 1, voice=1),
                event(66, 1, 1, voice=1),
                event(67, 2, 1, voice=1),
            ),
        )
        self.assertEqual(detect_ornamental_ncts(measure), ())

    def test_middle_exact_chord_is_not_reinterpreted_as_ornament(self):
        measure = Measure(
            1,
            TimeSignature(3, 4),
            (
                event(48, 0, 3, voice=2),
                event(52, 0, 3, voice=3),
                event(55, 0, 1, voice=4),
                event(64, 0, 1, voice=1),
                event(69, 1, 1, voice=1),
                event(67, 2, 1, voice=1),
            ),
        )
        self.assertEqual(detect_ornamental_ncts(measure), ())

    def test_changed_anchor_harmony_is_rejected(self):
        measure = Measure(
            1,
            TimeSignature(3, 4),
            (
                event(48, 0, 1, voice=2),
                event(52, 0, 1, voice=3),
                event(55, 0, 1, voice=4),
                event(72, 0, 1, voice=1),
                event(66, 1, 1, voice=1),
                event(55, 2, 1, voice=2),
                event(59, 2, 1, voice=3),
                event(62, 2, 1, voice=4),
                event(67, 2, 1, voice=1),
            ),
        )
        self.assertEqual(detect_ornamental_ncts(measure), ())

    def test_multiple_foreign_pitch_classes_are_rejected(self):
        base = appoggiatura_measure()
        measure = Measure(
            1,
            TimeSignature(3, 4),
            base.events + (event(70, 1, 1, voice=8),),
        )
        self.assertEqual(detect_ornamental_ncts(measure), ())

    def test_detector_is_deterministic(self):
        measure = appoggiatura_measure()
        expected = detect_ornamental_ncts(measure)
        for _ in range(10):
            self.assertEqual(detect_ornamental_ncts(measure), expected)

    def test_detector_does_not_change_existing_decisions(self):
        measure = appoggiatura_measure()
        context = TonalContext(0, TonalMode.MAJOR)
        exact_before = analyze_measure_exact(measure)
        context_before = analyze_measure_in_context(measure, context)
        structural_before = segment_measure_structurally(measure)
        suspension_before = detect_suspensions(measure)
        anticipation_before = detect_anticipations(measure)
        detect_ornamental_ncts(measure)
        self.assertEqual(analyze_measure_exact(measure), exact_before)
        self.assertEqual(analyze_measure_in_context(measure, context), context_before)
        self.assertEqual(segment_measure_structurally(measure), structural_before)
        self.assertEqual(detect_suspensions(measure), suspension_before)
        self.assertEqual(detect_anticipations(measure), anticipation_before)

    def test_rejects_non_measure_input(self):
        with self.assertRaises(TypeError):
            detect_ornamental_ncts(object())


if __name__ == "__main__":
    unittest.main()
