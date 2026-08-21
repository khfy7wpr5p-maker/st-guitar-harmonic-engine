import unittest

from st_guitar_harmonic_engine.context import TonalContext, TonalMode
from st_guitar_harmonic_engine.frames import HarmonicFrame
from st_guitar_harmonic_engine.local_context import LocalTonalContextPlan, LocalTonalContextSpan
from st_guitar_harmonic_engine.models import NoteEvent, RationalBeat, TieState
from st_guitar_harmonic_engine.phrase import PhrasePlan, PhraseSpan
from st_guitar_harmonic_engine.resolver import (
    CandidateFamily,
    EvidenceSource,
    HarmonicIdentity,
    ResolverCandidate,
    ResolverStatus,
)
from st_guitar_harmonic_engine.sequence import (
    resolve_candidates_by_precedence,
    resolve_harmonic_sequence,
)


def frame(*pitches):
    events = tuple(
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
    )
    return HarmonicFrame(1, RationalBeat(0), RationalBeat(1), events)


def candidate(root, variant, *evidence):
    return ResolverCandidate(
        HarmonicIdentity(root, CandidateFamily.BASIC, variant),
        tuple(evidence),
    )


class DeterministicSequenceResolverTests(unittest.TestCase):
    def test_unique_exact_frame_resolves(self):
        result = resolve_harmonic_sequence((frame(48, 52, 55),))
        self.assertIs(result.decisions[0].status, ResolverStatus.RESOLVED)
        self.assertEqual(result.decisions[0].candidates[0].identity.root_pc, 0)

    def test_exact_ambiguity_is_not_broken_by_weak_sequence_evidence(self):
        left = candidate(0, "diminished_seventh", EvidenceSource.EXACT, EvidenceSource.ADJACENT_CONTEXT)
        right = candidate(3, "diminished_seventh", EvidenceSource.EXACT)
        decision = resolve_candidates_by_precedence((left, right))
        self.assertIs(decision.status, ResolverStatus.AMBIGUOUS)
        self.assertEqual(len(decision.candidates), 2)

    def test_explicit_tonal_context_may_narrow_exact_ambiguity(self):
        left = candidate(0, "major", EvidenceSource.EXACT, EvidenceSource.TONAL_CONTEXT)
        right = candidate(9, "minor", EvidenceSource.EXACT)
        decision = resolve_candidates_by_precedence((left, right))
        self.assertIs(decision.status, ResolverStatus.RESOLVED)
        self.assertEqual(decision.candidates, (left,))

    def test_nonexact_tie_can_be_narrowed_lexicographically_without_scores(self):
        left = candidate(
            0,
            "major",
            EvidenceSource.INCOMPLETE_CHORD,
            EvidenceSource.ADJACENT_CONTEXT,
        )
        right = candidate(9, "minor", EvidenceSource.INCOMPLETE_CHORD)
        decision = resolve_candidates_by_precedence((right, left))
        self.assertIs(decision.status, ResolverStatus.RESOLVED)
        self.assertEqual(decision.candidates, (left,))

    def test_equal_nonexact_evidence_stays_ambiguous(self):
        candidates = (
            candidate(0, "major", EvidenceSource.INCOMPLETE_CHORD),
            candidate(9, "minor", EvidenceSource.INCOMPLETE_CHORD),
        )
        self.assertIs(resolve_candidates_by_precedence(candidates).status, ResolverStatus.AMBIGUOUS)

    def test_no_candidates_returns_no_match(self):
        self.assertIs(resolve_candidates_by_precedence(()).status, ResolverStatus.NO_MATCH)

    def test_sequence_context_requires_explicit_phrase_plan(self):
        frames = (frame(48, 52, 55), frame(48, 52, 55))
        isolated = resolve_harmonic_sequence(frames)
        self.assertNotIn(EvidenceSource.ADJACENT_CONTEXT, isolated.candidates[0][0].evidence)
        bounded = resolve_harmonic_sequence(frames, phrase_plan=PhrasePlan((PhraseSpan(0, 2),)))
        self.assertIn(EvidenceSource.ADJACENT_CONTEXT, bounded.candidates[0][0].evidence)
        self.assertIn(EvidenceSource.ADJACENT_CONTEXT, bounded.candidates[1][0].evidence)

    def test_phrase_boundary_blocks_context_leakage(self):
        frames = (frame(48, 52, 55), frame(48, 52, 55))
        result = resolve_harmonic_sequence(
            frames,
            phrase_plan=PhrasePlan((PhraseSpan(0, 1), PhraseSpan(1, 2))),
        )
        self.assertNotIn(EvidenceSource.ADJACENT_CONTEXT, result.candidates[0][0].evidence)
        self.assertNotIn(EvidenceSource.ADJACENT_CONTEXT, result.candidates[1][0].evidence)

    def test_explicit_local_context_is_forwarded_without_key_guessing(self):
        frames = (frame(48, 52, 55), frame(48, 52, 55))
        plan = LocalTonalContextPlan(
            (LocalTonalContextSpan(0, 1, TonalContext(0, TonalMode.MAJOR)),)
        )
        result = resolve_harmonic_sequence(frames, local_context=plan)
        self.assertIn(EvidenceSource.TONAL_CONTEXT, result.candidates[0][0].evidence)
        self.assertNotIn(EvidenceSource.TONAL_CONTEXT, result.candidates[1][0].evidence)

    def test_repeated_runs_are_equal(self):
        frames = (frame(55, 59, 62), frame(48, 52, 55))
        phrase = PhrasePlan((PhraseSpan(0, 2),))
        context = LocalTonalContextPlan(
            (LocalTonalContextSpan(0, 2, TonalContext(0, TonalMode.MAJOR)),)
        )
        expected = resolve_harmonic_sequence(frames, context, phrase)
        for _ in range(10):
            self.assertEqual(resolve_harmonic_sequence(frames, context, phrase), expected)

    def test_invalid_inputs_and_duplicate_identities_are_rejected(self):
        with self.assertRaises(TypeError):
            resolve_harmonic_sequence((object(),))
        duplicate = candidate(0, "major", EvidenceSource.INCOMPLETE_CHORD)
        with self.assertRaises(ValueError):
            resolve_candidates_by_precedence((duplicate, duplicate))


if __name__ == "__main__":
    unittest.main()
