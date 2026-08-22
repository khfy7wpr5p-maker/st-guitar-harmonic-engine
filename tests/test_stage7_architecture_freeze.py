import json
import unittest

from st_guitar_harmonic_engine.abstention import FinalDecisionState, apply_abstention_policy
from st_guitar_harmonic_engine.ai_evidence import (
    AI_EVIDENCE_SCHEMA_VERSION,
    AI_SUPPORTED_DOMAIN,
    AI_TASK_CONTRACT_VERSION,
)
from st_guitar_harmonic_engine.ai_shadow import (
    AI_AUTHORITATIVE_SOURCE,
    AI_AUTHORITY_SEMANTICS,
    AI_SHADOW_AUDIT_SCHEMA_VERSION,
)
from st_guitar_harmonic_engine.benchmark import (
    BENCHMARK_ACCURACY_CLAIM,
    BENCHMARK_SCHEMA_VERSION,
)
from st_guitar_harmonic_engine.explainability_schema import EXPLAINABILITY_SCHEMA_VERSION
from st_guitar_harmonic_engine.guitar_voicing import (
    GUITAR_VOICING_AUTHORITY,
    GUITAR_VOICING_SCHEMA_VERSION,
)
from st_guitar_harmonic_engine.performance import PERFORMANCE_AUTHORITY, PERFORMANCE_CONTRACT_VERSION
from st_guitar_harmonic_engine.public_api import (
    PUBLIC_API_SCHEMA_VERSION,
    PUBLIC_RESULT_SCHEMA_VERSION,
    serialize_public_result,
)
from st_guitar_harmonic_engine.resolver import (
    EVIDENCE_PRECEDENCE,
    CandidateFamily,
    EvidenceSource,
    HarmonicIdentity,
    ResolverCandidate,
    ResolverDecision,
    ResolverStatus,
)
from st_guitar_harmonic_engine.sequence import resolve_candidates_by_precedence


class Stage7ArchitectureFreezeTests(unittest.TestCase):
    def test_evidence_precedence_is_frozen_and_non_weighted(self):
        self.assertEqual(
            EVIDENCE_PRECEDENCE,
            (
                EvidenceSource.EXACT,
                EvidenceSource.TONAL_CONTEXT,
                EvidenceSource.STRUCTURAL,
                EvidenceSource.BASS_INVERSION,
                EvidenceSource.VERIFIED_NCT,
                EvidenceSource.INCOMPLETE_CHORD,
                EvidenceSource.COLOR_TONE,
                EvidenceSource.ADJACENT_CONTEXT,
                EvidenceSource.VOICE_FUNCTION,
            ),
        )

    def test_ai_contract_remains_shadow_bounded_and_non_authoritative(self):
        self.assertEqual(AI_EVIDENCE_SCHEMA_VERSION, "1.0")
        self.assertEqual(AI_TASK_CONTRACT_VERSION, "1.0")
        self.assertEqual(AI_SUPPORTED_DOMAIN, "guitar_harmony")
        self.assertEqual(AI_SHADOW_AUDIT_SCHEMA_VERSION, "1.0")
        self.assertEqual(
            AI_AUTHORITY_SEMANTICS,
            "shadow_only_bounded_evidence_never_authoritative",
        )
        self.assertEqual(AI_AUTHORITATIVE_SOURCE, "deterministic_resolver")

    def test_guitar_evidence_remains_descriptive_only(self):
        self.assertEqual(GUITAR_VOICING_SCHEMA_VERSION, "1.0")
        self.assertEqual(
            GUITAR_VOICING_AUTHORITY,
            "descriptive_bounded_evidence_not_harmonic_authority",
        )

    def test_public_explainability_benchmark_and_performance_contracts_are_frozen(self):
        self.assertEqual(EXPLAINABILITY_SCHEMA_VERSION, "1.0")
        self.assertEqual(PUBLIC_API_SCHEMA_VERSION, "1.0")
        self.assertEqual(PUBLIC_RESULT_SCHEMA_VERSION, "1.0")
        self.assertEqual(BENCHMARK_SCHEMA_VERSION, "1.0")
        self.assertEqual(BENCHMARK_ACCURACY_CLAIM, "not_available_without_teacher_gold")
        self.assertEqual(PERFORMANCE_CONTRACT_VERSION, "1.0")
        self.assertEqual(PERFORMANCE_AUTHORITY, "diagnostic_only")

    def test_final_state_vocabulary_is_frozen(self):
        self.assertEqual(
            tuple(item.value for item in FinalDecisionState),
            ("resolved", "ambiguous", "abstain", "no_match"),
        )

    def test_bass_only_candidate_cannot_cross_abstention_gate(self):
        candidate = ResolverCandidate(
            HarmonicIdentity(0, CandidateFamily.BASIC, "major"),
            (EvidenceSource.BASS_INVERSION,),
        )
        source = ResolverDecision(ResolverStatus.RESOLVED, (candidate,))
        gated = apply_abstention_policy(source)
        self.assertIs(gated.state, FinalDecisionState.ABSTAIN)
        self.assertEqual(gated.confidence.state.value, "weak")

    def test_exact_tie_remains_ambiguous(self):
        left = ResolverCandidate(
            HarmonicIdentity(0, CandidateFamily.BASIC, "major"),
            (EvidenceSource.EXACT,),
        )
        right = ResolverCandidate(
            HarmonicIdentity(3, CandidateFamily.BASIC, "minor"),
            (EvidenceSource.EXACT,),
        )
        decision = resolve_candidates_by_precedence((right, left))
        self.assertIs(decision.status, ResolverStatus.AMBIGUOUS)
        self.assertEqual(decision.candidates, (left, right))

    def test_public_serialization_cannot_turn_confidence_into_probability(self):
        from st_guitar_harmonic_engine.frames import HarmonicFrame
        from st_guitar_harmonic_engine.models import NoteEvent, RationalBeat

        frame = HarmonicFrame(
            1,
            RationalBeat(0),
            RationalBeat(1),
            (
                NoteEvent(1, 1, 1, 60, RationalBeat(0), RationalBeat(1)),
                NoteEvent(1, 1, 2, 64, RationalBeat(0), RationalBeat(1)),
                NoteEvent(1, 1, 3, 67, RationalBeat(0), RationalBeat(1)),
            ),
        )
        candidate = ResolverCandidate(
            HarmonicIdentity(0, CandidateFamily.BASIC, "major"),
            (EvidenceSource.EXACT,),
        )
        gated = apply_abstention_policy(
            ResolverDecision(ResolverStatus.RESOLVED, (candidate,))
        )
        serialized = json.dumps(serialize_public_result((frame,), (gated,)), sort_keys=True)
        self.assertNotIn("probability", serialized)
        self.assertNotIn('"score"', serialized)


if __name__ == "__main__":
    unittest.main()
