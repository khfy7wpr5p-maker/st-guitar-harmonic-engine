import unittest

from st_guitar_harmonic_engine.abstention import (
    AbstentionReason,
    FinalDecisionState,
    apply_abstention_policy,
)
from st_guitar_harmonic_engine.decision_audit import build_decision_audit
from st_guitar_harmonic_engine.public_api import serialize_gated_decision
from st_guitar_harmonic_engine.resolver import (
    CandidateFamily,
    EvidenceSource,
    HarmonicIdentity,
    ResolverCandidate,
    ResolverDecision,
    ResolverStatus,
)


def candidate(root, family, variant, *evidence):
    return ResolverCandidate(
        HarmonicIdentity(root, family, variant),
        tuple(evidence),
    )


class WeakIncompleteAmbiguityAbstainTests(unittest.TestCase):
    def test_all_weak_incomplete_ambiguity_abstains_without_selecting_identity(self):
        left = candidate(
            0,
            CandidateFamily.BASIC,
            "major",
            EvidenceSource.INCOMPLETE_CHORD,
        )
        right = candidate(
            9,
            CandidateFamily.BASIC,
            "minor_seventh",
            EvidenceSource.INCOMPLETE_CHORD,
        )
        decision = ResolverDecision(ResolverStatus.AMBIGUOUS, (left, right))
        gated = apply_abstention_policy(decision)
        self.assertIs(gated.state, FinalDecisionState.ABSTAIN)
        self.assertEqual(gated.source_decision, decision)
        self.assertIsNone(gated.confidence)
        self.assertIs(
            gated.abstention_reason,
            AbstentionReason.AMBIGUOUS_WEAK_INCOMPLETE,
        )
        self.assertEqual(gated.source_decision.candidates, (left, right))

    def test_exact_ambiguity_remains_ambiguous(self):
        left = candidate(0, CandidateFamily.BASIC, "augmented", EvidenceSource.EXACT)
        right = candidate(4, CandidateFamily.BASIC, "augmented", EvidenceSource.EXACT)
        decision = ResolverDecision(ResolverStatus.AMBIGUOUS, (left, right))
        gated = apply_abstention_policy(decision)
        self.assertIs(gated.state, FinalDecisionState.AMBIGUOUS)
        self.assertIsNone(gated.abstention_reason)

    def test_suspended_color_ambiguity_remains_ambiguous(self):
        left = candidate(0, CandidateFamily.SUSPENDED, "sus2", EvidenceSource.COLOR_TONE)
        right = candidate(7, CandidateFamily.SUSPENDED, "sus4", EvidenceSource.COLOR_TONE)
        decision = ResolverDecision(ResolverStatus.AMBIGUOUS, (left, right))
        gated = apply_abstention_policy(decision)
        self.assertIs(gated.state, FinalDecisionState.AMBIGUOUS)
        self.assertIsNone(gated.abstention_reason)

    def test_bounded_incomplete_ambiguity_is_not_hidden(self):
        left = candidate(
            0,
            CandidateFamily.BASIC,
            "major",
            EvidenceSource.INCOMPLETE_CHORD,
            EvidenceSource.ADJACENT_CONTEXT,
        )
        right = candidate(
            9,
            CandidateFamily.BASIC,
            "minor_seventh",
            EvidenceSource.INCOMPLETE_CHORD,
            EvidenceSource.VOICE_FUNCTION,
        )
        decision = ResolverDecision(ResolverStatus.AMBIGUOUS, (left, right))
        gated = apply_abstention_policy(decision)
        self.assertIs(gated.state, FinalDecisionState.AMBIGUOUS)

    def test_audit_preserves_underlying_ambiguity_when_final_gate_abstains(self):
        left = candidate(
            0,
            CandidateFamily.BASIC,
            "major",
            EvidenceSource.INCOMPLETE_CHORD,
        )
        right = candidate(
            9,
            CandidateFamily.BASIC,
            "minor_seventh",
            EvidenceSource.INCOMPLETE_CHORD,
        )
        decision = ResolverDecision(ResolverStatus.AMBIGUOUS, (left, right))
        audit = build_decision_audit((left, right), decision)
        self.assertIs(audit.final_state, FinalDecisionState.ABSTAIN)
        self.assertIs(audit.source_status, ResolverStatus.AMBIGUOUS)
        self.assertIsNone(audit.primary)
        self.assertIsNone(audit.confidence)
        self.assertIsNotNone(audit.ambiguity_reason)
        self.assertIs(
            audit.abstention_reason,
            AbstentionReason.AMBIGUOUS_WEAK_INCOMPLETE,
        )
        self.assertEqual(audit.supporting_evidence, (EvidenceSource.INCOMPLETE_CHORD,))
        self.assertEqual(audit.conflicting_evidence, ())
        self.assertEqual(
            {item.candidate.identity for item in audit.alternatives},
            {left.identity, right.identity},
        )

    def test_public_serialization_keeps_all_source_candidates_and_reason(self):
        left = candidate(
            0,
            CandidateFamily.BASIC,
            "major",
            EvidenceSource.INCOMPLETE_CHORD,
        )
        right = candidate(
            9,
            CandidateFamily.BASIC,
            "minor_seventh",
            EvidenceSource.INCOMPLETE_CHORD,
        )
        gated = apply_abstention_policy(
            ResolverDecision(ResolverStatus.AMBIGUOUS, (left, right))
        )
        payload = serialize_gated_decision(gated)
        self.assertEqual(payload["state"], "abstain")
        self.assertEqual(payload["source_status"], "ambiguous")
        self.assertEqual(len(payload["candidates"]), 2)
        self.assertIsNone(payload["confidence"])
        self.assertEqual(
            payload["abstention_reason"],
            "ambiguous_weak_incomplete",
        )

    def test_repeated_runs_are_deterministic(self):
        left = candidate(
            0,
            CandidateFamily.BASIC,
            "major",
            EvidenceSource.INCOMPLETE_CHORD,
        )
        right = candidate(
            9,
            CandidateFamily.BASIC,
            "minor_seventh",
            EvidenceSource.INCOMPLETE_CHORD,
        )
        decision = ResolverDecision(ResolverStatus.AMBIGUOUS, (left, right))
        expected = apply_abstention_policy(decision)
        for _ in range(10):
            self.assertEqual(apply_abstention_policy(decision), expected)


if __name__ == "__main__":
    unittest.main()
