import unittest

from st_guitar_harmonic_engine import (
    CandidateFamily,
    ChordQuality,
    EvidenceSource,
    HarmonicFrame,
    NoteEvent,
    RationalBeat,
    TieState,
    TonalContext,
    TonalMode,
    analyze_frame_exact,
)
from st_guitar_harmonic_engine.abstention import FinalDecisionState, apply_abstention_policy
from st_guitar_harmonic_engine.aggregator import aggregate_frame_evidence
from st_guitar_harmonic_engine.confidence import ConfidenceState
from st_guitar_harmonic_engine.resolver import ResolverDecision, ResolverStatus
from st_guitar_harmonic_engine.strength import assess_candidate_strength


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


class CandidateEvidenceAggregatorTests(unittest.TestCase):
    def test_exact_candidate_is_preserved_with_bass_evidence(self):
        result = aggregate_frame_evidence(frame(48, 52, 55))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].identity.root_pc, 0)
        self.assertIs(result[0].identity.family, CandidateFamily.BASIC)
        self.assertEqual(result[0].identity.variant, ChordQuality.MAJOR.value)
        self.assertEqual(
            result[0].evidence,
            (EvidenceSource.EXACT, EvidenceSource.BASS_INVERSION),
        )

    def test_exact_aggregator_path_stays_strong_after_bass_only_hardening(self):
        candidates = aggregate_frame_evidence(frame(48, 52, 55))
        self.assertEqual(
            candidates[0].evidence,
            (EvidenceSource.EXACT, EvidenceSource.BASS_INVERSION),
        )
        self.assertIs(
            assess_candidate_strength(candidates[0]).state,
            ConfidenceState.STRONG,
        )
        gated = apply_abstention_policy(
            ResolverDecision(ResolverStatus.RESOLVED, candidates)
        )
        self.assertIs(gated.state, FinalDecisionState.RESOLVED)
        self.assertEqual(gated.source_decision.candidates, candidates)

    def test_explicit_tonal_context_only_adds_support_to_matching_exact_candidate(self):
        result = aggregate_frame_evidence(
            frame(48, 52, 55),
            TonalContext(0, TonalMode.MAJOR),
        )
        self.assertEqual(
            result[0].evidence,
            (
                EvidenceSource.EXACT,
                EvidenceSource.TONAL_CONTEXT,
                EvidenceSource.BASS_INVERSION,
            ),
        )

    def test_exact_match_suppresses_lower_evidence_producers(self):
        target = frame(48, 52, 55, 57)  # exact A minor seventh
        self.assertEqual(len(analyze_frame_exact(target).candidates), 1)
        result = aggregate_frame_evidence(target)
        self.assertTrue(all(EvidenceSource.EXACT in item.evidence for item in result))
        self.assertTrue(all(EvidenceSource.INCOMPLETE_CHORD not in item.evidence for item in result))
        self.assertTrue(all(EvidenceSource.COLOR_TONE not in item.evidence for item in result))

    def test_incomplete_basic_candidate_is_normalized_without_ranking(self):
        result = aggregate_frame_evidence(frame(48, 52))  # C E; C major may omit G
        matching = [
            item
            for item in result
            if item.identity.root_pc == 0
            and item.identity.family is CandidateFamily.BASIC
            and item.identity.variant == ChordQuality.MAJOR.value
        ]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].evidence, (EvidenceSource.INCOMPLETE_CHORD,))

    def test_extension_candidate_is_normalized_as_color_tone(self):
        result = aggregate_frame_evidence(frame(48, 50, 52, 55))  # C D E G
        matching = [
            item
            for item in result
            if item.identity.root_pc == 0
            and item.identity.family is CandidateFamily.EXTENSION
            and item.identity.variant == "major:natural_ninth"
        ]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].evidence, (EvidenceSource.COLOR_TONE,))

    def test_repeated_runs_are_equal_and_ordered(self):
        target = frame(48, 52)
        expected = aggregate_frame_evidence(target)
        self.assertEqual(tuple(item.identity for item in expected), tuple(sorted(item.identity for item in expected)))
        for _ in range(10):
            self.assertEqual(aggregate_frame_evidence(target), expected)

    def test_aggregation_does_not_mutate_exact_analysis(self):
        target = frame(48, 52, 55)
        before = analyze_frame_exact(target)
        aggregate_frame_evidence(target, TonalContext(0, TonalMode.MAJOR))
        self.assertEqual(analyze_frame_exact(target), before)

    def test_rejects_untrusted_inputs(self):
        with self.assertRaises(TypeError):
            aggregate_frame_evidence(object())
        with self.assertRaises(TypeError):
            aggregate_frame_evidence(frame(48, 52, 55), object())


if __name__ == "__main__":
    unittest.main()
