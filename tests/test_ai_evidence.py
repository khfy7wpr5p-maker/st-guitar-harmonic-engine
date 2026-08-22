import json
import math
import unittest

from st_guitar_harmonic_engine.ai_evidence import (
    AI_EVIDENCE_SCHEMA_NAME,
    AI_EVIDENCE_SCHEMA_VERSION,
    AI_SUPPORTED_DOMAIN,
    AIRejectionReason,
    EvidenceScope,
    ModelCompatibilityPolicy,
    SpecialistEvidenceStrength,
    SpecialistType,
    SupportState,
    is_ai_evidence_payload_compatible,
    serialize_ai_evidence,
    validate_ai_evidence_payload,
)
from st_guitar_harmonic_engine.resolver import CandidateFamily, HarmonicIdentity


CHECKPOINT = "a" * 64
C_MAJOR = HarmonicIdentity(0, CandidateFamily.BASIC, "major")
G_MAJOR = HarmonicIdentity(7, CandidateFamily.BASIC, "major")
KNOWN = (C_MAJOR, G_MAJOR)
POLICY = ModelCompatibilityPolicy("nct-specialist", ("1.0.0",))


def candidate_payload(candidate):
    return {
        "root_pc": candidate.root_pc,
        "family": candidate.family.value,
        "variant": candidate.variant,
    }


def valid_payload():
    return {
        "schema_name": AI_EVIDENCE_SCHEMA_NAME,
        "schema_version": AI_EVIDENCE_SCHEMA_VERSION,
        "specialist_type": "nct",
        "provenance": {
            "model_id": "nct-specialist",
            "model_version": "1.0.0",
            "checkpoint_sha256": CHECKPOINT,
            "training_dataset_manifest_id": "teacher-gold-v1",
            "training_dataset_version": "2026-08",
            "task_contract_version": "1.0",
            "inference_schema_version": "1.0",
        },
        "source": "shadow-adapter",
        "input_identity": "measure-12-frame-3",
        "supported_domain": AI_SUPPORTED_DOMAIN,
        "evidence": [
            {
                "scope": "candidate",
                "label": "nct_consistent",
                "strength": "bounded",
                "support": "supported",
                "candidate": candidate_payload(C_MAJOR),
            },
            {
                "scope": "input",
                "label": "specialist_domain_known",
                "strength": "unknown",
                "support": "unknown",
                "candidate": None,
            },
        ],
    }


def validate(payload, *, policy=POLICY):
    return validate_ai_evidence_payload(
        payload,
        known_candidates=KNOWN,
        expected_input_identity="measure-12-frame-3",
        compatibility=policy,
    )


class AIEvidenceContractTests(unittest.TestCase):
    def test_all_declared_specialists_are_bounded_enum_values(self):
        self.assertEqual(
            {item.name for item in SpecialistType},
            {
                "LOCAL_TONAL_CONTEXT",
                "HARMONIC_BOUNDARY",
                "NCT",
                "INCOMPLETE_CHORD",
                "EXTENSION",
                "SUSPENSION",
                "CADENCE_FUNCTION",
                "PHRASE_CONTEXT",
                "ALTERED_HARMONY",
                "CANDIDATE_RERANKER",
                "ABSTENTION_RISK",
            },
        )

    def test_valid_payload_is_canonical_and_non_probabilistic(self):
        payload = valid_payload()
        payload["evidence"].reverse()
        result = validate(payload)
        self.assertTrue(result.accepted)
        self.assertIsNone(result.rejection_reason)
        evidence = result.evidence
        self.assertIs(evidence.specialist_type, SpecialistType.NCT)
        self.assertEqual(evidence.provenance.checkpoint_sha256, CHECKPOINT)
        self.assertEqual(
            tuple(item.scope for item in evidence.evidence),
            (EvidenceScope.CANDIDATE, EvidenceScope.INPUT),
        )
        encoded = json.dumps(serialize_ai_evidence(evidence), sort_keys=True, separators=(",", ":"))
        for _ in range(10):
            self.assertEqual(
                json.dumps(serialize_ai_evidence(evidence), sort_keys=True, separators=(",", ":")),
                encoded,
            )
        self.assertNotIn("probability", encoded)
        self.assertNotIn("score", encoded)
        self.assertTrue(is_ai_evidence_payload_compatible(serialize_ai_evidence(evidence)))

    def test_unknown_and_unsupported_states_are_explicit(self):
        result = validate(valid_payload())
        input_fact = next(item for item in result.evidence.evidence if item.scope is EvidenceScope.INPUT)
        self.assertIs(input_fact.strength, SpecialistEvidenceStrength.UNKNOWN)
        self.assertIs(input_fact.support, SupportState.UNKNOWN)
        payload = valid_payload()
        payload["evidence"][0]["support"] = "unsupported"
        result = validate(payload)
        self.assertTrue(result.accepted)
        self.assertIs(result.evidence.evidence[0].support, SupportState.UNSUPPORTED)

    def test_wrong_schema_and_unknown_specialist_fail_closed(self):
        payload = valid_payload()
        payload["schema_version"] = "2.0"
        self.assertIs(validate(payload).rejection_reason, AIRejectionReason.UNSUPPORTED_SCHEMA_VERSION)
        payload = valid_payload()
        payload["specialist_type"] = "free_form_agent"
        self.assertIs(validate(payload).rejection_reason, AIRejectionReason.UNKNOWN_SPECIALIST)

    def test_missing_provenance_and_model_identity_fail_closed(self):
        payload = valid_payload()
        payload["provenance"] = None
        self.assertIs(validate(payload).rejection_reason, AIRejectionReason.MISSING_PROVENANCE)
        payload = valid_payload()
        payload["provenance"]["model_id"] = ""
        self.assertIs(validate(payload).rejection_reason, AIRejectionReason.MISSING_MODEL_IDENTITY)

    def test_invalid_hash_nonfinite_and_empty_fields_fail_closed(self):
        payload = valid_payload()
        payload["provenance"]["checkpoint_sha256"] = "not-a-hash"
        self.assertIs(validate(payload).rejection_reason, AIRejectionReason.INVALID_HASH)
        payload = valid_payload()
        payload["evidence"][0]["unexpected"] = math.nan
        self.assertIs(validate(payload).rejection_reason, AIRejectionReason.NON_FINITE_VALUE)
        payload = valid_payload()
        payload["source"] = ""
        self.assertIs(validate(payload).rejection_reason, AIRejectionReason.EMPTY_REQUIRED_FIELD)

    def test_unknown_candidate_and_impossible_pitch_class_fail_closed(self):
        payload = valid_payload()
        payload["evidence"][0]["candidate"] = candidate_payload(
            HarmonicIdentity(9, CandidateFamily.BASIC, "minor")
        )
        self.assertIs(validate(payload).rejection_reason, AIRejectionReason.UNKNOWN_CANDIDATE)
        payload = valid_payload()
        payload["evidence"][0]["candidate"]["root_pc"] = 12
        self.assertIs(validate(payload).rejection_reason, AIRejectionReason.IMPOSSIBLE_VALUE)

    def test_invalid_candidate_enum_fails_closed(self):
        payload = valid_payload()
        payload["evidence"][0]["candidate"]["family"] = "imaginary"
        self.assertIn(
            validate(payload).rejection_reason,
            {AIRejectionReason.INVALID_ENUM, AIRejectionReason.IMPOSSIBLE_VALUE},
        )
        payload = valid_payload()
        payload["evidence"][0]["strength"] = "0.99"
        self.assertIs(validate(payload).rejection_reason, AIRejectionReason.INVALID_ENUM)

    def test_unsupported_domain_and_incompatible_model_fail_closed(self):
        payload = valid_payload()
        payload["supported_domain"] = "general_music"
        self.assertIs(validate(payload).rejection_reason, AIRejectionReason.UNSUPPORTED_DOMAIN)
        payload = valid_payload()
        payload["provenance"]["model_version"] = "9.9.9"
        self.assertIs(validate(payload).rejection_reason, AIRejectionReason.INCOMPATIBLE_MODEL_VERSION)

    def test_duplicate_and_conflicting_facts_are_rejected(self):
        payload = valid_payload()
        payload["evidence"].append(dict(payload["evidence"][0]))
        self.assertIs(validate(payload).rejection_reason, AIRejectionReason.DUPLICATE_RESPONSE)
        payload = valid_payload()
        conflicting = dict(payload["evidence"][0])
        conflicting["support"] = "unsupported"
        payload["evidence"].append(conflicting)
        self.assertIs(validate(payload).rejection_reason, AIRejectionReason.CONFLICTING_EVIDENCE)

    def test_input_identity_mismatch_and_partial_payload_are_rejected(self):
        payload = valid_payload()
        payload["input_identity"] = "stale-input"
        self.assertIs(validate(payload).rejection_reason, AIRejectionReason.INPUT_IDENTITY_MISMATCH)
        payload = valid_payload()
        del payload["evidence"]
        self.assertIs(validate(payload).rejection_reason, AIRejectionReason.MALFORMED_SCHEMA)

    def test_empty_evidence_is_not_accepted_as_model_claim(self):
        payload = valid_payload()
        payload["evidence"] = []
        self.assertIs(validate(payload).rejection_reason, AIRejectionReason.MALFORMED_EVIDENCE)

    def test_input_order_does_not_change_validated_or_serialized_evidence(self):
        left = valid_payload()
        right = valid_payload()
        right["evidence"].reverse()
        left_result = validate(left)
        right_result = validate(right)
        self.assertEqual(left_result.evidence, right_result.evidence)
        self.assertEqual(
            serialize_ai_evidence(left_result.evidence),
            serialize_ai_evidence(right_result.evidence),
        )

    def test_validator_rejects_bad_caller_contracts_before_untrusted_data(self):
        with self.assertRaises(TypeError):
            validate_ai_evidence_payload(
                valid_payload(),
                known_candidates=(object(),),
                expected_input_identity="measure-12-frame-3",
                compatibility=POLICY,
            )
        with self.assertRaises(ValueError):
            ModelCompatibilityPolicy("nct-specialist", ("1.0.0", "1.0.0"))


if __name__ == "__main__":
    unittest.main()
