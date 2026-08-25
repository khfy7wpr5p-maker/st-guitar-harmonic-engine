import unittest

from st_guitar_harmonic_engine.stage8_openscore_snapshot import (
    OpenScoreRepositorySnapshot,
    OpenScoreSnapshotStatus,
    assess_openscore_snapshots,
    canonical_openscore_snapshots,
)


class Stage8OpenScoreSnapshotTests(unittest.TestCase):
    def test_canonical_live_verified_snapshots_are_frozen(self):
        snapshots = canonical_openscore_snapshots()
        result = assess_openscore_snapshots(snapshots)
        self.assertIs(result.status, OpenScoreSnapshotStatus.SNAPSHOT_PLAN_FROZEN)
        self.assertEqual(result.source_count, 2)
        self.assertFalse(result.model_training_authorized)
        self.assertFalse(result.production_authority_granted)

    def test_pins_expected_external_commits_and_cc0_license_blob(self):
        by_id = {item.source_id: item for item in canonical_openscore_snapshots()}
        self.assertEqual(
            by_id["openscore-string-quartets"].commit_sha,
            "91c780acf1502e7b4f745dc100836c501f41d8e3",
        )
        self.assertEqual(
            by_id["openscore-lieder"].commit_sha,
            "6b2dc542ce2e8aa4b78c8ee62103b210efc07015",
        )
        self.assertEqual(
            {item.license_blob_sha for item in by_id.values()},
            {"0e259d42c996742e9e3cba14c677129b2c1b6311"},
        )
        self.assertEqual({item.license_id for item in by_id.values()}, {"CC0-1.0"})

    def test_missing_source_fails_closed(self):
        result = assess_openscore_snapshots(canonical_openscore_snapshots()[:1])
        self.assertIs(result.status, OpenScoreSnapshotStatus.BLOCKED_SOURCE_SET)

    def test_commit_drift_fails_closed(self):
        original = canonical_openscore_snapshots()
        first = original[0]
        drifted = OpenScoreRepositorySnapshot(
            source_id=first.source_id,
            repository=first.repository,
            commit_sha="a" * 40,
            license_path=first.license_path,
            license_blob_sha=first.license_blob_sha,
            license_id=first.license_id,
            score_root=first.score_root,
            source_extension=first.source_extension,
            conversion_extension=first.conversion_extension,
            frozen_snapshot=first.frozen_snapshot,
            training_rights_confirmed=first.training_rights_confirmed,
            commercial_use_allowed=first.commercial_use_allowed,
        )
        result = assess_openscore_snapshots((drifted,) + original[1:])
        self.assertIs(result.status, OpenScoreSnapshotStatus.BLOCKED_INTEGRITY)
        self.assertIn(f"{first.source_id}:snapshot_metadata_drift", result.reasons)

    def test_unfrozen_snapshot_fails_closed(self):
        original = canonical_openscore_snapshots()
        first = original[0]
        drifted = OpenScoreRepositorySnapshot(
            source_id=first.source_id,
            repository=first.repository,
            commit_sha=first.commit_sha,
            license_path=first.license_path,
            license_blob_sha=first.license_blob_sha,
            license_id=first.license_id,
            score_root=first.score_root,
            source_extension=first.source_extension,
            conversion_extension=first.conversion_extension,
            frozen_snapshot=False,
            training_rights_confirmed=first.training_rights_confirmed,
            commercial_use_allowed=first.commercial_use_allowed,
        )
        result = assess_openscore_snapshots((drifted,) + original[1:])
        self.assertIs(result.status, OpenScoreSnapshotStatus.BLOCKED_INTEGRITY)

    def test_invalid_format_boundary_is_rejected_at_construction(self):
        with self.assertRaises(ValueError):
            OpenScoreRepositorySnapshot(
                source_id="openscore-test",
                repository="OpenScore/Test",
                commit_sha="a" * 40,
                license_path="LICENSE.txt",
                license_blob_sha="b" * 40,
                license_id="CC0-1.0",
                score_root="scores",
                source_extension=".pdf",
                conversion_extension=".mxl",
                frozen_snapshot=True,
                training_rights_confirmed=True,
                commercial_use_allowed=True,
            )


if __name__ == "__main__":
    unittest.main()
