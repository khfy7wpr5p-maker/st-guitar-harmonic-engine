import unittest

from st_guitar_harmonic_engine.resolver import (
    CandidateFamily,
    EvidenceSource,
    HarmonicIdentity,
    ResolverCandidate,
)
from st_guitar_harmonic_engine.voice_leading import (
    annotate_voice_leading,
    observe_voice_leading,
)


def basic(root, variant, *evidence):
    return ResolverCandidate(
        HarmonicIdentity(root, CandidateFamily.BASIC, variant),
        tuple(evidence),
    )


class VoiceLeadingEvidenceTests(unittest.TestCase):
    def test_unambiguous_neighbor_can_add_bounded_support(self):
        g_major = basic(7, "major", EvidenceSource.EXACT)
        c_major = basic(0, "major", EvidenceSource.INCOMPLETE_CHORD)
        observations = observe_voice_leading((c_major,), previous=(g_major,))
        self.assertEqual(len(observations), 1)
        self.assertGreaterEqual(observations[0].previous_links, 2)
        result = annotate_voice_leading((c_major,), previous=(g_major,))
        self.assertEqual(
            result[0].evidence,
            (EvidenceSource.INCOMPLETE_CHORD, EvidenceSource.VOICE_FUNCTION),
        )

    def test_ambiguous_neighbor_is_not_used_as_voice_leading_authority(self):
        current = (basic(0, "major", EvidenceSource.INCOMPLETE_CHORD),)
        previous = (
            basic(7, "major", EvidenceSource.EXACT),
            basic(11, "diminished", EvidenceSource.EXACT),
        )
        self.assertEqual(observe_voice_leading(current, previous=previous), ())
        self.assertEqual(annotate_voice_leading(current, previous=previous), current)

    def test_nonbasic_neighbor_is_not_interpreted(self):
        current = (basic(0, "major", EvidenceSource.INCOMPLETE_CHORD),)
        extension = ResolverCandidate(
            HarmonicIdentity(7, CandidateFamily.EXTENSION, "major:natural_ninth"),
            (EvidenceSource.COLOR_TONE,),
        )
        self.assertEqual(annotate_voice_leading(current, previous=(extension,)), current)

    def test_exact_precedence_is_preserved(self):
        g_major = basic(7, "major", EvidenceSource.EXACT)
        c_major = basic(0, "major", EvidenceSource.EXACT, EvidenceSource.BASS_INVERSION)
        result = annotate_voice_leading((c_major,), previous=(g_major,))
        self.assertEqual(result[0].evidence[0], EvidenceSource.EXACT)
        self.assertIn(EvidenceSource.BASS_INVERSION, result[0].evidence)
        self.assertIn(EvidenceSource.VOICE_FUNCTION, result[0].evidence)

    def test_candidate_cardinality_order_and_repeated_run_are_stable(self):
        current = (
            basic(0, "major", EvidenceSource.INCOMPLETE_CHORD),
            basic(9, "minor", EvidenceSource.INCOMPLETE_CHORD),
        )
        previous = (basic(7, "major", EvidenceSource.EXACT),)
        expected = annotate_voice_leading(current, previous=previous)
        self.assertEqual(tuple(item.identity for item in expected), tuple(item.identity for item in current))
        for _ in range(10):
            self.assertEqual(annotate_voice_leading(current, previous=previous), expected)

    def test_invalid_inputs_are_rejected(self):
        with self.assertRaises(TypeError):
            observe_voice_leading((object(),))


if __name__ == "__main__":
    unittest.main()
