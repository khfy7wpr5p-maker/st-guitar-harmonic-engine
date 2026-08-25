import unittest

from st_guitar_harmonic_engine.stage8_data_governance import (
    Stage8DataGovernanceStatus,
    Stage8DataSourceManifest,
    Stage8DatasetRole,
    Stage8LicenseClass,
    assess_stage8_data_governance,
)


A = "a" * 64
B = "b" * 64
C = "c" * 64
D = "d" * 64


def source(
    *,
    source_id="owned-synthetic-v1",
    role=Stage8DatasetRole.TRAIN_CANDIDATE,
    case_count=100,
    license_id="OWNER-TRAINING-GRANT",
    license_class=Stage8LicenseClass.OWNED,
    provenance_sha256=A,
    content_sha256=B,
    frozen_snapshot=True,
    training_rights_confirmed=True,
    commercial_use_allowed=True,
    teacher_gold_overlap_count=0,
    holdout_overlap_count=0,
    derived_from_holdout_labels=False,
    contains_personal_data=False,
):
    return Stage8DataSourceManifest(
        source_id=source_id,
        role=role,
        case_count=case_count,
        license_id=license_id,
        license_class=license_class,
        provenance_sha256=provenance_sha256,
        content_sha256=content_sha256,
        frozen_snapshot=frozen_snapshot,
        training_rights_confirmed=training_rights_confirmed,
        commercial_use_allowed=commercial_use_allowed,
        teacher_gold_overlap_count=teacher_gold_overlap_count,
        holdout_overlap_count=holdout_overlap_count,
        derived_from_holdout_labels=derived_from_holdout_labels,
        contains_personal_data=contains_personal_data,
    )


class Stage8DataGovernanceTests(unittest.TestCase):
    def test_empty_manifest_fails_closed(self):
        result = assess_stage8_data_governance(())
        self.assertIs(result.status, Stage8DataGovernanceStatus.BLOCKED_EMPTY_MANIFEST)
        self.assertFalse(result.model_training_authorized)
        self.assertFalse(result.production_authority_granted)

    def test_owned_frozen_disjoint_source_is_dataset_design_eligible_only(self):
        result = assess_stage8_data_governance((source(),))
        self.assertIs(result.status, Stage8DataGovernanceStatus.DATASET_DESIGN_ELIGIBLE)
        self.assertEqual(result.reasons, ())
        self.assertEqual(result.training_candidate_case_count, 100)
        self.assertFalse(result.model_training_authorized)
        self.assertFalse(result.production_authority_granted)

    def test_noncommercial_training_candidate_is_blocked(self):
        item = source(
            license_id="CC-BY-NC-SA-4.0",
            license_class=Stage8LicenseClass.NONCOMMERCIAL,
            training_rights_confirmed=False,
            commercial_use_allowed=False,
        )
        result = assess_stage8_data_governance((item,))
        self.assertIs(result.status, Stage8DataGovernanceStatus.BLOCKED_RIGHTS)
        self.assertIn("owned-synthetic-v1:license_not_training_eligible", result.reasons)
        self.assertIn("owned-synthetic-v1:commercial_use_not_allowed", result.reasons)

    def test_noncommercial_reference_only_source_does_not_poison_valid_training_source(self):
        training = source()
        reference = source(
            source_id="external-reference-v1",
            role=Stage8DatasetRole.REFERENCE_ONLY,
            case_count=50,
            license_id="CC-BY-NC-SA-4.0",
            license_class=Stage8LicenseClass.NONCOMMERCIAL,
            provenance_sha256=C,
            content_sha256=D,
            training_rights_confirmed=False,
            commercial_use_allowed=False,
        )
        result = assess_stage8_data_governance((training, reference))
        self.assertIs(result.status, Stage8DataGovernanceStatus.DATASET_DESIGN_ELIGIBLE)
        self.assertEqual(result.reference_only_case_count, 50)
        self.assertFalse(result.model_training_authorized)

    def test_teacher_gold_and_holdout_leakage_blocks_before_rights(self):
        leaked = source(
            license_class=Stage8LicenseClass.UNKNOWN,
            license_id="UNKNOWN",
            training_rights_confirmed=False,
            commercial_use_allowed=False,
            teacher_gold_overlap_count=1,
            holdout_overlap_count=1,
            derived_from_holdout_labels=True,
        )
        result = assess_stage8_data_governance((leaked,))
        self.assertIs(result.status, Stage8DataGovernanceStatus.BLOCKED_DATA_LEAKAGE)
        self.assertEqual(
            result.reasons,
            (
                "owned-synthetic-v1:derived_from_holdout_labels",
                "owned-synthetic-v1:holdout_overlap",
                "owned-synthetic-v1:teacher_gold_overlap",
            ),
        )

    def test_personal_data_blocks_manifest(self):
        result = assess_stage8_data_governance((source(contains_personal_data=True),))
        self.assertIs(result.status, Stage8DataGovernanceStatus.BLOCKED_PRIVACY_RISK)

    def test_duplicate_source_id_or_content_snapshot_fails_integrity(self):
        first = source()
        duplicate_content = source(
            source_id="second-source-v1",
            provenance_sha256=C,
            content_sha256=B,
        )
        result = assess_stage8_data_governance((first, duplicate_content))
        self.assertIs(result.status, Stage8DataGovernanceStatus.BLOCKED_INTEGRITY)

    def test_unfrozen_or_empty_source_fails_integrity(self):
        item = source(case_count=0, frozen_snapshot=False)
        result = assess_stage8_data_governance((item,))
        self.assertIs(result.status, Stage8DataGovernanceStatus.BLOCKED_INTEGRITY)
        self.assertEqual(
            result.reasons,
            (
                "owned-synthetic-v1:empty_source",
                "owned-synthetic-v1:snapshot_not_frozen",
            ),
        )

    def test_reference_only_manifest_cannot_become_training_design(self):
        item = source(role=Stage8DatasetRole.REFERENCE_ONLY)
        result = assess_stage8_data_governance((item,))
        self.assertIs(result.status, Stage8DataGovernanceStatus.BLOCKED_RIGHTS)
        self.assertEqual(result.reasons, ("no_training_candidate_source",))


if __name__ == "__main__":
    unittest.main()
