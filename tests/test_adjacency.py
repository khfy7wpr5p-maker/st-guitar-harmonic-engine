import unittest

from st_guitar_harmonic_engine.adjacency import (
    annotate_adjacent_context,
    observe_adjacent_context,
)
from st_guitar_harmonic_engine.resolver import (
    CandidateFamily,
    EvidenceSource,
    HarmonicIdentity,
    ResolverCandidate,
)


def candidate(root, variant, *evidence):
    return ResolverCandidate(
        HarmonicIdentity(root, CandidateFamily.BASIC, variant),
        tuple(evidence),
    )


class AdjacentContextTests(unittest.TestCase):
    def test_matching_previous_candidate_adds_only_adjacent_support(self):
        c = candidate(0, "major", EvidenceSource.INCOMPLETE_CHORD)
        result = annotate_adjacent_context((c,), previous=(c,))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].identity, c.identity)
        self.assertEqual(
            result[0].evidence,
            (EvidenceSource.INCOMPLETE_CHORD, EvidenceSource.ADJACENT_CONTEXT),
        )

    def test_matching_next_candidate_is_recorded(self):
        c = candidate(0, "major", EvidenceSource.EXACT)
        observation = observe_adjacent_context((c,), next_=(c,))
        self.assertEqual(len(observation), 1)
        self.assertFalse(observation[0].previous_match)
        self.assertTrue(observation[0].next_match)

    def test_nonmatching_neighbors_cannot_create_or_remove_candidates(self):
        current = (
            candidate(0, "major", EvidenceSource.EXACT),
            candidate(9, "minor", EvidenceSource.EXACT),
        )
        previous = (candidate(7, "major", EvidenceSource.EXACT),)
        self.assertEqual(annotate_adjacent_context(current, previous), current)

    def test_exact_evidence_is_never_overridden(self):
        c = candidate(0, "major", EvidenceSource.EXACT, EvidenceSource.BASS_INVERSION)
        result = annotate_adjacent_context((c,), previous=(c,), next_=(c,))
        self.assertEqual(result[0].evidence[0], EvidenceSource.EXACT)
        self.assertIn(EvidenceSource.BASS_INVERSION, result[0].evidence)
        self.assertIn(EvidenceSource.ADJACENT_CONTEXT, result[0].evidence)

    def test_cardinality_and_order_are_stable(self):
        current = (
            candidate(0, "major", EvidenceSource.INCOMPLETE_CHORD),
            candidate(4, "minor", EvidenceSource.INCOMPLETE_CHORD),
        )
        expected = annotate_adjacent_context(current, previous=(current[1],), next_=(current[0],))
        self.assertEqual(tuple(item.identity for item in expected), tuple(item.identity for item in current))
        for _ in range(10):
            self.assertEqual(
                annotate_adjacent_context(current, previous=(current[1],), next_=(current[0],)),
                expected,
            )

    def test_invalid_inputs_are_rejected(self):
        with self.assertRaises(TypeError):
            observe_adjacent_context((object(),))
        with self.assertRaises(ValueError):
            from st_guitar_harmonic_engine.adjacency import AdjacentContextObservation
            AdjacentContextObservation(
                HarmonicIdentity(0, CandidateFamily.BASIC, "major"),
                False,
                False,
            )


if __name__ == "__main__":
    unittest.main()
