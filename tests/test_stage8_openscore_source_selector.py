import unittest

from st_guitar_harmonic_engine.stage8_openscore_source_selector import (
    OpenScoreSourceSelectionError,
    describe_openscore_source,
    select_diversified_openscore_sources,
)


def _lieder_pool(composers=8, groups_per_composer=2):
    result = []
    counter = 1
    for composer in range(composers):
        for group in range(groups_per_composer):
            result.append(
                f"scores/Composer_{composer}/Cycle_{group}/Song_{counter}/lc{counter}.mscx"
            )
            counter += 1
    return tuple(result)


class Stage8OpenScoreSourceSelectorTests(unittest.TestCase):
    def test_selection_is_input_order_independent(self):
        pool = _lieder_pool()
        forward = select_diversified_openscore_sources(
            source_id="openscore-lieder",
            score_relative_paths=pool,
            requested_source_items=8,
        )
        reverse = select_diversified_openscore_sources(
            source_id="openscore-lieder",
            score_relative_paths=tuple(reversed(pool)),
            requested_source_items=8,
        )
        self.assertEqual(forward.selected, reverse.selected)
        self.assertEqual(forward.selection_sha256, reverse.selection_sha256)
        self.assertEqual(forward.distinct_source_group_count, 8)
        self.assertGreaterEqual(forward.distinct_composer_count, 7)
        self.assertFalse(forward.model_training_authorized)
        self.assertFalse(forward.production_authority_granted)

    def test_lieder_cycle_grouping_matches_miner_contract(self):
        first = describe_openscore_source(
            "openscore-lieder",
            "scores/Composer_A/Cycle_X/Song_1/lc1.mscx",
        )
        second = describe_openscore_source(
            "openscore-lieder",
            "scores/Composer_A/Cycle_X/Song_2/lc2.mscx",
        )
        third = describe_openscore_source(
            "openscore-lieder",
            "scores/Composer_A/Cycle_Y/Song_3/lc3.mscx",
        )
        self.assertEqual(first.source_group_id, second.source_group_id)
        self.assertNotEqual(first.source_group_id, third.source_group_id)

    def test_quartet_work_grouping_uses_parent_directory(self):
        first = describe_openscore_source(
            "openscore-string-quartets",
            "scores/Composer_A/Quartet_1/a.mscx",
        )
        second = describe_openscore_source(
            "openscore-string-quartets",
            "scores/Composer_A/Quartet_1/b.mscx",
        )
        other = describe_openscore_source(
            "openscore-string-quartets",
            "scores/Composer_A/Quartet_2/c.mscx",
        )
        self.assertEqual(first.source_group_id, second.source_group_id)
        self.assertNotEqual(first.source_group_id, other.source_group_id)

    def test_excluded_paths_and_groups_are_never_selected(self):
        pool = _lieder_pool(composers=9, groups_per_composer=2)
        excluded_path = pool[0]
        excluded_descriptor = describe_openscore_source("openscore-lieder", pool[1])
        result = select_diversified_openscore_sources(
            source_id="openscore-lieder",
            score_relative_paths=pool,
            requested_source_items=8,
            excluded_score_relative_paths=frozenset({excluded_path}),
            excluded_source_group_ids=frozenset({excluded_descriptor.source_group_id}),
        )
        selected_paths = {item.score_relative_path for item in result.selected}
        selected_groups = {item.source_group_id for item in result.selected}
        self.assertNotIn(excluded_path, selected_paths)
        self.assertNotIn(excluded_descriptor.source_group_id, selected_groups)

    def test_duplicate_source_path_fails_closed(self):
        path = "scores/Composer_A/Cycle_X/Song_1/lc1.mscx"
        with self.assertRaises(OpenScoreSourceSelectionError):
            select_diversified_openscore_sources(
                source_id="openscore-lieder",
                score_relative_paths=(path, path),
                requested_source_items=1,
            )

    def test_insufficient_composer_diversity_fails_closed(self):
        pool = _lieder_pool(composers=2, groups_per_composer=5)
        with self.assertRaises(OpenScoreSourceSelectionError):
            select_diversified_openscore_sources(
                source_id="openscore-lieder",
                score_relative_paths=pool,
                requested_source_items=7,
            )

    def test_one_score_per_source_group_is_enforced(self):
        pool = (
            "scores/Composer_A/Cycle_X/Song_1/lc1.mscx",
            "scores/Composer_A/Cycle_X/Song_2/lc2.mscx",
            "scores/Composer_B/Cycle_Y/Song_3/lc3.mscx",
        )
        with self.assertRaises(OpenScoreSourceSelectionError):
            select_diversified_openscore_sources(
                source_id="openscore-lieder",
                score_relative_paths=pool,
                requested_source_items=3,
            )

    def test_unsafe_path_fails_closed(self):
        with self.assertRaises(ValueError):
            describe_openscore_source(
                "openscore-lieder",
                "scores/Composer_A/../Cycle/Song/lc1.mscx",
            )


if __name__ == "__main__":
    unittest.main()
