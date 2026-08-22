import unittest

from st_guitar_harmonic_engine import (
    AnalysisStatus,
    CandidateFamily,
    ChordQuality,
    EvidenceSource,
    HarmonicFrame,
    HarmonicIdentity,
    Inversion,
    NoteEvent,
    OmissionKind,
    PitchStep,
    RationalBeat,
    ResolverCandidate,
    ResolverDecision,
    ResolverStatus,
    WrittenPitch,
    analyze_frame_exact,
    generate_incomplete_chord_candidates,
    resolve_candidates_by_precedence,
)
from st_guitar_harmonic_engine.abstention import (
    AbstentionReason,
    FinalDecisionState,
    apply_abstention_policy,
)


def frame(*pitches, written=None):
    written = written or {}
    events = tuple(
        NoteEvent(
            measure_number=1,
            staff=1,
            voice=index + 1,
            midi_pitch=pitch,
            onset=RationalBeat(0),
            duration=RationalBeat(1),
            written_pitch=written.get(index),
        )
        for index, pitch in enumerate(pitches)
    )
    return HarmonicFrame(1, RationalBeat(0), RationalBeat(1), events)


def candidate(root, family, variant, *evidence):
    return ResolverCandidate(
        HarmonicIdentity(root, family, variant),
        tuple(evidence),
    )


class GuitarCoreRegressionTests(unittest.TestCase):
    def test_exact_guitar_harmony_and_inversion_matrix(self):
        cases = (
            ((48, 52, 55), 0, ChordQuality.MAJOR, Inversion.ROOT_POSITION),
            ((45, 48, 52), 9, ChordQuality.MINOR, Inversion.ROOT_POSITION),
            ((48, 52, 55, 58), 0, ChordQuality.DOMINANT_SEVENTH, Inversion.ROOT_POSITION),
            ((52, 55, 60), 0, ChordQuality.MAJOR, Inversion.FIRST),
            ((55, 60, 64), 0, ChordQuality.MAJOR, Inversion.SECOND),
        )
        for pitches, root, quality, inversion in cases:
            with self.subTest(pitches=pitches):
                result = analyze_frame_exact(frame(*pitches))
                self.assertIs(result.status, AnalysisStatus.UNIQUE)
                self.assertEqual(result.candidates[0].candidate.root_pc, root)
                self.assertIs(result.candidates[0].candidate.quality, quality)
                self.assertIs(result.candidates[0].bass.inversion, inversion)

    def test_octave_duplicates_do_not_change_exact_identity(self):
        simple = analyze_frame_exact(frame(48, 52, 55))
        doubled = analyze_frame_exact(frame(48, 52, 55, 60, 64, 67))
        self.assertIs(simple.status, AnalysisStatus.UNIQUE)
        self.assertIs(doubled.status, AnalysisStatus.UNIQUE)
        self.assertEqual(simple.candidates[0].candidate, doubled.candidates[0].candidate)

    def test_enharmonic_spelling_preserves_same_harmonic_result(self):
        sharp = frame(
            50, 54, 57,
            written={
                0: WrittenPitch(PitchStep.D, 0, 3),
                1: WrittenPitch(PitchStep.F, 1, 3),
                2: WrittenPitch(PitchStep.A, 0, 3),
            },
        )
        flat = frame(
            50, 54, 57,
            written={
                0: WrittenPitch(PitchStep.D, 0, 3),
                1: WrittenPitch(PitchStep.G, -1, 3),
                2: WrittenPitch(PitchStep.A, 0, 3),
            },
        )
        self.assertEqual(analyze_frame_exact(sharp), analyze_frame_exact(flat))

    def test_missing_root_third_and_fifth_are_evidence_not_authority(self):
        missing_root = generate_incomplete_chord_candidates(frame(52, 55))
        self.assertTrue(any(
            item.root_pc == 0 and item.quality is ChordQuality.MAJOR
            and item.omission is OmissionKind.ROOT
            for item in missing_root
        ))

        missing_third = generate_incomplete_chord_candidates(frame(48, 55))
        c_interpretations = {
            (item.quality, item.omission)
            for item in missing_third if item.root_pc == 0
        }
        self.assertIn((ChordQuality.MAJOR, OmissionKind.THIRD), c_interpretations)
        self.assertIn((ChordQuality.MINOR, OmissionKind.THIRD), c_interpretations)

        missing_fifth = generate_incomplete_chord_candidates(frame(48, 52))
        self.assertTrue(any(
            item.root_pc == 0 and item.quality is ChordQuality.MAJOR
            and item.omission is OmissionKind.FIFTH
            for item in missing_fifth
        ))

    def test_exact_triad_suppresses_missing_seventh_reinterpretation(self):
        self.assertEqual(generate_incomplete_chord_candidates(frame(48, 52, 55)), ())

    def test_incomplete_dominant_seventh_alone_abstains(self):
        incomplete = candidate(
            0,
            CandidateFamily.BASIC,
            ChordQuality.DOMINANT_SEVENTH.value,
            EvidenceSource.INCOMPLETE_CHORD,
        )
        source = ResolverDecision(ResolverStatus.RESOLVED, (incomplete,))
        gated = apply_abstention_policy(source)
        self.assertIs(gated.state, FinalDecisionState.ABSTAIN)
        self.assertIs(gated.abstention_reason, AbstentionReason.WEAK_EVIDENCE)

    def test_exact_validated_candidate_outranks_rootless_omission_hypothesis(self):
        exact = candidate(
            4,
            CandidateFamily.BASIC,
            ChordQuality.DIMINISHED.value,
            EvidenceSource.EXACT,
        )
        omission = candidate(
            0,
            CandidateFamily.BASIC,
            ChordQuality.DOMINANT_SEVENTH.value,
            EvidenceSource.BASS_INVERSION,
            EvidenceSource.INCOMPLETE_CHORD,
        )
        result = resolve_candidates_by_precedence((omission, exact))
        self.assertIs(result.status, ResolverStatus.RESOLVED)
        self.assertEqual(result.candidates, (exact,))

    def test_repeated_runs_are_equal(self):
        target = frame(48, 52, 55, 60, 64, 67)
        expected = analyze_frame_exact(target)
        for _ in range(20):
            self.assertEqual(analyze_frame_exact(target), expected)


if __name__ == "__main__":
    unittest.main()
