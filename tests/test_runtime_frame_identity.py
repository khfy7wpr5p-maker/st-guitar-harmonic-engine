import unittest

from st_guitar_harmonic_engine.frames import HarmonicFrame
from st_guitar_harmonic_engine.models import NoteEvent, RationalBeat, TieState
from st_guitar_harmonic_engine.public_api import PublicRequestMode, ValidatedPublicRequest
from st_guitar_harmonic_engine.runtime_frame_identity import (
    RUNTIME_FRAME_ID_PREFIX,
    RUNTIME_FRAME_TRACE_SCHEMA_NAME,
    build_runtime_frame_identity_trace,
    canonical_runtime_frame_identity_payload,
    runtime_frame_id,
)


SOURCE_A = "a" * 64
SOURCE_B = "b" * 64


def _event(*, pitch: int, voice: int = 1, duration: int = 2) -> NoteEvent:
    return NoteEvent(
        measure_number=1,
        staff=1,
        voice=voice,
        midi_pitch=pitch,
        onset=RationalBeat(0),
        duration=RationalBeat(duration),
        tie=TieState.NONE,
    )


def _frame(events=None, *, end=1) -> HarmonicFrame:
    events = tuple(events or (_event(pitch=60), _event(pitch=64, voice=2)))
    return HarmonicFrame(
        measure_number=1,
        start=RationalBeat(0),
        end=RationalBeat(end),
        events=events,
    )


class RuntimeFrameIdentityTests(unittest.TestCase):
    def test_identity_is_stable_across_event_tuple_order(self):
        first = _event(pitch=60)
        second = _event(pitch=64, voice=2)
        left = _frame((first, second))
        right = _frame((second, first))
        self.assertEqual(
            runtime_frame_id(left, source_sha256=SOURCE_A),
            runtime_frame_id(right, source_sha256=SOURCE_A),
        )

    def test_identity_is_scoped_by_source_digest(self):
        frame = _frame()
        self.assertNotEqual(
            runtime_frame_id(frame, source_sha256=SOURCE_A),
            runtime_frame_id(frame, source_sha256=SOURCE_B),
        )

    def test_identity_changes_when_exact_frame_content_changes(self):
        original = _frame()
        changed = _frame((_event(pitch=60), _event(pitch=65, voice=2)))
        self.assertNotEqual(
            runtime_frame_id(original, source_sha256=SOURCE_A),
            runtime_frame_id(changed, source_sha256=SOURCE_A),
        )

    def test_identity_has_frozen_prefix_and_sha256_length(self):
        value = runtime_frame_id(_frame(), source_sha256=SOURCE_A)
        self.assertTrue(value.startswith(RUNTIME_FRAME_ID_PREFIX))
        self.assertEqual(len(value.removeprefix(RUNTIME_FRAME_ID_PREFIX)), 64)

    def test_source_digest_is_normalized_to_lowercase(self):
        payload = canonical_runtime_frame_identity_payload(
            _frame(), source_sha256="A" * 64
        )
        self.assertEqual(payload["source_sha256"], SOURCE_A)

    def test_invalid_source_digest_fails_closed(self):
        for invalid in ("", "a" * 63, "g" * 64):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    runtime_frame_id(_frame(), source_sha256=invalid)
        with self.assertRaises(TypeError):
            runtime_frame_id(_frame(), source_sha256=123)  # type: ignore[arg-type]

    def test_trace_contains_only_join_metadata_and_safety_flags(self):
        frame = _frame()
        request = ValidatedPublicRequest(PublicRequestMode.BATCH, (frame,), None)
        trace = build_runtime_frame_identity_trace(request, source_sha256=SOURCE_A)

        self.assertEqual(trace["schema_name"], RUNTIME_FRAME_TRACE_SCHEMA_NAME)
        self.assertEqual(trace["identity_role"], "JOIN_KEY_NOT_MODEL_FEATURE")
        self.assertFalse(trace["contains_harmonic_decision"])
        self.assertFalse(trace["contains_teacher_or_target_label"])
        self.assertFalse(trace["contains_future_or_next_context"])
        self.assertFalse(trace["model_feature_authority"])
        self.assertFalse(trace["production_authority"])
        self.assertTrue(trace["deterministic_resolver_authority_unchanged"])
        self.assertEqual(
            trace["entries"][0]["runtime_frame_id"],
            runtime_frame_id(frame, source_sha256=SOURCE_A),
        )
        self.assertEqual(
            set(trace["entries"][0]),
            {"frame_index", "runtime_frame_id", "measure_number", "start", "end"},
        )

    def test_trace_rejects_duplicate_frame_identity(self):
        frame = _frame()
        request = ValidatedPublicRequest(PublicRequestMode.BATCH, (frame, frame), None)
        with self.assertRaises(ValueError):
            build_runtime_frame_identity_trace(request, source_sha256=SOURCE_A)

    def test_trace_requires_validated_request(self):
        with self.assertRaises(TypeError):
            build_runtime_frame_identity_trace(object(), source_sha256=SOURCE_A)  # type: ignore[arg-type]

    def test_canonical_payload_contains_no_harmonic_answer_fields(self):
        payload = canonical_runtime_frame_identity_payload(_frame(), source_sha256=SOURCE_A)
        serialized_keys = set(payload) | set(payload["frame"])
        forbidden = {"decision", "function", "roman", "label", "target", "next"}
        self.assertTrue(forbidden.isdisjoint(serialized_keys))


if __name__ == "__main__":
    unittest.main()
