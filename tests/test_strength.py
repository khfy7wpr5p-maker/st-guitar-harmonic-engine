import unittest

from st_guitar_harmonic_engine.confidence import ConfidenceState
from st_guitar_harmonic_engine.resolver import (
    CandidateFamily,
    EvidenceSource,
    HarmonicIdentity,
    ResolverCandidate,
)
from st_guitar_harmonic_engine.strength import assess_candidate_strength


def candidate(*evidence):
    return ResolverCandidate(
        HarmonicIdentity(0, CandidateFamily.BASIC, "major"),
        tuple(evidence),
    )


class EvidenceStrengthTests(unittest.TestCase):
    def test_exact_is_strong_even_with_lower_evidence(self):
        result = assess_candidate_strength(
            candidate(
                EvidenceSource.EXACT,
                EvidenceSource.ADJACENT_CONTEXT,
                EvidenceSource.VOICE_FUNCTION,
            )
        )
        self.assertIs(result.state, ConfidenceState.STRONG)

    def test_direct_contextual_or_structural_support_is_bounded(self):
        for source in (
            EvidenceSource.TONAL_CONTEXT,
            EvidenceSource.STRUCTURAL,
            EvidenceSource.VERIFIED_NCT,
        ):
            with self.subTest(source=source):
                self.assertIs(
                    assess_candidate_strength(candidate(source)).state,
                    ConfidenceState.BOUNDED,
                )

    def test_bass_inversion_alone_is_weak_not_bounded(self):
        result = assess_candidate_strength(candidate(EvidenceSource.BASS_INVERSION))
        self.assertIs(result.state, ConfidenceState.WEAK)
        self.assertEqual(result.basis, (EvidenceSource.BASS_INVERSION,))

    def test_weak_primary_with_independent_corroboration_is_bounded(self):
        result = assess_candidate_strength(
            candidate(
                EvidenceSource.INCOMPLETE_CHORD,
                EvidenceSource.ADJACENT_CONTEXT,
            )
        )
        self.assertIs(result.state, ConfidenceState.BOUNDED)

    def test_single_lower_evidence_is_weak(self):
        for source in (
            EvidenceSource.BASS_INVERSION,
            EvidenceSource.INCOMPLETE_CHORD,
            EvidenceSource.COLOR_TONE,
            EvidenceSource.ADJACENT_CONTEXT,
            EvidenceSource.VOICE_FUNCTION,
        ):
            with self.subTest(source=source):
                self.assertIs(
                    assess_candidate_strength(candidate(source)).state,
                    ConfidenceState.WEAK,
                )

    def test_no_evidence_is_insufficient(self):
        result = assess_candidate_strength(candidate())
        self.assertIs(result.state, ConfidenceState.INSUFFICIENT)
        self.assertEqual(result.basis, ())

    def test_repeated_runs_are_equal(self):
        target = candidate(
            EvidenceSource.INCOMPLETE_CHORD,
            EvidenceSource.ADJACENT_CONTEXT,
        )
        expected = assess_candidate_strength(target)
        for _ in range(10):
            self.assertEqual(assess_candidate_strength(target), expected)

    def test_invalid_input_is_rejected(self):
        with self.assertRaises(TypeError):
            assess_candidate_strength(object())


if __name__ == "__main__":
    unittest.main()
