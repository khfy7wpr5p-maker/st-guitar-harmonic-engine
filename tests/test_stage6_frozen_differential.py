import unittest

from st_guitar_harmonic_engine.abstention import FinalDecisionState, apply_abstention_policy
from st_guitar_harmonic_engine.aggregator import aggregate_frame_evidence
from st_guitar_harmonic_engine.frames import HarmonicFrame
from st_guitar_harmonic_engine.models import NoteEvent, RationalBeat
from st_guitar_harmonic_engine.resolver import (
    CandidateFamily,
    EvidenceSource,
    HarmonicIdentity,
    ResolverCandidate,
    ResolverStatus,
)
from st_guitar_harmonic_engine.sequence import resolve_candidates_by_precedence


FROZEN_STAGE6_MAIN_SHA = "c2df9d09d3e2c84a9ea203f8567ec5e48eeab3ea"


def event(pitch, voice=1):
    return NoteEvent(
        measure_number=1,
        staff=1,
        voice=voice,
        midi_pitch=pitch,
        onset=RationalBeat(0),
        duration=RationalBeat(1),
    )


def frame(*pitches):
    events = tuple(event(pitch, index + 1) for index, pitch in enumerate(pitches))
    return HarmonicFrame(1, RationalBeat(0), RationalBeat(1), events)


def candidate(root, evidence, variant="major"):
    return ResolverCandidate(
        HarmonicIdentity(root, CandidateFamily.BASIC, variant),
        evidence,
    )


class FrozenStage6DifferentialTests(unittest.TestCase):
    def test_frozen_reference_sha_is_explicit(self):
        self.assertEqual(
            FROZEN_STAGE6_MAIN_SHA,
            "c2df9d09d3e2c84a9ea203f8567ec5e48eeab3ea",
        )

    def test_exact_c_major_semantics_match_stage6_baseline(self):
        candidates = aggregate_frame_evidence(frame(60, 64, 67))
        self.assertEqual(len(candidates), 1)
        current = candidates[0]
        self.assertEqual(
            (
                current.identity.root_pc,
                current.identity.family.value,
                current.identity.variant,
                tuple(item.value for item in current.evidence),
            ),
            (0, "basic", "major", ("exact", "bass_inversion")),
        )
        source = resolve_candidates_by_precedence(candidates)
        gated = apply_abstention_policy(source)
        self.assertIs(source.status, ResolverStatus.RESOLVED)
        self.assertIs(gated.state, FinalDecisionState.RESOLVED)
        self.assertEqual(gated.confidence.state.value, "strong")

    def test_exact_diminished_seventh_ambiguity_matches_stage6_baseline(self):
        candidates = aggregate_frame_evidence(frame(60, 63, 66, 69))
        self.assertEqual(
            tuple((item.identity.root_pc, item.identity.variant) for item in candidates),
            ((0, "diminished_seventh"), (3, "diminished_seventh"), (6, "diminished_seventh"), (9, "diminished_seventh")),
        )
        source = resolve_candidates_by_precedence(candidates)
        gated = apply_abstention_policy(source)
        self.assertIs(source.status, ResolverStatus.AMBIGUOUS)
        self.assertIs(gated.state, FinalDecisionState.AMBIGUOUS)

    def test_bass_only_candidate_remains_abstained_as_stage6_hardening(self):
        current = candidate(0, (EvidenceSource.BASS_INVERSION,))
        source = resolve_candidates_by_precedence((current,))
        gated = apply_abstention_policy(source)
        self.assertIs(source.status, ResolverStatus.RESOLVED)
        self.assertIs(gated.state, FinalDecisionState.ABSTAIN)
        self.assertEqual(gated.confidence.state.value, "weak")

    def test_omission_only_candidate_remains_abstained(self):
        current = candidate(0, (EvidenceSource.INCOMPLETE_CHORD,))
        gated = apply_abstention_policy(resolve_candidates_by_precedence((current,)))
        self.assertIs(gated.state, FinalDecisionState.ABSTAIN)
        self.assertEqual(gated.confidence.state.value, "weak")

    def test_exact_precedence_still_wins_over_lower_evidence(self):
        exact = candidate(0, (EvidenceSource.EXACT,))
        structural = candidate(7, (EvidenceSource.STRUCTURAL,))
        decision = resolve_candidates_by_precedence((structural, exact))
        self.assertIs(decision.status, ResolverStatus.RESOLVED)
        self.assertEqual(decision.candidates, (exact,))

    def test_repeated_runs_and_input_order_do_not_drift(self):
        exact = candidate(0, (EvidenceSource.EXACT,))
        structural = candidate(7, (EvidenceSource.STRUCTURAL,))
        expected = resolve_candidates_by_precedence((exact, structural))
        self.assertEqual(resolve_candidates_by_precedence((structural, exact)), expected)
        for _ in range(20):
            self.assertEqual(resolve_candidates_by_precedence((exact, structural)), expected)


if __name__ == "__main__":
    unittest.main()
