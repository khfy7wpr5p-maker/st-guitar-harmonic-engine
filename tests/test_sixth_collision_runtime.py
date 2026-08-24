import unittest

from st_guitar_harmonic_engine.abstention import FinalDecisionState, apply_abstention_policy
from st_guitar_harmonic_engine.aggregator import aggregate_frame_evidence
from st_guitar_harmonic_engine.context import TonalContext, TonalMode
from st_guitar_harmonic_engine.frames import HarmonicFrame
from st_guitar_harmonic_engine.models import NoteEvent, RationalBeat, TieState
from st_guitar_harmonic_engine.resolver import CandidateFamily, EvidenceSource, HarmonicIdentity
from st_guitar_harmonic_engine.sequence import resolve_candidates_by_precedence


def frame(*pitches):
    return HarmonicFrame(
        1,
        RationalBeat(0),
        RationalBeat(1),
        tuple(
            NoteEvent(
                measure_number=1,
                staff=1,
                voice=index + 1,
                midi_pitch=pitch,
                onset=RationalBeat(0),
                duration=RationalBeat(1),
                tie=TieState.NONE,
            )
            for index, pitch in enumerate(pitches)
        ),
    )


class SixthCollisionRuntimeTests(unittest.TestCase):
    def test_major_sixth_pitch_set_preserves_equal_exact_ambiguity(self):
        candidates = aggregate_frame_evidence(frame(48, 52, 55, 57))  # C E G A
        self.assertEqual(
            {item.identity for item in candidates},
            {
                HarmonicIdentity(0, CandidateFamily.BASIC, "major_sixth"),
                HarmonicIdentity(9, CandidateFamily.BASIC, "minor_seventh"),
            },
        )
        self.assertTrue(all(EvidenceSource.EXACT in item.evidence for item in candidates))
        decision = resolve_candidates_by_precedence(candidates)
        self.assertEqual(decision.status.value, "ambiguous")
        self.assertIs(apply_abstention_policy(decision).state, FinalDecisionState.AMBIGUOUS)

    def test_minor_sixth_pitch_set_preserves_equal_exact_ambiguity(self):
        candidates = aggregate_frame_evidence(frame(48, 51, 55, 57))  # C Eb G A
        self.assertEqual(
            {item.identity for item in candidates},
            {
                HarmonicIdentity(0, CandidateFamily.BASIC, "minor_sixth"),
                HarmonicIdentity(9, CandidateFamily.BASIC, "half_diminished_seventh"),
            },
        )
        self.assertEqual(resolve_candidates_by_precedence(candidates).status.value, "ambiguous")

    def test_transposed_major_sixth_collision_is_detected(self):
        candidates = aggregate_frame_evidence(frame(53, 57, 60, 62))  # F A C D
        self.assertEqual(
            {item.identity for item in candidates},
            {
                HarmonicIdentity(5, CandidateFamily.BASIC, "major_sixth"),
                HarmonicIdentity(2, CandidateFamily.BASIC, "minor_seventh"),
            },
        )

    def test_non_collision_exact_chord_is_unchanged(self):
        candidates = aggregate_frame_evidence(frame(48, 52, 55, 59))  # Cmaj7
        self.assertEqual(len(candidates), 1)
        self.assertEqual(
            candidates[0].identity,
            HarmonicIdentity(0, CandidateFamily.BASIC, "major_seventh"),
        )

    def test_tonal_context_does_not_break_collision_in_this_contract(self):
        candidates = aggregate_frame_evidence(
            frame(48, 52, 55, 57),
            TonalContext(0, TonalMode.MAJOR),
        )
        self.assertEqual(len(candidates), 2)
        self.assertTrue(
            all(EvidenceSource.TONAL_CONTEXT not in item.evidence for item in candidates)
        )
        self.assertEqual(resolve_candidates_by_precedence(candidates).status.value, "ambiguous")

    def test_repeated_collision_aggregation_is_deterministic(self):
        target = frame(48, 52, 55, 57)
        expected = aggregate_frame_evidence(target)
        for _ in range(10):
            self.assertEqual(aggregate_frame_evidence(target), expected)


if __name__ == "__main__":
    unittest.main()
