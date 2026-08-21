import unittest

from st_guitar_harmonic_engine.ambiguity import (
    AmbiguityReason,
    assess_ambiguity,
)
from st_guitar_harmonic_engine.resolver import (
    CandidateFamily,
    EvidenceSource,
    HarmonicIdentity,
    ResolverCandidate,
    ResolverDecision,
    ResolverStatus,
)


def candidate(root, *evidence):
    return ResolverCandidate(
        HarmonicIdentity(root, CandidateFamily.BASIC, "major"),
        tuple(evidence),
    )


class AmbiguityGateTests(unittest.TestCase):
    def test_exact_conflict_is_preserved(self):
        left = candidate(0, EvidenceSource.EXACT)
        right = candidate(3, EvidenceSource.EXACT)
        decision = ResolverDecision(ResolverStatus.AMBIGUOUS, (left, right))
        result = assess_ambiguity((right, left), decision)
        self.assertTrue(result.ambiguous)
        self.assertIs(result.reason, AmbiguityReason.EXACT_CONFLICT)
        self.assertEqual(result.candidates, (left, right))

    def test_equal_nonexact_top_rank_is_explicit_tie(self):
        left = candidate(0, EvidenceSource.INCOMPLETE_CHORD)
        right = candidate(9, EvidenceSource.INCOMPLETE_CHORD)
        decision = ResolverDecision(ResolverStatus.AMBIGUOUS, (left, right))
        result = assess_ambiguity((left, right), decision)
        self.assertTrue(result.ambiguous)
        self.assertIs(result.reason, AmbiguityReason.TOP_RANK_TIE)

    def test_resolved_decision_is_not_reopened_by_gate(self):
        primary = candidate(0, EvidenceSource.EXACT)
        alternative = candidate(9, EvidenceSource.INCOMPLETE_CHORD)
        decision = ResolverDecision(ResolverStatus.RESOLVED, (primary,))
        result = assess_ambiguity((primary, alternative), decision)
        self.assertFalse(result.ambiguous)
        self.assertIsNone(result.reason)
        self.assertEqual(result.candidates, ())

    def test_no_match_is_not_reported_as_ambiguity(self):
        result = assess_ambiguity((), ResolverDecision(ResolverStatus.NO_MATCH, ()))
        self.assertFalse(result.ambiguous)

    def test_decision_must_reference_candidate_pool(self):
        left = candidate(0, EvidenceSource.EXACT)
        right = candidate(7, EvidenceSource.EXACT)
        with self.assertRaises(ValueError):
            assess_ambiguity((left,), ResolverDecision(ResolverStatus.RESOLVED, (right,)))

    def test_repeated_runs_are_equal_and_input_order_stable(self):
        left = candidate(0, EvidenceSource.INCOMPLETE_CHORD)
        right = candidate(9, EvidenceSource.INCOMPLETE_CHORD)
        decision = ResolverDecision(ResolverStatus.AMBIGUOUS, (right, left))
        expected = assess_ambiguity((right, left), decision)
        self.assertEqual(assess_ambiguity((left, right), decision), expected)
        for _ in range(10):
            self.assertEqual(assess_ambiguity((right, left), decision), expected)

    def test_invalid_inputs_are_rejected(self):
        left = candidate(0, EvidenceSource.EXACT)
        decision = ResolverDecision(ResolverStatus.RESOLVED, (left,))
        with self.assertRaises(TypeError):
            assess_ambiguity((object(),), decision)
        with self.assertRaises(TypeError):
            assess_ambiguity((left,), object())
        with self.assertRaises(ValueError):
            assess_ambiguity((left, left), decision)


if __name__ == "__main__":
    unittest.main()
