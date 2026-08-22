import unittest

from st_guitar_harmonic_engine.confidence import ConfidenceState
from st_guitar_harmonic_engine.ranking import rank_candidates
from st_guitar_harmonic_engine.resolver import (
    CandidateFamily,
    EvidenceSource,
    HarmonicIdentity,
    ResolverCandidate,
)


def candidate(root, *evidence):
    return ResolverCandidate(
        HarmonicIdentity(root, CandidateFamily.BASIC, "major"),
        tuple(evidence),
    )


class CandidateRankingContractTests(unittest.TestCase):
    def test_strong_group_precedes_bounded_and_weak(self):
        strong = candidate(0, EvidenceSource.EXACT)
        bounded = candidate(2, EvidenceSource.STRUCTURAL)
        weak = candidate(4, EvidenceSource.INCOMPLETE_CHORD)
        groups = rank_candidates((weak, strong, bounded))
        self.assertEqual(
            tuple(group.assessment.state for group in groups),
            (ConfidenceState.STRONG, ConfidenceState.BOUNDED, ConfidenceState.WEAK),
        )
        self.assertEqual(groups[0].candidates, (strong,))

    def test_same_rank_remains_explicit_tie_group(self):
        left = candidate(0, EvidenceSource.INCOMPLETE_CHORD)
        right = candidate(9, EvidenceSource.INCOMPLETE_CHORD)
        groups = rank_candidates((right, left))
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].candidates, (left, right))
        self.assertIs(groups[0].assessment.state, ConfidenceState.WEAK)

    def test_precedence_orders_equal_strength_without_numeric_score(self):
        tonal = candidate(0, EvidenceSource.TONAL_CONTEXT)
        bass = candidate(7, EvidenceSource.BASS_INVERSION)
        groups = rank_candidates((bass, tonal))
        self.assertEqual(groups[0].candidates, (tonal,))
        self.assertEqual(groups[1].candidates, (bass,))

    def test_ranking_does_not_mutate_or_remove_candidates(self):
        values = (
            candidate(7, EvidenceSource.VOICE_FUNCTION),
            candidate(0, EvidenceSource.EXACT),
            candidate(5, EvidenceSource.COLOR_TONE),
        )
        groups = rank_candidates(values)
        flattened = tuple(item for group in groups for item in group.candidates)
        self.assertEqual({item.identity for item in flattened}, {item.identity for item in values})
        self.assertEqual(len(flattened), len(values))

    def test_repeated_runs_are_equal_and_input_order_independent(self):
        values = (
            candidate(9, EvidenceSource.INCOMPLETE_CHORD),
            candidate(0, EvidenceSource.INCOMPLETE_CHORD),
            candidate(7, EvidenceSource.EXACT),
        )
        expected = rank_candidates(values)
        self.assertEqual(rank_candidates(tuple(reversed(values))), expected)
        for _ in range(10):
            self.assertEqual(rank_candidates(values), expected)

    def test_empty_and_invalid_inputs(self):
        self.assertEqual(rank_candidates(()), ())
        with self.assertRaises(TypeError):
            rank_candidates((object(),))
        duplicate = candidate(0, EvidenceSource.EXACT)
        with self.assertRaises(ValueError):
            rank_candidates((duplicate, duplicate))


if __name__ == "__main__":
    unittest.main()
