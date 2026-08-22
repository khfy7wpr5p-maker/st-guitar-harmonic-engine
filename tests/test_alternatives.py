import unittest

from st_guitar_harmonic_engine.abstention import apply_abstention_policy
from st_guitar_harmonic_engine.alternatives import build_alternative_report
from st_guitar_harmonic_engine.confidence import ConfidenceState
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


class AlternativesContractTests(unittest.TestCase):
    def test_resolved_has_primary_and_ranked_alternatives(self):
        primary = candidate(0, EvidenceSource.EXACT)
        bounded = candidate(7, EvidenceSource.STRUCTURAL)
        weak = candidate(9, EvidenceSource.INCOMPLETE_CHORD)
        gated = apply_abstention_policy(
            ResolverDecision(ResolverStatus.RESOLVED, (primary,))
        )
        report = build_alternative_report((weak, primary, bounded), gated)
        self.assertEqual(report.primary, primary)
        self.assertEqual(
            tuple(item.candidate for item in report.alternatives),
            (bounded, weak),
        )
        self.assertEqual(
            tuple(item.confidence.state for item in report.alternatives),
            (ConfidenceState.BOUNDED, ConfidenceState.WEAK),
        )

    def test_abstain_never_claims_primary(self):
        withheld = candidate(0, EvidenceSource.INCOMPLETE_CHORD)
        gated = apply_abstention_policy(
            ResolverDecision(ResolverStatus.RESOLVED, (withheld,))
        )
        report = build_alternative_report((withheld,), gated)
        self.assertIsNone(report.primary)
        self.assertEqual(report.alternatives[0].candidate, withheld)
        self.assertIs(report.alternatives[0].confidence.state, ConfidenceState.WEAK)

    def test_ambiguous_never_claims_primary_and_keeps_all_candidates(self):
        left = candidate(0, EvidenceSource.EXACT)
        right = candidate(3, EvidenceSource.EXACT)
        gated = apply_abstention_policy(
            ResolverDecision(ResolverStatus.AMBIGUOUS, (right, left))
        )
        report = build_alternative_report((right, left), gated)
        self.assertIsNone(report.primary)
        self.assertEqual(
            tuple(item.candidate for item in report.alternatives),
            (left, right),
        )

    def test_no_match_requires_empty_pool_and_has_no_alternatives(self):
        gated = apply_abstention_policy(ResolverDecision(ResolverStatus.NO_MATCH, ()))
        self.assertEqual(build_alternative_report((), gated).alternatives, ())
        with self.assertRaises(ValueError):
            build_alternative_report((candidate(0, EvidenceSource.EXACT),), gated)

    def test_source_decision_must_be_inside_pool(self):
        primary = candidate(0, EvidenceSource.EXACT)
        other = candidate(7, EvidenceSource.EXACT)
        gated = apply_abstention_policy(
            ResolverDecision(ResolverStatus.RESOLVED, (primary,))
        )
        with self.assertRaises(ValueError):
            build_alternative_report((other,), gated)

    def test_repeated_runs_and_input_order_are_stable(self):
        primary = candidate(0, EvidenceSource.EXACT)
        left = candidate(7, EvidenceSource.INCOMPLETE_CHORD)
        right = candidate(9, EvidenceSource.INCOMPLETE_CHORD)
        gated = apply_abstention_policy(
            ResolverDecision(ResolverStatus.RESOLVED, (primary,))
        )
        values = (right, primary, left)
        expected = build_alternative_report(values, gated)
        self.assertEqual(build_alternative_report(tuple(reversed(values)), gated), expected)
        for _ in range(10):
            self.assertEqual(build_alternative_report(values, gated), expected)

    def test_duplicate_and_invalid_inputs_are_rejected(self):
        primary = candidate(0, EvidenceSource.EXACT)
        gated = apply_abstention_policy(
            ResolverDecision(ResolverStatus.RESOLVED, (primary,))
        )
        with self.assertRaises(ValueError):
            build_alternative_report((primary, primary), gated)
        with self.assertRaises(TypeError):
            build_alternative_report((object(),), gated)
        with self.assertRaises(TypeError):
            build_alternative_report((primary,), object())


if __name__ == "__main__":
    unittest.main()
