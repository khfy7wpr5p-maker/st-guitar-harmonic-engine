import unittest

from st_guitar_harmonic_engine.abstention import FinalDecisionState, apply_abstention_policy
from st_guitar_harmonic_engine.aggregator import aggregate_frame_evidence
from st_guitar_harmonic_engine.alterations import (
    SuspendedChordKind,
    generate_suspended_chord_candidates,
)
from st_guitar_harmonic_engine.frames import HarmonicFrame
from st_guitar_harmonic_engine.models import NoteEvent, RationalBeat, TieState
from st_guitar_harmonic_engine.resolver import CandidateFamily, EvidenceSource, ResolverStatus
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


class SuspendedSeventhVocabularyTests(unittest.TestCase):
    def test_c7sus4_is_one_complete_unique_suspended_candidate(self):
        candidates = generate_suspended_chord_candidates(frame(48, 53, 55, 58))
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].root_pc, 0)
        self.assertIs(candidates[0].kind, SuspendedChordKind.SEVENTH_SUS4)
        self.assertEqual(candidates[0].observed_pitch_classes, (0, 5, 7, 10))

    def test_c7sus2_is_one_complete_unique_suspended_candidate(self):
        candidates = generate_suspended_chord_candidates(frame(48, 50, 55, 58))
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].root_pc, 0)
        self.assertIs(candidates[0].kind, SuspendedChordKind.SEVENTH_SUS2)
        self.assertEqual(candidates[0].observed_pitch_classes, (0, 2, 7, 10))

    def test_complete_suspended_seventh_gets_structural_support_and_resolves_bounded(self):
        candidates = aggregate_frame_evidence(frame(48, 53, 55, 58))
        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertIs(candidate.identity.family, CandidateFamily.SUSPENDED)
        self.assertEqual(candidate.identity.variant, "7sus4")
        self.assertEqual(
            candidate.evidence,
            (EvidenceSource.STRUCTURAL, EvidenceSource.COLOR_TONE),
        )
        source = resolve_candidates_by_precedence(candidates)
        self.assertIs(source.status, ResolverStatus.RESOLVED)
        gated = apply_abstention_policy(source)
        self.assertIs(gated.state, FinalDecisionState.RESOLVED)
        self.assertEqual(gated.confidence.state.value, "bounded")

    def test_suspended_triad_remains_color_tone_only_and_ambiguous(self):
        candidates = aggregate_frame_evidence(frame(48, 53, 55))
        self.assertEqual(len(candidates), 2)
        self.assertTrue(
            all(candidate.evidence == (EvidenceSource.COLOR_TONE,) for candidate in candidates)
        )
        self.assertIs(
            resolve_candidates_by_precedence(candidates).status,
            ResolverStatus.AMBIGUOUS,
        )

    def test_exact_basic_seventh_still_suppresses_suspended_layer(self):
        candidates = generate_suspended_chord_candidates(frame(48, 52, 55, 58))
        self.assertEqual(candidates, ())

    def test_incomplete_7sus_does_not_get_promoted(self):
        self.assertEqual(
            tuple(
                item
                for item in generate_suspended_chord_candidates(frame(48, 53, 58))
                if item.kind in {
                    SuspendedChordKind.SEVENTH_SUS2,
                    SuspendedChordKind.SEVENTH_SUS4,
                }
            ),
            (),
        )

    def test_transposition_and_repeated_runs_are_deterministic(self):
        target = frame(50, 55, 57, 60)  # D7sus4
        expected = generate_suspended_chord_candidates(target)
        self.assertEqual(len(expected), 1)
        self.assertEqual(expected[0].root_pc, 2)
        self.assertIs(expected[0].kind, SuspendedChordKind.SEVENTH_SUS4)
        for _ in range(10):
            self.assertEqual(generate_suspended_chord_candidates(target), expected)
            self.assertEqual(aggregate_frame_evidence(target), aggregate_frame_evidence(target))


if __name__ == "__main__":
    unittest.main()
