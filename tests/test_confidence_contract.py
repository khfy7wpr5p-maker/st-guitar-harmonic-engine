import unittest

from st_guitar_harmonic_engine.confidence import (
    CONFIDENCE_SEMANTICS,
    ConfidenceAssessment,
    ConfidenceState,
)
from st_guitar_harmonic_engine.resolver import EvidenceSource


class ConfidenceContractTests(unittest.TestCase):
    def test_contract_is_explicitly_non_probabilistic(self):
        self.assertEqual(
            CONFIDENCE_SEMANTICS,
            "categorical_evidence_state_not_probability",
        )
        assessment = ConfidenceAssessment(
            ConfidenceState.STRONG,
            (EvidenceSource.EXACT,),
        )
        self.assertFalse(hasattr(assessment, "probability"))
        self.assertFalse(hasattr(assessment, "score"))
        self.assertFalse(hasattr(assessment, "percentage"))

    def test_basis_requires_canonical_precedence_order(self):
        ConfidenceAssessment(
            ConfidenceState.BOUNDED,
            (EvidenceSource.TONAL_CONTEXT, EvidenceSource.BASS_INVERSION),
        )
        with self.assertRaises(ValueError):
            ConfidenceAssessment(
                ConfidenceState.BOUNDED,
                (EvidenceSource.BASS_INVERSION, EvidenceSource.TONAL_CONTEXT),
            )

    def test_duplicate_basis_is_rejected(self):
        with self.assertRaises(ValueError):
            ConfidenceAssessment(
                ConfidenceState.STRONG,
                (EvidenceSource.EXACT, EvidenceSource.EXACT),
            )

    def test_insufficient_cannot_claim_supporting_evidence(self):
        ConfidenceAssessment(ConfidenceState.INSUFFICIENT, ())
        with self.assertRaises(ValueError):
            ConfidenceAssessment(
                ConfidenceState.INSUFFICIENT,
                (EvidenceSource.ADJACENT_CONTEXT,),
            )

    def test_repeated_construction_is_equal(self):
        first = ConfidenceAssessment(
            ConfidenceState.WEAK,
            (EvidenceSource.INCOMPLETE_CHORD,),
        )
        second = ConfidenceAssessment(
            ConfidenceState.WEAK,
            (EvidenceSource.INCOMPLETE_CHORD,),
        )
        self.assertEqual(first, second)

    def test_invalid_types_are_rejected(self):
        with self.assertRaises(TypeError):
            ConfidenceAssessment("strong", (EvidenceSource.EXACT,))
        with self.assertRaises(TypeError):
            ConfidenceAssessment(ConfidenceState.STRONG, ("exact",))


if __name__ == "__main__":
    unittest.main()
