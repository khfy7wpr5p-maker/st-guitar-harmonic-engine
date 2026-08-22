import json
import unittest

from st_guitar_harmonic_engine.ai_evidence import (
    AI_EVIDENCE_SCHEMA_NAME,
    AI_EVIDENCE_SCHEMA_VERSION,
    AI_SUPPORTED_DOMAIN,
    AIRejectionReason,
    ModelCompatibilityPolicy,
)
from st_guitar_harmonic_engine.ai_shadow import (
    AI_AUTHORITATIVE_SOURCE,
    AI_AUTHORITY_SEMANTICS,
    AIRuntimeFailure,
    ModelUnavailableError,
    is_ai_shadow_audit_payload_compatible,
    run_shadow_ai_adapter,
    serialize_ai_shadow_audit,
)
from st_guitar_harmonic_engine.resolver import (
    CandidateFamily,
    EvidenceSource,
    HarmonicIdentity,
    ResolverCandidate,
    ResolverDecision,
    ResolverStatus,
)


CHECKPOINT = "b" * 64
C_MAJOR = HarmonicIdentity(0, CandidateFamily.BASIC, "major")
G_MAJOR = HarmonicIdentity(7, CandidateFamily.BASIC, "major")
KNOWN = (C_MAJOR, G_MAJOR)
POLICY = ModelCompatibilityPolicy("shadow-specialist", ("1.0.0",))


def resolver_candidate(identity, *evidence):
    return ResolverCandidate(identity, tuple(evidence))


def decision(identity=C_MAJOR):
    return ResolverDecision(
        ResolverStatus.RESOLVED,
        (resolver_candidate(identity, EvidenceSource.EXACT),),
    )


def candidate_payload(identity):
    return {
        "root_pc": identity.root_pc,
        "family": identity.family.value,
        "variant": identity.variant,
    }


def payload(*identities):
    evidence = [
        {
            "scope": "candidate",
            "label": "candidate_support",
            "strength": "bounded",
            "support": "supported",
            "candidate": candidate_payload(identity),
        }
        for identity in identities
    ]
    if not evidence:
        evidence = [
            {
                "scope": "input",
                "label": "context_unknown",
                "strength": "unknown",
                "support": "unknown",
                "candidate": None,
            }
        ]
    return {
        "schema_name": AI_EVIDENCE_SCHEMA_NAME,
        "schema_version": AI_EVIDENCE_SCHEMA_VERSION,
        "specialist_type": "candidate_reranker",
        "provenance": {
            "model_id": "shadow-specialist",
            "model_version": "1.0.0",
            "checkpoint_sha256": CHECKPOINT,
            "training_dataset_manifest_id": "teacher-gold-manifest",
            "training_dataset_version": "1",
            "task_contract_version": "1.0",
            "inference_schema_version": "1.0",
        },
        "source": "shadow-test-adapter",
        "input_identity": "frame-42",
        "supported_domain": AI_SUPPORTED_DOMAIN,
        "evidence": evidence,
    }


def run(adapter, deterministic=None, *, policy=POLICY):
    return run_shadow_ai_adapter(
        adapter,
        object(),
        deterministic_decision=deterministic or decision(),
        known_candidates=KNOWN,
        expected_input_identity="frame-42",
        compatibility=policy,
    )


class AIShadowRuntimeTests(unittest.TestCase):
    def test_agreement_is_audit_only_and_preserves_authority(self):
        deterministic = decision()
        audit = run(lambda request: payload(C_MAJOR), deterministic)
        self.assertEqual(audit.authoritative_decision, deterministic)
        self.assertTrue(audit.agreement)
        self.assertFalse(audit.disagreement)
        self.assertEqual(audit.candidate_overlap, (C_MAJOR,))
        self.assertEqual(audit.authoritative_source, AI_AUTHORITATIVE_SOURCE)
        self.assertEqual(audit.authoritative_decision.candidates[0].identity, C_MAJOR)

    def test_disagreement_never_replaces_deterministic_result(self):
        deterministic = decision(C_MAJOR)
        audit = run(lambda request: payload(G_MAJOR), deterministic)
        self.assertFalse(audit.agreement)
        self.assertTrue(audit.disagreement)
        self.assertEqual(audit.candidate_overlap, ())
        self.assertEqual(audit.authoritative_decision, deterministic)
        self.assertEqual(audit.authoritative_decision.candidates[0].identity, C_MAJOR)

    def test_partial_overlap_is_reported_as_disagreement(self):
        deterministic = ResolverDecision(
            ResolverStatus.AMBIGUOUS,
            (
                resolver_candidate(C_MAJOR, EvidenceSource.EXACT),
                resolver_candidate(G_MAJOR, EvidenceSource.EXACT),
            ),
        )
        audit = run(lambda request: payload(C_MAJOR), deterministic)
        self.assertFalse(audit.agreement)
        self.assertTrue(audit.disagreement)
        self.assertEqual(audit.candidate_overlap, (C_MAJOR,))
        self.assertEqual(audit.authoritative_decision, deterministic)

    def test_input_scoped_evidence_does_not_claim_harmony(self):
        audit = run(lambda request: payload())
        self.assertFalse(audit.agreement)
        self.assertFalse(audit.disagreement)
        self.assertEqual(audit.candidate_overlap, ())
        self.assertIsNotNone(audit.ai_evidence)

    def test_timeout_exception_empty_and_unavailable_fail_closed(self):
        def timeout(_request):
            raise TimeoutError("late")

        def broken(_request):
            raise RuntimeError("boom")

        def unavailable(_request):
            raise ModelUnavailableError("offline")

        cases = (
            (timeout, AIRuntimeFailure.TIMEOUT),
            (broken, AIRuntimeFailure.EXCEPTION),
            (lambda request: None, AIRuntimeFailure.EMPTY_RESPONSE),
            (lambda request: {}, AIRuntimeFailure.EMPTY_RESPONSE),
            (unavailable, AIRuntimeFailure.MODEL_UNAVAILABLE),
        )
        deterministic = decision()
        for adapter, expected in cases:
            with self.subTest(expected=expected):
                audit = run(adapter, deterministic)
                self.assertIs(audit.runtime_failure, expected)
                self.assertIsNone(audit.ai_evidence)
                self.assertEqual(audit.authoritative_decision, deterministic)
                self.assertFalse(audit.agreement)
                self.assertFalse(audit.disagreement)

    def test_malformed_unknown_schema_and_stale_model_fail_closed(self):
        malformed = payload(C_MAJOR)
        del malformed["provenance"]
        audit = run(lambda request: malformed)
        self.assertIs(audit.rejected_ai_evidence_reason, AIRejectionReason.MALFORMED_SCHEMA)
        self.assertIsNone(audit.ai_evidence)

        unknown_schema = payload(C_MAJOR)
        unknown_schema["schema_version"] = "9.0"
        audit = run(lambda request: unknown_schema)
        self.assertIs(
            audit.rejected_ai_evidence_reason,
            AIRejectionReason.UNSUPPORTED_SCHEMA_VERSION,
        )

        stale = payload(C_MAJOR)
        stale["provenance"]["model_version"] = "0.9.0"
        audit = run(lambda request: stale)
        self.assertIs(
            audit.rejected_ai_evidence_reason,
            AIRejectionReason.INCOMPATIBLE_MODEL_VERSION,
        )

    def test_duplicate_and_conflicting_ai_evidence_never_reaches_authority(self):
        duplicate = payload(C_MAJOR)
        duplicate["evidence"].append(dict(duplicate["evidence"][0]))
        audit = run(lambda request: duplicate)
        self.assertIs(
            audit.rejected_ai_evidence_reason,
            AIRejectionReason.DUPLICATE_RESPONSE,
        )
        self.assertEqual(audit.authoritative_decision, decision())

        conflicting = payload(C_MAJOR)
        conflict = dict(conflicting["evidence"][0])
        conflict["support"] = "unsupported"
        conflicting["evidence"].append(conflict)
        audit = run(lambda request: conflicting)
        self.assertIs(
            audit.rejected_ai_evidence_reason,
            AIRejectionReason.CONFLICTING_EVIDENCE,
        )
        self.assertEqual(audit.authoritative_decision, decision())

    def test_repeated_calls_and_input_order_are_deterministic(self):
        first = payload(C_MAJOR, G_MAJOR)
        second = payload(C_MAJOR, G_MAJOR)
        second["evidence"].reverse()
        expected = run(lambda request: first)
        for _ in range(10):
            self.assertEqual(run(lambda request: first), expected)
        reordered = run(lambda request: second)
        self.assertEqual(expected, reordered)
        self.assertEqual(
            serialize_ai_shadow_audit(expected),
            serialize_ai_shadow_audit(reordered),
        )

    def test_serialization_freezes_authority_and_provenance_audit(self):
        audit = run(lambda request: payload(G_MAJOR))
        serialized = serialize_ai_shadow_audit(audit)
        self.assertTrue(is_ai_shadow_audit_payload_compatible(serialized))
        self.assertEqual(serialized["authority_semantics"], AI_AUTHORITY_SEMANTICS)
        self.assertEqual(serialized["authoritative_source"], AI_AUTHORITATIVE_SOURCE)
        self.assertEqual(
            serialized["deterministic_result"]["candidates"][0]["identity"],
            candidate_payload(C_MAJOR),
        )
        self.assertEqual(serialized["ai_evidence"]["provenance"]["checkpoint_sha256"], CHECKPOINT)
        encoded = json.dumps(serialized, sort_keys=True, separators=(",", ":"))
        for _ in range(10):
            self.assertEqual(
                json.dumps(
                    serialize_ai_shadow_audit(audit),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                encoded,
            )

    def test_runtime_failure_serialization_reports_reason_without_ai_payload(self):
        audit = run(lambda request: None)
        serialized = serialize_ai_shadow_audit(audit)
        self.assertEqual(serialized["runtime_failure"], "empty_response")
        self.assertIsNone(serialized["ai_evidence"])
        self.assertIsNone(serialized["rejected_ai_evidence_reason"])

    def test_non_callable_adapter_and_bad_decision_are_rejected_as_caller_errors(self):
        with self.assertRaises(TypeError):
            run_shadow_ai_adapter(
                object(),
                object(),
                deterministic_decision=decision(),
                known_candidates=KNOWN,
                expected_input_identity="frame-42",
                compatibility=POLICY,
            )
        with self.assertRaises(TypeError):
            run_shadow_ai_adapter(
                lambda request: payload(C_MAJOR),
                object(),
                deterministic_decision=object(),
                known_candidates=KNOWN,
                expected_input_identity="frame-42",
                compatibility=POLICY,
            )


if __name__ == "__main__":
    unittest.main()
