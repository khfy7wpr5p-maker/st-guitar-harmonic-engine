import unittest

from st_guitar_harmonic_engine.context import TonalContext, TonalMode
from st_guitar_harmonic_engine.local_context import (
    LocalTonalContextPlan,
    LocalTonalContextSpan,
)


class LocalTonalContextTests(unittest.TestCase):
    def test_explicit_spans_support_local_key_change_without_inference(self):
        c_major = TonalContext(0, TonalMode.MAJOR)
        a_minor = TonalContext(9, TonalMode.MINOR)
        plan = LocalTonalContextPlan(
            (
                LocalTonalContextSpan(0, 2, c_major),
                LocalTonalContextSpan(2, 4, a_minor),
            )
        )
        self.assertEqual(plan.contexts_for(4), (c_major, c_major, a_minor, a_minor))

    def test_uncovered_frames_remain_unknown(self):
        c_major = TonalContext(0, TonalMode.MAJOR)
        plan = LocalTonalContextPlan((LocalTonalContextSpan(1, 2, c_major),))
        self.assertEqual(plan.contexts_for(3), (None, c_major, None))

    def test_overlapping_spans_are_rejected(self):
        c_major = TonalContext(0, TonalMode.MAJOR)
        with self.assertRaises(ValueError):
            LocalTonalContextPlan(
                (
                    LocalTonalContextSpan(0, 2, c_major),
                    LocalTonalContextSpan(1, 3, c_major),
                )
            )

    def test_unsorted_spans_are_rejected(self):
        c_major = TonalContext(0, TonalMode.MAJOR)
        with self.assertRaises(ValueError):
            LocalTonalContextPlan(
                (
                    LocalTonalContextSpan(2, 3, c_major),
                    LocalTonalContextSpan(0, 1, c_major),
                )
            )

    def test_plan_cannot_extend_beyond_frame_count(self):
        plan = LocalTonalContextPlan(
            (LocalTonalContextSpan(0, 3, TonalContext(0, TonalMode.MAJOR)),)
        )
        with self.assertRaises(ValueError):
            plan.contexts_for(2)

    def test_repeated_lookup_is_deterministic(self):
        plan = LocalTonalContextPlan(
            (LocalTonalContextSpan(0, 2, TonalContext(0, TonalMode.MAJOR)),)
        )
        expected = plan.contexts_for(3)
        for _ in range(10):
            self.assertEqual(plan.contexts_for(3), expected)

    def test_invalid_indices_and_contexts_are_rejected(self):
        with self.assertRaises(ValueError):
            LocalTonalContextSpan(-1, 1, TonalContext(0, TonalMode.MAJOR))
        with self.assertRaises(TypeError):
            LocalTonalContextSpan(0, 1, object())
        plan = LocalTonalContextPlan(())
        with self.assertRaises(ValueError):
            plan.context_at(-1)


if __name__ == "__main__":
    unittest.main()
