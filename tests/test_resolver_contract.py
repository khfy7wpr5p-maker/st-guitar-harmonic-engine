import unittest

from st_guitar_harmonic_engine.resolver import (
    EVIDENCE_PRECEDENCE,
    CandidateFamily,
    EvidenceSource,
    HarmonicIdentity,
    ResolverCandidate,
    ResolverDecision,
    ResolverStatus,
    evidence_precedence_index,
    stronger_evidence,
)


class ResolverContractTests(unittest.TestCase):
    def test_precedence_is_complete_unique_and_stable(self):
        self.assertEqual(EVIDENCE_PRECEDENCE[0], EvidenceSource.EXACT)
        self.assertEqual(EVIDENCE_PRECEDENCE[-1], EvidenceSource.VOICE_FUNCTION)
        self.assertEqual(len(EVIDENCE_PRECEDENCE), len(EvidenceSource))
        self.assertEqual(len(set(EVIDENCE_PRECEDENCE)), len(EVIDENCE_PRECEDENCE))
        self.assertEqual(
            tuple(evidence_precedence_index(item) for item in EVIDENCE_PRECEDENCE),
            tuple(range(len(EVIDENCE_PRECEDENCE))),
        )

    def test_exact_always_outranks_lower_evidence(self):
        for source in EVIDENCE_PRECEDENCE[1:]:
            self.assertIs(stronger_evidence(EvidenceSource.EXACT, source), EvidenceSource.EXACT)
            self.assertIs(stronger_evidence(source, EvidenceSource.EXACT), EvidenceSource.EXACT)

    def test_candidate_requires_canonical_evidence_order(self):
        identity = HarmonicIdentity(0, CandidateFamily.BASIC, "major")
        ResolverCandidate(
            identity,
            (EvidenceSource.EXACT, EvidenceSource.TONAL_CONTEXT),
        )
        with self.assertRaises(ValueError):
            ResolverCandidate(
                identity,
                (EvidenceSource.TONAL_CONTEXT, EvidenceSource.EXACT),
            )
        with self.assertRaises(ValueError):
            ResolverCandidate(identity, (EvidenceSource.EXACT, EvidenceSource.EXACT))

    def test_decision_status_preserves_ambiguity_and_no_match(self):
        c_major = ResolverCandidate(
            HarmonicIdentity(0, CandidateFamily.BASIC, "major"),
            (EvidenceSource.EXACT,),
        )
        a_minor = ResolverCandidate(
            HarmonicIdentity(9, CandidateFamily.BASIC, "minor"),
            (EvidenceSource.EXACT,),
        )
        ResolverDecision(ResolverStatus.NO_MATCH, ())
        ResolverDecision(ResolverStatus.RESOLVED, (c_major,))
        ResolverDecision(ResolverStatus.AMBIGUOUS, (c_major, a_minor))
        with self.assertRaises(ValueError):
            ResolverDecision(ResolverStatus.RESOLVED, (c_major, a_minor))
        with self.assertRaises(ValueError):
            ResolverDecision(ResolverStatus.NO_MATCH, (c_major,))

    def test_identity_validation_rejects_untrusted_shape(self):
        with self.assertRaises(ValueError):
            HarmonicIdentity(12, CandidateFamily.BASIC, "major")
        with self.assertRaises(ValueError):
            HarmonicIdentity(0, CandidateFamily.BASIC, "")
        with self.assertRaises(TypeError):
            HarmonicIdentity(0, "basic", "major")

    def test_repeated_construction_is_equal(self):
        first = ResolverCandidate(
            HarmonicIdentity(7, CandidateFamily.BASIC, "dominant_seventh"),
            (EvidenceSource.EXACT, EvidenceSource.BASS_INVERSION),
        )
        second = ResolverCandidate(
            HarmonicIdentity(7, CandidateFamily.BASIC, "dominant_seventh"),
            (EvidenceSource.EXACT, EvidenceSource.BASS_INVERSION),
        )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
