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
    detect_ornamental_ncts,
    detect_pedals,
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


def add_triad(events, pitches, onset, *, voice_base):
    for offset, pitch in enumerate(pitches):
        events.append(event(pitch, onset, 1, voice=voice_base + offset))


def pedal_measure():
    events = [event(60, 0, 3, voice=1)]
    add_triad(events, (48, 52, 55), 0, voice_base=2)   # C major: pedal C is structural.
    add_triad(events, (55, 59, 62), 1, voice_base=5)   # G major: pedal C is foreign.
    add_triad(events, (53, 57, 60), 2, voice_base=8)   # F major: pedal C is structural.
    return Measure(1, TimeSignature(3, 4), tuple(events))


def repeated_harmony_measure():
    events = [event(60, 0, 3, voice=1)]
    for onset, base in ((0, 2), (1, 5), (2, 8)):
        add_triad(events, (48, 52, 55), onset, voice_base=base)
    return Measure(1, TimeSignature(3, 4), tuple(events))


def all_chord_tone_measure():
    events = [event(60, 0, 3, voice=1)]
    add_triad(events, (48, 52, 55), 0, voice_base=2)   # C major
    add_triad(events, (53, 57, 60), 1, voice_base=5)   # F major
    add_triad(events, (57, 60, 64), 2, voice_base=8)   # A minor
    return Measure(1, TimeSignature(3, 4), tuple(events))


def all_foreign_measure():
    events = [event(60, 0, 3, voice=1)]
    add_triad(events, (55, 59, 62), 0, voice_base=2)   # G major
    add_triad(events, (50, 54, 57), 1, voice_base=5)   # D major
    add_triad(events, (52, 56, 59), 2, voice_base=8)   # E major
    return Measure(1, TimeSignature(3, 4), tuple(events))


class PedalEvidenceTests(unittest.TestCase):
    def test_sustained_pedal_with_changing_underlying_harmony_is_detected(self):
        observations = detect_pedals(pedal_measure())
        self.assertEqual(len(observations), 1)
        item = observations[0]
        self.assertEqual((item.first_frame_index, item.last_frame_index), (0, 2))
        self.assertEqual((item.start, item.end), (RationalBeat(0), RationalBeat(3)))
        self.assertEqual((item.staff, item.voice), (1, 1))
        self.assertEqual((item.midi_pitch, item.pitch_class), (60, 0))
        self.assertEqual(
            tuple((frame.root_pc, frame.quality.value) for frame in item.frames),
            ((0, "major"), (7, "major"), (5, "major")),
        )
        self.assertEqual(
            tuple(frame.pedal_is_chord_tone for frame in item.frames),
            (True, False, True),
        )

    def test_two_frames_are_insufficient(self):
        measure = Measure(
            1,
            TimeSignature(2, 4),
            (
                event(60, 0, 2, voice=1),
                event(48, 0, 1, voice=2),
                event(52, 0, 1, voice=3),
                event(55, 0, 1, voice=4),
                event(55, 1, 1, voice=5),
                event(59, 1, 1, voice=6),
                event(62, 1, 1, voice=7),
            ),
        )
        self.assertEqual(detect_pedals(measure), ())

    def test_unchanged_underlying_harmony_is_rejected(self):
        self.assertEqual(detect_pedals(repeated_harmony_measure()), ())

    def test_common_chord_tone_across_all_harmonies_is_not_pedal_evidence(self):
        self.assertEqual(detect_pedals(all_chord_tone_measure()), ())

    def test_pitch_foreign_to_every_harmony_is_too_weak_to_classify(self):
        self.assertEqual(detect_pedals(all_foreign_measure()), ())

    def test_rearticulated_or_tied_chain_is_not_combined_into_one_pedal(self):
        events = [
            event(60, 0, 1, voice=1, tie=TieState.START),
            event(60, 1, 1, voice=1, tie=TieState.CONTINUE),
            event(60, 2, 1, voice=1, tie=TieState.STOP),
        ]
        add_triad(events, (48, 52, 55), 0, voice_base=2)
        add_triad(events, (55, 59, 62), 1, voice_base=5)
        add_triad(events, (53, 57, 60), 2, voice_base=8)
        measure = Measure(1, TimeSignature(3, 4), tuple(events))
        self.assertEqual(detect_pedals(measure), ())

    def test_ambiguous_reduced_frame_rejects_entire_candidate(self):
        events = [event(61, 0, 3, voice=1)]
        # Diminished seventh is intentionally symmetric/ambiguous in exact analysis.
        for offset, pitch in enumerate((48, 51, 54, 57)):
            events.append(event(pitch, 0, 1, voice=2 + offset))
        add_triad(events, (55, 59, 62), 1, voice_base=6)
        add_triad(events, (53, 57, 60), 2, voice_base=9)
        measure = Measure(1, TimeSignature(3, 4), tuple(events))
        self.assertEqual(detect_pedals(measure), ())

    def test_detector_is_deterministic(self):
        measure = pedal_measure()
        expected = detect_pedals(measure)
        for _ in range(10):
            self.assertEqual(detect_pedals(measure), expected)

    def test_detector_does_not_change_existing_decisions_or_evidence(self):
        measure = pedal_measure()
        context = TonalContext(0, TonalMode.MAJOR)
        exact_before = analyze_measure_exact(measure)
        context_before = analyze_measure_in_context(measure, context)
        structural_before = segment_measure_structurally(measure)
        suspension_before = detect_suspensions(measure)
        anticipation_before = detect_anticipations(measure)
        ornamental_before = detect_ornamental_ncts(measure)

        detect_pedals(measure)

        self.assertEqual(analyze_measure_exact(measure), exact_before)
        self.assertEqual(analyze_measure_in_context(measure, context), context_before)
        self.assertEqual(segment_measure_structurally(measure), structural_before)
        self.assertEqual(detect_suspensions(measure), suspension_before)
        self.assertEqual(detect_anticipations(measure), anticipation_before)
        self.assertEqual(detect_ornamental_ncts(measure), ornamental_before)

    def test_rejects_non_measure_input(self):
        with self.assertRaises(TypeError):
            detect_pedals(object())


if __name__ == "__main__":
    unittest.main()
