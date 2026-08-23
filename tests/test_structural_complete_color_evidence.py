import unittest

from st_guitar_harmonic_engine.abstention import FinalDecisionState, apply_abstention_policy
from st_guitar_harmonic_engine.aggregator import aggregate_frame_evidence
from st_guitar_harmonic_engine.confidence import ConfidenceState
from st_guitar_harmonic_engine.models import NoteEvent, RationalBeat, TieState
from st_guitar_harmonic_engine.frames import HarmonicFrame
from st_guitar_harmonic_engine.resolver import (
    CandidateFamily,
    EvidenceSource,
    ResolverDecision,
    ResolverStatus,
)
from st_guitar_harmonic_engine.sequence import resolve_candidates_by_precedence
from st_guitar_harmonic_engine.strength import assess_candidate_strength


def frame(*pitches):
    events = tuple(
        NoteEvent(
            measure_number=1,
            staff=1,
            voice=index + 1,
            midi_pitch=pitch,
            onset=RationalBeat(0),
            duration=RationalBeat(1),
            tie=TieState.NONE,
        )
        for index, pitch in enumerate(pitches)
    )
    return HarmonicFrame(1, RationalBeat(0), RationalBeat(1), events)


class StructuralCompleteColorEvidenceTests(unittest.TestCase):
    def test_complete_major_add9_gets_structural_plus_color_support(self):
        candidates = aggregate_frame_evidence(frame(48, 50, 52, 55))  # C D E G
        matching = tuple(
            item
            for item in candidates
            if item.identity.root_pc == 0
            and item.identity.family is CandidateFamily.EXTENSION
            and item.identity.variant == "major:natural_ninth"
        )
        self.assertEqual(len(matching), 1)
        self.assertEqual(
            matching[0].evidence,
            (EvidenceSource.STRUCTURAL, EvidenceSource.COLOR_TONE),
        )
        self.assertIs(
            assess_candidate_strength(matching[0]).state,
            ConfidenceState.BOUNDED,
        )

        decision = resolve_candidates_by_precedence(candidates)
        self.assertIs(decision.status, ResolverStatus.RESOLVED)
        self.assertEqual(decision.candidates, matching)
        gated = apply_abstention_policy(decision)
        self.assertIs(gated.state, FinalDecisionState.RESOLVED)

    def test_complete_dominant_flat_nine_gets_structural_plus_color_support(self):
        candidates = aggregate_frame_evidence(frame(48, 52, 55, 58, 61))  # C E G Bb Db
        matching = tuple(
            item
            for item in candidates
            if item.identity.root_pc == 0
            and item.identity.family is CandidateFamily.ALTERED
            and item.identity.variant == "dominant_seventh:flat_ninth"
        )
        self.assertEqual(len(matching), 1)
        self.assertEqual(
            matching[0].evidence,
            (EvidenceSource.STRUCTURAL, EvidenceSource.COLOR_TONE),
        )
        self.assertIs(
            assess_candidate_strength(matching[0]).state,
            ConfidenceState.BOUNDED,
        )

        decision = resolve_candidates_by_precedence(candidates)
        self.assertIs(decision.status, ResolverStatus.RESOLVED)
        self.assertEqual(decision.candidates, matching)
        self.assertIs(apply_abstention_policy(decision).state, FinalDecisionState.RESOLVED)

    def test_suspended_candidates_do_not_gain_structural_support(self):
        candidates = aggregate_frame_evidence(frame(48, 50, 55))  # C D G
        suspended = tuple(
            item for item in candidates if item.identity.family is CandidateFamily.SUSPENDED
        )
        self.assertTrue(suspended)
        self.assertTrue(
            all(item.evidence == (EvidenceSource.COLOR_TONE,) for item in suspended)
        )
        self.assertTrue(
            all(assess_candidate_strength(item).state is ConfidenceState.WEAK for item in suspended)
        )

    def test_incomplete_candidates_do_not_gain_structural_support(self):
        candidates = aggregate_frame_evidence(frame(48, 52))  # C E
        incomplete = tuple(
            item for item in candidates if EvidenceSource.INCOMPLETE_CHORD in item.evidence
        )
        self.assertTrue(incomplete)
        self.assertTrue(
            all(EvidenceSource.STRUCTURAL not in item.evidence for item in incomplete)
        )

    def test_exact_candidate_path_is_unchanged(self):
        candidates = aggregate_frame_evidence(frame(48, 52, 55))  # C E G
        self.assertEqual(len(candidates), 1)
        self.assertEqual(
            candidates[0].evidence,
            (EvidenceSource.EXACT, EvidenceSource.BASS_INVERSION),
        )
        decision = ResolverDecision(ResolverStatus.RESOLVED, candidates)
        self.assertIs(apply_abstention_policy(decision).state, FinalDecisionState.RESOLVED)


if __name__ == "__main__":
    unittest.main()
