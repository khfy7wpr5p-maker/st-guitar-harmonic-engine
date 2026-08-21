import unittest

from st_guitar_harmonic_engine.context import TonalContext, TonalMode
from st_guitar_harmonic_engine.functional import (
    FunctionalRelation,
    annotate_functional_relations,
    observe_functional_relations,
)
from st_guitar_harmonic_engine.resolver import (
    CandidateFamily,
    EvidenceSource,
    HarmonicIdentity,
    ResolverCandidate,
)


def basic(root, variant, *evidence):
    return ResolverCandidate(
        HarmonicIdentity(root, CandidateFamily.BASIC, variant),
        tuple(evidence),
    )


class FunctionalEvidenceTests(unittest.TestCase):
    def test_explicit_major_context_recognizes_v_to_i(self):
        context = TonalContext(0, TonalMode.MAJOR)
        dominant = basic(7, "dominant_seventh", EvidenceSource.EXACT)
        tonic = basic(0, "major", EvidenceSource.INCOMPLETE_CHORD)
        observations = observe_functional_relations((tonic,), context, previous=(dominant,))
        self.assertEqual(len(observations), 1)
        self.assertIs(observations[0].relation, FunctionalRelation.DOMINANT_TO_TONIC)
        self.assertTrue(observations[0].from_previous)

    def test_minor_context_allows_major_dominant_to_minor_tonic(self):
        context = TonalContext(9, TonalMode.MINOR)
        dominant = basic(4, "major", EvidenceSource.EXACT)
        tonic = basic(9, "minor", EvidenceSource.INCOMPLETE_CHORD)
        result = annotate_functional_relations((tonic,), context, previous=(dominant,))
        self.assertIn(EvidenceSource.VOICE_FUNCTION, result[0].evidence)

    def test_ambiguous_neighbor_is_not_functional_authority(self):
        context = TonalContext(0, TonalMode.MAJOR)
        tonic = basic(0, "major", EvidenceSource.INCOMPLETE_CHORD)
        previous = (
            basic(7, "major", EvidenceSource.EXACT),
            basic(11, "diminished", EvidenceSource.EXACT),
        )
        self.assertEqual(observe_functional_relations((tonic,), context, previous=previous), ())
        self.assertEqual(annotate_functional_relations((tonic,), context, previous=previous), (tonic,))

    def test_wrong_key_does_not_fabricate_cadence(self):
        context = TonalContext(2, TonalMode.MAJOR)
        dominant = basic(7, "dominant_seventh", EvidenceSource.EXACT)
        tonic = basic(0, "major", EvidenceSource.INCOMPLETE_CHORD)
        self.assertEqual(observe_functional_relations((tonic,), context, previous=(dominant,)), ())

    def test_candidate_cardinality_order_and_exact_precedence_are_preserved(self):
        context = TonalContext(0, TonalMode.MAJOR)
        current = (
            basic(0, "major", EvidenceSource.EXACT, EvidenceSource.BASS_INVERSION),
            basic(9, "minor", EvidenceSource.EXACT, EvidenceSource.BASS_INVERSION),
        )
        previous = (basic(7, "dominant_seventh", EvidenceSource.EXACT),)
        result = annotate_functional_relations(current, context, previous=previous)
        self.assertEqual(tuple(item.identity for item in result), tuple(item.identity for item in current))
        self.assertEqual(result[0].evidence[0], EvidenceSource.EXACT)
        self.assertEqual(result[1].evidence, current[1].evidence)
        for _ in range(10):
            self.assertEqual(annotate_functional_relations(current, context, previous=previous), result)

    def test_invalid_inputs_are_rejected(self):
        tonic = basic(0, "major", EvidenceSource.EXACT)
        with self.assertRaises(TypeError):
            observe_functional_relations((tonic,), object())
        with self.assertRaises(TypeError):
            observe_functional_relations((object(),), TonalContext(0, TonalMode.MAJOR))


if __name__ == "__main__":
    unittest.main()
