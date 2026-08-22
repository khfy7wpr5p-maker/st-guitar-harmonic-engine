import unittest

from st_guitar_harmonic_engine import (
    AlterationKind,
    CandidateFamily,
    ChordQuality,
    EvidenceSource,
    ExtensionKind,
    HarmonicFrame,
    HarmonicIdentity,
    NoteEvent,
    PhrasePlan,
    PhraseSpan,
    RationalBeat,
    ResolverCandidate,
    ResolverDecision,
    ResolverStatus,
    SuspendedChordKind,
    generate_altered_tension_candidates,
    generate_extension_candidates,
    generate_suspended_chord_candidates,
    phrase_bounded_neighbors,
    resolve_candidates_by_precedence,
)
from st_guitar_harmonic_engine.abstention import (
    AbstentionReason,
    FinalDecisionState,
    apply_abstention_policy,
)
from st_guitar_harmonic_engine.guitar_voicing import (
    CandidateBassRelation,
    ContextualBassState,
    GuitarStringObservation,
    GuitarStringState,
    build_guitar_voicing_evidence,
    describe_bass_against_candidate,
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
        )
        for index, pitch in enumerate(pitches)
    )
    return HarmonicFrame(1, RationalBeat(0), RationalBeat(1), events)


def candidate(root, family, variant, *evidence):
    return ResolverCandidate(
        HarmonicIdentity(root, family, variant),
        tuple(evidence),
    )


def sounding(string_number, fret, midi_pitch):
    return GuitarStringObservation(
        string_number,
        GuitarStringState.SOUNDING,
        fret,
        midi_pitch,
    )


class GuitarAmbiguityRegressionTests(unittest.TestCase):
    def test_add9_surface_is_extension_evidence(self):
        candidates = generate_extension_candidates(frame(48, 50, 52, 55))
        self.assertTrue(any(
            item.root_pc == 0
            and item.base_quality is ChordQuality.MAJOR
            and item.extension is ExtensionKind.NATURAL_NINTH
            for item in candidates
        ))

    def test_sus_surface_preserves_multiple_interpretations(self):
        candidates = generate_suspended_chord_candidates(frame(48, 50, 55))
        self.assertGreaterEqual(len(candidates), 2)
        self.assertTrue(any(
            item.root_pc == 0 and item.kind is SuspendedChordKind.SUS2
            for item in candidates
        ))
        self.assertEqual(candidates, generate_suspended_chord_candidates(frame(48, 50, 55)))

    def test_flat_ninth_surface_is_altered_evidence(self):
        candidates = generate_altered_tension_candidates(frame(48, 49, 52, 55, 58))
        self.assertTrue(any(
            item.root_pc == 0
            and item.base_quality is ChordQuality.DOMINANT_SEVENTH
            and item.alteration is AlterationKind.FLAT_NINTH
            for item in candidates
        ))

    def test_c6_vs_am7_over_c_policy_preserves_ambiguity(self):
        c6 = candidate(
            0,
            CandidateFamily.EXTENSION,
            "major:sixth",
            EvidenceSource.STRUCTURAL,
            EvidenceSource.BASS_INVERSION,
        )
        am7 = candidate(
            9,
            CandidateFamily.BASIC,
            ChordQuality.MINOR_SEVENTH.value,
            EvidenceSource.STRUCTURAL,
            EvidenceSource.BASS_INVERSION,
        )
        result = resolve_candidates_by_precedence((am7, c6))
        self.assertIs(result.status, ResolverStatus.AMBIGUOUS)
        self.assertEqual(set(result.candidates), {c6, am7})

    def test_add9_vs_unverified_nct_policy_preserves_ambiguity(self):
        add9 = candidate(
            0,
            CandidateFamily.EXTENSION,
            "major:natural_ninth",
            EvidenceSource.COLOR_TONE,
        )
        c_with_unverified_d = candidate(
            0,
            CandidateFamily.BASIC,
            ChordQuality.MAJOR.value,
            EvidenceSource.COLOR_TONE,
        )
        result = resolve_candidates_by_precedence((add9, c_with_unverified_d))
        self.assertIs(result.status, ResolverStatus.AMBIGUOUS)

    def test_verified_nct_precedence_can_narrow_add9_conflict(self):
        add9 = candidate(
            0,
            CandidateFamily.EXTENSION,
            "major:natural_ninth",
            EvidenceSource.COLOR_TONE,
        )
        verified_nct = candidate(
            0,
            CandidateFamily.BASIC,
            ChordQuality.MAJOR.value,
            EvidenceSource.VERIFIED_NCT,
            EvidenceSource.COLOR_TONE,
        )
        result = resolve_candidates_by_precedence((add9, verified_nct))
        self.assertIs(result.status, ResolverStatus.RESOLVED)
        self.assertEqual(result.candidates, (verified_nct,))

    def test_sus_vs_unverified_nct_policy_preserves_ambiguity(self):
        sus = candidate(
            0,
            CandidateFamily.SUSPENDED,
            SuspendedChordKind.SUS4.value,
            EvidenceSource.COLOR_TONE,
        )
        nct_like = candidate(
            0,
            CandidateFamily.BASIC,
            ChordQuality.MAJOR.value,
            EvidenceSource.COLOR_TONE,
        )
        self.assertIs(
            resolve_candidates_by_precedence((nct_like, sus)).status,
            ResolverStatus.AMBIGUOUS,
        )

    def test_equal_altered_hypotheses_preserve_ambiguity(self):
        left = candidate(
            0,
            CandidateFamily.ALTERED,
            "dominant_seventh:flat_ninth",
            EvidenceSource.COLOR_TONE,
        )
        right = candidate(
            0,
            CandidateFamily.ALTERED,
            "dominant_seventh:sharp_ninth",
            EvidenceSource.COLOR_TONE,
        )
        result = resolve_candidates_by_precedence((right, left))
        self.assertIs(result.status, ResolverStatus.AMBIGUOUS)

    def test_bass_only_hypotheses_do_not_create_certainty(self):
        left = candidate(
            0,
            CandidateFamily.BASIC,
            ChordQuality.MAJOR.value,
            EvidenceSource.BASS_INVERSION,
        )
        right = candidate(
            9,
            CandidateFamily.BASIC,
            ChordQuality.MINOR_SEVENTH.value,
            EvidenceSource.BASS_INVERSION,
        )
        self.assertIs(
            resolve_candidates_by_precedence((right, left)).status,
            ResolverStatus.AMBIGUOUS,
        )
        gated = apply_abstention_policy(
            ResolverDecision(ResolverStatus.RESOLVED, (left,))
        )
        self.assertIs(gated.state, FinalDecisionState.ABSTAIN)
        self.assertIs(gated.abstention_reason, AbstentionReason.WEAK_EVIDENCE)

    def test_open_string_pedal_observation_is_non_authoritative(self):
        harmonic = candidate(
            0,
            CandidateFamily.BASIC,
            ChordQuality.MAJOR.value,
            EvidenceSource.EXACT,
        )
        decision = ResolverDecision(ResolverStatus.RESOLVED, (harmonic,))
        voicing = build_guitar_voicing_evidence(
            (
                sounding(6, 0, 38),
                sounding(5, 3, 48),
                sounding(4, 2, 52),
                sounding(3, 0, 55),
            )
        )
        bass = describe_bass_against_candidate(
            voicing,
            root_pc=0,
            candidate_pitch_classes=(0, 4, 7),
            pedal_bass_state=ContextualBassState.POSSIBLE,
        )
        self.assertIs(bass.candidate_relation, CandidateBassRelation.OUTSIDE_CANDIDATE)
        self.assertIs(bass.pedal_bass_state, ContextualBassState.POSSIBLE)
        self.assertEqual(decision.candidates, (harmonic,))

    def test_phrase_boundaries_block_neighbor_leakage(self):
        first = (candidate(0, CandidateFamily.BASIC, "major", EvidenceSource.EXACT),)
        second = (candidate(7, CandidateFamily.BASIC, "major", EvidenceSource.EXACT),)
        third = (candidate(0, CandidateFamily.BASIC, "major", EvidenceSource.EXACT),)
        sequence = (first, second, third)
        plan = PhrasePlan((PhraseSpan(0, 1), PhraseSpan(1, 3)))

        self.assertEqual(phrase_bounded_neighbors(sequence, 0, plan), ((), ()))
        self.assertEqual(phrase_bounded_neighbors(sequence, 1, plan), ((), third))

    def test_candidate_order_and_repeated_runs_are_stable(self):
        values = (
            candidate(0, CandidateFamily.EXTENSION, "major:sixth", EvidenceSource.STRUCTURAL),
            candidate(9, CandidateFamily.BASIC, "minor_seventh", EvidenceSource.STRUCTURAL),
            candidate(7, CandidateFamily.BASIC, "major", EvidenceSource.VOICE_FUNCTION),
        )
        expected = resolve_candidates_by_precedence(values)
        self.assertEqual(resolve_candidates_by_precedence(tuple(reversed(values))), expected)
        for _ in range(20):
            self.assertEqual(resolve_candidates_by_precedence(values), expected)


if __name__ == "__main__":
    unittest.main()
