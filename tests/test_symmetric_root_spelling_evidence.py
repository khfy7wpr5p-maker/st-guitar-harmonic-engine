import unittest

from st_guitar_harmonic_engine.abstention import FinalDecisionState, apply_abstention_policy
from st_guitar_harmonic_engine.aggregator import aggregate_frame_evidence
from st_guitar_harmonic_engine.frames import HarmonicFrame
from st_guitar_harmonic_engine.models import NoteEvent, RationalBeat, TieState
from st_guitar_harmonic_engine.resolver import (
    CandidateFamily,
    EvidenceSource,
    HarmonicIdentity,
    ResolverCandidate,
    ResolverStatus,
)
from st_guitar_harmonic_engine.sequence import resolve_candidates_by_precedence
from st_guitar_harmonic_engine.spelling import PitchStep, WrittenPitch
from st_guitar_harmonic_engine.spelling_resolution import (
    select_spelling_supported_symmetric_candidate,
    written_pitch_class,
)
from st_guitar_harmonic_engine.analysis import analyze_frame_exact


def event(voice, midi, step=None, alter=0, octave=3):
    written = None if step is None else WrittenPitch(step, alter, octave)
    return NoteEvent(
        measure_number=1,
        staff=1,
        voice=voice,
        midi_pitch=midi,
        onset=RationalBeat(0),
        duration=RationalBeat(1),
        tie=TieState.NONE,
        written_pitch=written,
    )


def frame(*events):
    return HarmonicFrame(1, RationalBeat(0), RationalBeat(1), tuple(events))


class SymmetricRootSpellingEvidenceTests(unittest.TestCase):
    def test_written_pitch_class_supports_double_accidentals(self):
        self.assertEqual(written_pitch_class(WrittenPitch(PitchStep.B, -2, 3)), 9)
        self.assertEqual(written_pitch_class(WrittenPitch(PitchStep.F, 2, 4)), 7)

    def test_d_augmented_written_stack_selects_d_root(self):
        target = frame(
            event(1, 50, PitchStep.D, 0, 3),
            event(2, 54, PitchStep.F, 1, 3),
            event(3, 58, PitchStep.A, 1, 3),
        )
        exact = analyze_frame_exact(target)
        self.assertEqual(len(exact.candidates), 3)
        selected = select_spelling_supported_symmetric_candidate(
            target,
            tuple(item.candidate for item in exact.candidates),
        )
        self.assertIsNotNone(selected)
        self.assertEqual(selected.root_pc, 2)

        candidates = aggregate_frame_evidence(target)
        structurally_supported = tuple(
            item for item in candidates if EvidenceSource.STRUCTURAL in item.evidence
        )
        self.assertEqual(len(structurally_supported), 1)
        self.assertEqual(structurally_supported[0].identity.root_pc, 2)
        decision = resolve_candidates_by_precedence(candidates)
        self.assertIs(decision.status, ResolverStatus.RESOLVED)
        self.assertEqual(decision.candidates[0].identity.root_pc, 2)
        self.assertIs(apply_abstention_policy(decision).state, FinalDecisionState.RESOLVED)

    def test_d_sharp_diminished_seventh_written_stack_selects_d_sharp_root(self):
        target = frame(
            event(1, 51, PitchStep.D, 1, 3),
            event(2, 54, PitchStep.F, 1, 3),
            event(3, 57, PitchStep.A, 0, 3),
            event(4, 60, PitchStep.C, 0, 4),
        )
        exact = analyze_frame_exact(target)
        self.assertEqual(len(exact.candidates), 4)
        selected = select_spelling_supported_symmetric_candidate(
            target,
            tuple(item.candidate for item in exact.candidates),
        )
        self.assertIsNotNone(selected)
        self.assertEqual(selected.root_pc, 3)

        candidates = aggregate_frame_evidence(target)
        decision = resolve_candidates_by_precedence(candidates)
        self.assertIs(decision.status, ResolverStatus.RESOLVED)
        self.assertEqual(decision.candidates[0].identity.root_pc, 3)

    def test_missing_written_spelling_preserves_augmented_ambiguity(self):
        target = frame(event(1, 50), event(2, 54), event(3, 58))
        candidates = aggregate_frame_evidence(target)
        self.assertFalse(any(EvidenceSource.STRUCTURAL in item.evidence for item in candidates))
        decision = resolve_candidates_by_precedence(candidates)
        self.assertIs(decision.status, ResolverStatus.AMBIGUOUS)
        self.assertEqual(len(decision.candidates), 3)

    def test_partial_written_spelling_fails_closed(self):
        target = frame(
            event(1, 50, PitchStep.D, 0, 3),
            event(2, 54, PitchStep.F, 1, 3),
            event(3, 58),
        )
        candidates = aggregate_frame_evidence(target)
        self.assertFalse(any(EvidenceSource.STRUCTURAL in item.evidence for item in candidates))
        self.assertIs(
            resolve_candidates_by_precedence(candidates).status,
            ResolverStatus.AMBIGUOUS,
        )

    def test_pitch_class_inconsistent_written_spelling_fails_closed(self):
        target = frame(
            event(1, 50, PitchStep.E, -1, 3),  # written Eb != sounding D pitch class
            event(2, 54, PitchStep.F, 1, 3),
            event(3, 58, PitchStep.A, 1, 3),
        )
        candidates = aggregate_frame_evidence(target)
        self.assertFalse(any(EvidenceSource.STRUCTURAL in item.evidence for item in candidates))
        self.assertIs(
            resolve_candidates_by_precedence(candidates).status,
            ResolverStatus.AMBIGUOUS,
        )

    def test_conflicting_enharmonic_duplicate_spelling_fails_closed(self):
        target = frame(
            event(1, 50, PitchStep.D, 0, 3),
            event(2, 50, PitchStep.E, -2, 3),
            event(3, 54, PitchStep.F, 1, 3),
            event(4, 58, PitchStep.A, 1, 3),
        )
        candidates = aggregate_frame_evidence(target)
        self.assertFalse(any(EvidenceSource.STRUCTURAL in item.evidence for item in candidates))
        self.assertIs(
            resolve_candidates_by_precedence(candidates).status,
            ResolverStatus.AMBIGUOUS,
        )

    def test_non_symmetric_exact_chord_does_not_gain_structural_spelling_evidence(self):
        target = frame(
            event(1, 48, PitchStep.C, 0, 3),
            event(2, 52, PitchStep.E, 0, 3),
            event(3, 55, PitchStep.G, 0, 3),
        )
        candidates = aggregate_frame_evidence(target)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(
            candidates[0].evidence,
            (EvidenceSource.EXACT, EvidenceSource.BASS_INVERSION),
        )

    def test_arbitrary_non_symmetric_exact_structural_marker_cannot_break_tie(self):
        left = ResolverCandidate(
            HarmonicIdentity(0, CandidateFamily.BASIC, "major"),
            (EvidenceSource.EXACT, EvidenceSource.STRUCTURAL),
        )
        right = ResolverCandidate(
            HarmonicIdentity(9, CandidateFamily.BASIC, "minor"),
            (EvidenceSource.EXACT,),
        )
        decision = resolve_candidates_by_precedence((left, right))
        self.assertIs(decision.status, ResolverStatus.AMBIGUOUS)
        self.assertEqual(set(decision.candidates), {left, right})

    def test_tonal_and_structural_conflict_preserves_exact_ambiguity(self):
        tonal = ResolverCandidate(
            HarmonicIdentity(6, CandidateFamily.BASIC, "augmented"),
            (EvidenceSource.EXACT, EvidenceSource.TONAL_CONTEXT),
        )
        spelled = ResolverCandidate(
            HarmonicIdentity(2, CandidateFamily.BASIC, "augmented"),
            (EvidenceSource.EXACT, EvidenceSource.STRUCTURAL),
        )
        third = ResolverCandidate(
            HarmonicIdentity(10, CandidateFamily.BASIC, "augmented"),
            (EvidenceSource.EXACT,),
        )
        decision = resolve_candidates_by_precedence((tonal, spelled, third))
        self.assertIs(decision.status, ResolverStatus.AMBIGUOUS)
        self.assertEqual(len(decision.candidates), 3)

    def test_repeated_spelling_resolution_is_deterministic(self):
        target = frame(
            event(1, 50, PitchStep.D, 0, 3),
            event(2, 54, PitchStep.F, 1, 3),
            event(3, 58, PitchStep.A, 1, 3),
        )
        expected = aggregate_frame_evidence(target)
        for _ in range(10):
            self.assertEqual(aggregate_frame_evidence(target), expected)
            self.assertEqual(
                resolve_candidates_by_precedence(aggregate_frame_evidence(target)),
                resolve_candidates_by_precedence(expected),
            )


if __name__ == "__main__":
    unittest.main()
