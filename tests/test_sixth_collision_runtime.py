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


def decision_for(target, context=None):
    return resolve_candidates_by_precedence(aggregate_frame_evidence(target, context))


class SixthCollisionRuntimeTests(unittest.TestCase):
    def test_major_sixth_pitch_set_preserves_equal_exact_ambiguity_without_context(self):
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

    def test_minor_sixth_pitch_set_preserves_equal_exact_ambiguity_without_context(self):
        candidates = aggregate_frame_evidence(frame(48, 51, 55, 57))  # C Eb G A
        self.assertEqual(
            {item.identity for item in candidates},
            {
                HarmonicIdentity(0, CandidateFamily.BASIC, "minor_sixth"),
                HarmonicIdentity(9, CandidateFamily.BASIC, "half_diminished_seventh"),
            },
        )
        self.assertEqual(resolve_candidates_by_precedence(candidates).status.value, "ambiguous")

    def test_explicit_major_tonic_resolves_major_sixth_collision(self):
        decision = decision_for(
            frame(48, 52, 55, 57),
            TonalContext(0, TonalMode.MAJOR),
        )
        self.assertEqual(decision.status.value, "resolved")
        self.assertEqual(
            decision.candidates[0].identity,
            HarmonicIdentity(0, CandidateFamily.BASIC, "major_sixth"),
        )
        self.assertIn(EvidenceSource.TONAL_CONTEXT, decision.candidates[0].evidence)

    def test_explicit_minor_tonic_resolves_competing_minor_seventh(self):
        decision = decision_for(
            frame(48, 52, 55, 57),
            TonalContext(9, TonalMode.MINOR),
        )
        self.assertEqual(decision.status.value, "resolved")
        self.assertEqual(
            decision.candidates[0].identity,
            HarmonicIdentity(9, CandidateFamily.BASIC, "minor_seventh"),
        )
        self.assertIn(EvidenceSource.TONAL_CONTEXT, decision.candidates[0].evidence)

    def test_major_sixth_collision_stays_ambiguous_under_unrelated_or_wrong_mode_context(self):
        for context in (
            TonalContext(0, TonalMode.MINOR),
            TonalContext(5, TonalMode.MAJOR),
            TonalContext(9, TonalMode.MAJOR),
        ):
            with self.subTest(context=context):
                self.assertEqual(
                    decision_for(frame(48, 52, 55, 57), context).status.value,
                    "ambiguous",
                )

    def test_explicit_minor_tonic_resolves_minor_sixth_collision(self):
        decision = decision_for(
            frame(48, 51, 55, 57),
            TonalContext(0, TonalMode.MINOR),
        )
        self.assertEqual(decision.status.value, "resolved")
        self.assertEqual(
            decision.candidates[0].identity,
            HarmonicIdentity(0, CandidateFamily.BASIC, "minor_sixth"),
        )
        self.assertIn(EvidenceSource.TONAL_CONTEXT, decision.candidates[0].evidence)

    def test_half_diminished_collision_is_not_promoted_as_minor_tonic(self):
        decision = decision_for(
            frame(48, 51, 55, 57),
            TonalContext(9, TonalMode.MINOR),
        )
        self.assertEqual(decision.status.value, "ambiguous")
        self.assertTrue(
            all(EvidenceSource.TONAL_CONTEXT not in item.evidence for item in decision.candidates)
        )

    def test_root_position_minor_seventh_is_protected(self):
        candidates = aggregate_frame_evidence(frame(57, 60, 64, 67))  # A C E G
        self.assertEqual(
            tuple(item.identity for item in candidates),
            (HarmonicIdentity(9, CandidateFamily.BASIC, "minor_seventh"),),
        )
        self.assertEqual(resolve_candidates_by_precedence(candidates).status.value, "resolved")

    def test_root_position_half_diminished_seventh_is_protected(self):
        candidates = aggregate_frame_evidence(frame(59, 62, 65, 69))  # B D F A
        self.assertEqual(
            tuple(item.identity for item in candidates),
            (HarmonicIdentity(11, CandidateFamily.BASIC, "half_diminished_seventh"),),
        )
        self.assertEqual(resolve_candidates_by_precedence(candidates).status.value, "resolved")

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

    def test_repeated_contextual_collision_resolution_is_deterministic(self):
        target = frame(48, 52, 55, 57)
        context = TonalContext(0, TonalMode.MAJOR)
        expected = aggregate_frame_evidence(target, context)
        for _ in range(10):
            self.assertEqual(aggregate_frame_evidence(target, context), expected)
            self.assertEqual(
                resolve_candidates_by_precedence(aggregate_frame_evidence(target, context)),
                resolve_candidates_by_precedence(expected),
            )


if __name__ == "__main__":
    unittest.main()
