import unittest

from st_guitar_harmonic_engine.abstention import (
    AbstentionReason,
    FinalDecisionState,
    apply_abstention_policy,
)
from st_guitar_harmonic_engine.confidence import ConfidenceState
from st_guitar_harmonic_engine.resolver import (
    CandidateFamily,
    EvidenceSource,
    HarmonicIdentity,
    ResolverCandidate,
    ResolverDecision,
    ResolverStatus,
)


def candidate(*evidence):
    return ResolverCandidate(
        HarmonicIdentity(0, CandidateFamily.BASIC, "major"),
        tuple(evidence),
    )


class AbstentionPolicyTests(unittest.TestCase):
    def test_exact_resolved_candidate_passes_gate(self):
        decision = ResolverDecision(ResolverStatus.RESOLVED, (candidate(EvidenceSource.EXACT),))
        result = apply_abstention_policy(decision)
        self.assertIs(result.state, FinalDecisionState.RESOLVED)
        self.assertIs(result.confidence.state, ConfidenceState.STRONG)
        self.assertIsNone(result.abstention_reason)

    def test_bounded_candidate_passes_gate(self):
        decision = ResolverDecision(
            ResolverStatus.RESOLVED,
            (candidate(EvidenceSource.TONAL_CONTEXT),),
        )
        result = apply_abstention_policy(decision)
        self.assertIs(result.state, FinalDecisionState.RESOLVED)
        self.assertIs(result.confidence.state, ConfidenceState.BOUNDED)

    def test_bass_inversion_only_candidate_abstains_instead_of_creating_identity(self):
        decision = ResolverDecision(
            ResolverStatus.RESOLVED,
            (candidate(EvidenceSource.BASS_INVERSION),),
        )
        result = apply_abstention_policy(decision)
        self.assertIs(result.state, FinalDecisionState.ABSTAIN)
        self.assertIs(result.abstention_reason, AbstentionReason.WEAK_EVIDENCE)
        self.assertIs(result.confidence.state, ConfidenceState.WEAK)
        self.assertEqual(result.source_decision, decision)

    def test_weak_single_candidate_abstains_instead_of_false_certainty(self):
        decision = ResolverDecision(
            ResolverStatus.RESOLVED,
            (candidate(EvidenceSource.INCOMPLETE_CHORD),),
        )
        result = apply_abstention_policy(decision)
        self.assertIs(result.state, FinalDecisionState.ABSTAIN)
        self.assertIs(result.abstention_reason, AbstentionReason.WEAK_EVIDENCE)
        self.assertIs(result.confidence.state, ConfidenceState.WEAK)
        self.assertEqual(result.source_decision, decision)

    def test_candidate_without_evidence_abstains_as_insufficient(self):
        decision = ResolverDecision(ResolverStatus.RESOLVED, (candidate(),))
        result = apply_abstention_policy(decision)
        self.assertIs(result.state, FinalDecisionState.ABSTAIN)
        self.assertIs(result.abstention_reason, AbstentionReason.INSUFFICIENT_EVIDENCE)
        self.assertIs(result.confidence.state, ConfidenceState.INSUFFICIENT)

    def test_ambiguity_is_preserved_and_never_forced_to_one_candidate(self):
        left = candidate(EvidenceSource.EXACT)
        right = ResolverCandidate(
            HarmonicIdentity(3, CandidateFamily.BASIC, "major"),
            (EvidenceSource.EXACT,),
        )
        decision = ResolverDecision(ResolverStatus.AMBIGUOUS, (left, right))
        result = apply_abstention_policy(decision)
        self.assertIs(result.state, FinalDecisionState.AMBIGUOUS)
        self.assertEqual(result.source_decision.candidates, (left, right))
        self.assertIsNone(result.confidence)

    def test_no_match_remains_no_match_not_abstain(self):
        decision = ResolverDecision(ResolverStatus.NO_MATCH, ())
        result = apply_abstention_policy(decision)
        self.assertIs(result.state, FinalDecisionState.NO_MATCH)
        self.assertIsNone(result.abstention_reason)

    def test_repeated_runs_are_equal(self):
        decision = ResolverDecision(
            ResolverStatus.RESOLVED,
            (candidate(EvidenceSource.INCOMPLETE_CHORD),),
        )
        expected = apply_abstention_policy(decision)
        for _ in range(10):
            self.assertEqual(apply_abstention_policy(decision), expected)

    def test_invalid_input_is_rejected(self):
        with self.assertRaises(TypeError):
            apply_abstention_policy(object())


if __name__ == "__main__":
    unittest.main()
