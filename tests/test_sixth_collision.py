import unittest

from st_guitar_harmonic_engine.resolver import EvidenceSource
from st_guitar_harmonic_engine.sixth_collision import (
    SIXTH_COLLISION_CONTRACT_VERSION,
    SIXTH_COLLISION_PERMITTED_DISAMBIGUATORS,
    SixthChordKind,
    SixthCollisionDisposition,
    assess_sixth_collision_evidence,
    build_sixth_chord_collision,
)


class SixthChordCollisionTests(unittest.TestCase):
    def test_contract_version_is_explicit(self):
        self.assertEqual(SIXTH_COLLISION_CONTRACT_VERSION, "0.1")

    def test_major_sixth_matches_relative_minor_seventh_pitch_set(self):
        collision = build_sixth_chord_collision(0, SixthChordKind.MAJOR_SIXTH)
        self.assertEqual(collision.pitch_classes, (0, 4, 7, 9))
        self.assertEqual(collision.competing_root_pc, 9)
        self.assertEqual(collision.competing_variant, "minor_seventh")

    def test_minor_sixth_matches_relative_half_diminished_seventh_pitch_set(self):
        collision = build_sixth_chord_collision(0, SixthChordKind.MINOR_SIXTH)
        self.assertEqual(collision.pitch_classes, (0, 3, 7, 9))
        self.assertEqual(collision.competing_root_pc, 9)
        self.assertEqual(collision.competing_variant, "half_diminished_seventh")

    def test_collision_transposes_deterministically_for_all_roots(self):
        for root in range(12):
            with self.subTest(root=root):
                major = build_sixth_chord_collision(root, SixthChordKind.MAJOR_SIXTH)
                minor = build_sixth_chord_collision(root, SixthChordKind.MINOR_SIXTH)
                self.assertEqual(major.competing_root_pc, (root + 9) % 12)
                self.assertEqual(minor.competing_root_pc, (root + 9) % 12)
                self.assertEqual(
                    major,
                    build_sixth_chord_collision(root, SixthChordKind.MAJOR_SIXTH),
                )
                self.assertEqual(
                    minor,
                    build_sixth_chord_collision(root, SixthChordKind.MINOR_SIXTH),
                )

    def test_only_tonal_context_is_currently_permitted_for_future_disambiguation(self):
        self.assertEqual(
            SIXTH_COLLISION_PERMITTED_DISAMBIGUATORS,
            (EvidenceSource.TONAL_CONTEXT,),
        )

    def test_bass_structure_spelling_adjacent_and_voice_evidence_cannot_authorize_root_choice(self):
        weak_or_non_disambiguating = (
            EvidenceSource.STRUCTURAL,
            EvidenceSource.BASS_INVERSION,
            EvidenceSource.VERIFIED_NCT,
            EvidenceSource.COLOR_TONE,
            EvidenceSource.ADJACENT_CONTEXT,
            EvidenceSource.VOICE_FUNCTION,
        )
        self.assertIs(
            assess_sixth_collision_evidence(weak_or_non_disambiguating),
            SixthCollisionDisposition.PRESERVE_AMBIGUITY,
        )

    def test_explicit_tonal_context_only_makes_case_eligible_not_resolved(self):
        self.assertIs(
            assess_sixth_collision_evidence((EvidenceSource.TONAL_CONTEXT,)),
            SixthCollisionDisposition.CONTEXT_ELIGIBLE,
        )
        self.assertNotEqual(
            SixthCollisionDisposition.CONTEXT_ELIGIBLE.value,
            "resolved",
        )

    def test_empty_evidence_preserves_ambiguity(self):
        self.assertIs(
            assess_sixth_collision_evidence(()),
            SixthCollisionDisposition.PRESERVE_AMBIGUITY,
        )

    def test_invalid_inputs_fail_closed(self):
        for invalid_root in (-1, 12, True, 1.5):
            with self.subTest(root=invalid_root):
                with self.assertRaises((TypeError, ValueError)):
                    build_sixth_chord_collision(invalid_root, SixthChordKind.MAJOR_SIXTH)

        with self.assertRaises(TypeError):
            build_sixth_chord_collision(0, "major_sixth")
        with self.assertRaises(TypeError):
            assess_sixth_collision_evidence([EvidenceSource.TONAL_CONTEXT])
        with self.assertRaises(ValueError):
            assess_sixth_collision_evidence(
                (EvidenceSource.TONAL_CONTEXT, EvidenceSource.TONAL_CONTEXT)
            )


if __name__ == "__main__":
    unittest.main()
