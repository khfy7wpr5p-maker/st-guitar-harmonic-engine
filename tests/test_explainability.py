import unittest

from st_guitar_harmonic_engine import (
    AnalysisStatus,
    ChordQuality,
    Measure,
    NCTKind,
    NoteEvent,
    RationalBeat,
    ResolutionStatus,
    TimeSignature,
    TonalContext,
    TonalMode,
    analyze_measure_exact,
    analyze_measure_in_context,
    build_measure_explainability,
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


def c_major_with_passing_tone():
    return Measure(
        1,
        TimeSignature(3, 4),
        (
            event(48, 0, 3, voice=2),
            event(52, 0, 3, voice=3),
            event(55, 0, 3, voice=4),
            event(60, 0, 1, voice=1),
            event(62, 1, 1, voice=1),
            event(64, 2, 1, voice=1),
        ),
    )


def sustained_measure(*pitches):
    return Measure(
        1,
        TimeSignature(4, 4),
        tuple(
            event(pitch, 0, 4, voice=index + 1)
            for index, pitch in enumerate(pitches)
        ),
    )


class ExplainabilityTests(unittest.TestCase):
    def test_passing_tone_is_attached_only_to_middle_frame(self):
        report = build_measure_explainability(c_major_with_passing_tone())
        self.assertEqual(len(report.frames), 3)
        self.assertEqual(report.frames[0].ncts, ())
        self.assertEqual(len(report.frames[1].ncts), 1)
        self.assertEqual(report.frames[1].ncts[0].kind, NCTKind.PASSING)
        self.assertEqual(report.frames[1].ncts[0].midi_pitch, 62)
        self.assertEqual(report.frames[2].ncts, ())

    def test_missing_fifth_is_exposed_as_explainability_evidence(self):
        report = build_measure_explainability(sustained_measure(48, 52))
        self.assertEqual(len(report.frames), 1)
        omissions = report.frames[0].omissions
        self.assertEqual(len(omissions), 1)
        self.assertEqual((omissions[0].root_pc, omissions[0].quality), (0, ChordQuality.MAJOR))
        self.assertEqual(omissions[0].omitted_pc, 7)

    def test_exact_chord_does_not_emit_omission_evidence(self):
        report = build_measure_explainability(sustained_measure(48, 52, 55))
        self.assertEqual(report.frames[0].omissions, ())

    def test_empty_measure_returns_empty_evidence_report(self):
        report = build_measure_explainability(Measure(1, TimeSignature(4, 4), ()))
        self.assertEqual(report.measure_number, 1)
        self.assertEqual(report.frames, ())

    def test_exact_decision_is_identical_before_and_after_explainability(self):
        measure = c_major_with_passing_tone()
        before = analyze_measure_exact(measure)
        report = build_measure_explainability(measure)
        after = analyze_measure_exact(measure)
        self.assertEqual(before, after)
        self.assertEqual(
            tuple(item.status for item in before),
            (AnalysisStatus.UNIQUE, AnalysisStatus.NO_MATCH, AnalysisStatus.UNIQUE),
        )
        self.assertEqual(len(report.frames[1].ncts), 1)

    def test_context_decision_is_identical_before_and_after_explainability(self):
        measure = sustained_measure(48, 52, 55)
        context = TonalContext(0, TonalMode.MAJOR)
        before = analyze_measure_in_context(measure, context)
        build_measure_explainability(measure)
        after = analyze_measure_in_context(measure, context)
        self.assertEqual(before, after)
        self.assertEqual(before[0].status, ResolutionStatus.RESOLVED)

    def test_report_is_deterministic(self):
        measure = c_major_with_passing_tone()
        self.assertEqual(
            build_measure_explainability(measure),
            build_measure_explainability(measure),
        )

    def test_rejects_non_measure_input(self):
        with self.assertRaises(TypeError):
            build_measure_explainability(object())


if __name__ == "__main__":
    unittest.main()
