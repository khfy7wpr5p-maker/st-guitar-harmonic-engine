import json
import unittest

from st_guitar_harmonic_engine.abstention import AbstentionReason, FinalDecisionState
from st_guitar_harmonic_engine.ambiguity import AmbiguityReason
from st_guitar_harmonic_engine.confidence import ConfidenceState
from st_guitar_harmonic_engine.decision_audit import (
    DECISION_AUDIT_SCHEMA_NAME,
    DECISION_AUDIT_SCHEMA_VERSION,
    audit_sequence_resolution,
    build_decision_audit,
    is_decision_audit_payload_compatible,
    serialize_decision_audit,
)
from st_guitar_harmonic_engine.resolver import (
    CandidateFamily,
    EvidenceSource,
    HarmonicIdentity,
    ResolverCandidate,
    ResolverDecision,
    ResolverStatus,
)
from st_guitar_harmonic_engine.sequence import SequenceResolution


def candidate(root, *evidence):
    return ResolverCandidate(
        HarmonicIdentity(root, CandidateFamily.BASIC, "major"),
        tuple(evidence),
    )


class DecisionAuditTests(unittest.TestCase):
    def test_resolved_audit_reports_primary_support_conflict_and_confidence(self):
        primary = candidate(0, EvidenceSource.EXACT)
        alternative = candidate(7, EvidenceSource.BASS_INVERSION)
        decision = ResolverDecision(ResolverStatus.RESOLVED, (primary,))
        original = decision
        audit = build_decision_audit((alternative, primary), decision)
        self.assertIs(audit.final_state, FinalDecisionState.RESOLVED)
        self.assertEqual(audit.primary, primary)
        self.assertEqual(audit.supporting_evidence, (EvidenceSource.EXACT,))
        self.assertEqual(audit.conflicting_evidence, (EvidenceSource.BASS_INVERSION,))
        self.assertIs(audit.confidence.state, ConfidenceState.STRONG)
        self.assertIsNone(audit.ambiguity_reason)
        self.assertIsNone(audit.abstention_reason)
        self.assertEqual(decision, original)

    def test_exact_ambiguity_has_no_primary_and_reports_reason(self):
        left = candidate(0, EvidenceSource.EXACT)
        right = candidate(3, EvidenceSource.EXACT)
        decision = ResolverDecision(ResolverStatus.AMBIGUOUS, (right, left))
        audit = build_decision_audit((right, left), decision)
        self.assertIs(audit.final_state, FinalDecisionState.AMBIGUOUS)
        self.assertIsNone(audit.primary)
        self.assertIs(audit.ambiguity_reason, AmbiguityReason.EXACT_CONFLICT)
        self.assertEqual(audit.supporting_evidence, (EvidenceSource.EXACT,))
        self.assertEqual(audit.conflicting_evidence, ())
        self.assertIsNone(audit.confidence)
        self.assertEqual(
            tuple(item.candidate for item in audit.alternatives),
            (left, right),
        )

    def test_ambiguous_divergent_evidence_is_reported_not_resolved(self):
        left = candidate(
            0,
            EvidenceSource.INCOMPLETE_CHORD,
            EvidenceSource.ADJACENT_CONTEXT,
        )
        right = candidate(
            9,
            EvidenceSource.INCOMPLETE_CHORD,
            EvidenceSource.VOICE_FUNCTION,
        )
        decision = ResolverDecision(ResolverStatus.AMBIGUOUS, (left, right))
        audit = build_decision_audit((left, right), decision)
        self.assertIs(audit.final_state, FinalDecisionState.AMBIGUOUS)
        self.assertEqual(audit.supporting_evidence, (EvidenceSource.INCOMPLETE_CHORD,))
        self.assertEqual(
            audit.conflicting_evidence,
            (EvidenceSource.ADJACENT_CONTEXT, EvidenceSource.VOICE_FUNCTION),
        )

    def test_weak_resolved_source_is_audited_as_abstain(self):
        withheld = candidate(0, EvidenceSource.INCOMPLETE_CHORD)
        decision = ResolverDecision(ResolverStatus.RESOLVED, (withheld,))
        audit = build_decision_audit((withheld,), decision)
        self.assertIs(audit.final_state, FinalDecisionState.ABSTAIN)
        self.assertIsNone(audit.primary)
        self.assertIs(audit.confidence.state, ConfidenceState.WEAK)
        self.assertIs(audit.abstention_reason, AbstentionReason.WEAK_EVIDENCE)
        self.assertEqual(audit.supporting_evidence, (EvidenceSource.INCOMPLETE_CHORD,))
        self.assertEqual(audit.alternatives[0].candidate, withheld)

    def test_no_match_audit_is_empty_and_explicit(self):
        decision = ResolverDecision(ResolverStatus.NO_MATCH, ())
        audit = build_decision_audit((), decision)
        self.assertIs(audit.final_state, FinalDecisionState.NO_MATCH)
        self.assertIsNone(audit.primary)
        self.assertEqual(audit.alternatives, ())
        self.assertEqual(audit.supporting_evidence, ())
        self.assertEqual(audit.conflicting_evidence, ())

    def test_serialization_is_stable_versioned_and_non_probabilistic(self):
        primary = candidate(0, EvidenceSource.EXACT)
        alternative = candidate(7, EvidenceSource.INCOMPLETE_CHORD)
        audit = build_decision_audit(
            (alternative, primary),
            ResolverDecision(ResolverStatus.RESOLVED, (primary,)),
        )
        payload = serialize_decision_audit(audit)
        self.assertEqual(payload["schema_name"], DECISION_AUDIT_SCHEMA_NAME)
        self.assertEqual(payload["schema_version"], DECISION_AUDIT_SCHEMA_VERSION)
        self.assertEqual(payload["confidence_state"], "strong")
        self.assertNotIn("probability", payload)
        self.assertNotIn("score", payload)
        self.assertTrue(is_decision_audit_payload_compatible(payload))
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        for _ in range(10):
            self.assertEqual(
                json.dumps(
                    serialize_decision_audit(audit),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                encoded,
            )

    def test_payload_compatibility_rejects_wrong_or_extra_schema(self):
        audit = build_decision_audit(
            (),
            ResolverDecision(ResolverStatus.NO_MATCH, ()),
        )
        payload = serialize_decision_audit(audit)
        wrong = dict(payload)
        wrong["schema_version"] = "2.0"
        self.assertFalse(is_decision_audit_payload_compatible(wrong))
        extra = dict(payload)
        extra["authoritative_override"] = True
        self.assertFalse(is_decision_audit_payload_compatible(extra))
        self.assertFalse(is_decision_audit_payload_compatible(object()))

    def test_sequence_audit_preserves_frame_decisions(self):
        exact = candidate(0, EvidenceSource.EXACT)
        weak = candidate(9, EvidenceSource.INCOMPLETE_CHORD)
        resolution = SequenceResolution(
            ((exact,), (weak,), ()),
            (
                ResolverDecision(ResolverStatus.RESOLVED, (exact,)),
                ResolverDecision(ResolverStatus.RESOLVED, (weak,)),
                ResolverDecision(ResolverStatus.NO_MATCH, ()),
            ),
        )
        original = resolution
        audits = audit_sequence_resolution(resolution)
        self.assertEqual(
            tuple(item.final_state for item in audits),
            (
                FinalDecisionState.RESOLVED,
                FinalDecisionState.ABSTAIN,
                FinalDecisionState.NO_MATCH,
            ),
        )
        self.assertEqual(resolution, original)

    def test_candidate_input_order_does_not_change_audit(self):
        primary = candidate(0, EvidenceSource.EXACT)
        left = candidate(7, EvidenceSource.INCOMPLETE_CHORD)
        right = candidate(9, EvidenceSource.BASS_INVERSION)
        decision = ResolverDecision(ResolverStatus.RESOLVED, (primary,))
        expected = build_decision_audit((right, primary, left), decision)
        self.assertEqual(
            build_decision_audit((left, primary, right), decision),
            expected,
        )

    def test_invalid_inputs_are_rejected(self):
        with self.assertRaises(TypeError):
            build_decision_audit((), object())
        with self.assertRaises(TypeError):
            audit_sequence_resolution(object())
        with self.assertRaises(TypeError):
            serialize_decision_audit(object())


if __name__ == "__main__":
    unittest.main()
