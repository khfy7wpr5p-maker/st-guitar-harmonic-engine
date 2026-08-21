import unittest

from st_guitar_harmonic_engine.phrase import PhrasePlan, PhraseSpan, phrase_bounded_neighbors
from st_guitar_harmonic_engine.resolver import (
    CandidateFamily,
    EvidenceSource,
    HarmonicIdentity,
    ResolverCandidate,
)


def candidate(root):
    return ResolverCandidate(
        HarmonicIdentity(root, CandidateFamily.BASIC, "major"),
        (EvidenceSource.EXACT,),
    )


class PhraseContextTests(unittest.TestCase):
    def test_neighbors_are_available_only_inside_same_phrase(self):
        sequence = ((candidate(0),), (candidate(7),), (candidate(5),), (candidate(0),))
        plan = PhrasePlan((PhraseSpan(0, 2), PhraseSpan(2, 4)))
        previous, next_ = phrase_bounded_neighbors(sequence, 1, plan)
        self.assertEqual(previous, sequence[0])
        self.assertEqual(next_, ())
        previous, next_ = phrase_bounded_neighbors(sequence, 2, plan)
        self.assertEqual(previous, ())
        self.assertEqual(next_, sequence[3])

    def test_uncovered_frames_receive_no_phrase_neighbors(self):
        sequence = ((candidate(0),), (candidate(7),), (candidate(0),))
        plan = PhrasePlan((PhraseSpan(0, 1), PhraseSpan(2, 3)))
        self.assertEqual(phrase_bounded_neighbors(sequence, 1, plan), ((), ()))

    def test_overlapping_or_unsorted_phrases_are_rejected(self):
        with self.assertRaises(ValueError):
            PhrasePlan((PhraseSpan(0, 2), PhraseSpan(1, 3)))
        with self.assertRaises(ValueError):
            PhrasePlan((PhraseSpan(2, 3), PhraseSpan(0, 1)))

    def test_plan_must_fit_sequence(self):
        sequence = ((candidate(0),),)
        with self.assertRaises(ValueError):
            phrase_bounded_neighbors(sequence, 0, PhrasePlan((PhraseSpan(0, 2),)))

    def test_repeated_boundary_queries_are_deterministic(self):
        sequence = ((candidate(0),), (candidate(7),), (candidate(0),))
        plan = PhrasePlan((PhraseSpan(0, 3),))
        expected = phrase_bounded_neighbors(sequence, 1, plan)
        for _ in range(10):
            self.assertEqual(phrase_bounded_neighbors(sequence, 1, plan), expected)

    def test_invalid_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            PhraseSpan(-1, 1)
        with self.assertRaises(TypeError):
            PhrasePlan((object(),))
        with self.assertRaises(TypeError):
            phrase_bounded_neighbors((object(),), 0, PhrasePlan(()))
        with self.assertRaises(IndexError):
            phrase_bounded_neighbors((), 0, PhrasePlan(()))


if __name__ == "__main__":
    unittest.main()
