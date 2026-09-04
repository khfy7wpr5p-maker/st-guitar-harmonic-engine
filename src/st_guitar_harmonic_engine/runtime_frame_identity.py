"""Stage 2-N exact runtime-frame identity bridge.

This module creates a stable join key for one deterministic runtime frame. The
key is metadata only: it is not a model feature, carries no harmonic answer, and
grants no production authority.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .frames import HarmonicFrame
from .public_api import ValidatedPublicRequest


RUNTIME_FRAME_IDENTITY_SCHEMA_NAME = "st_guitar_harmonic_engine.runtime_frame_identity"
RUNTIME_FRAME_IDENTITY_SCHEMA_VERSION = "1.0"
RUNTIME_FRAME_TRACE_SCHEMA_NAME = "st_guitar_harmonic_engine.runtime_frame_identity_trace"
RUNTIME_FRAME_TRACE_SCHEMA_VERSION = "1.0"
RUNTIME_FRAME_ID_PREFIX = "st-rfi-v1:"


def _normalize_source_sha256(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("source_sha256 must be a string")
    normalized = value.lower()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise ValueError("source_sha256 must be exactly 64 hexadecimal characters")
    return normalized


def _beat_payload(beat) -> dict[str, int]:
    return {"numerator": beat.numerator, "denominator": beat.denominator}


def _event_payload(event) -> dict[str, Any]:
    return {
        "measure_number": event.measure_number,
        "staff": event.staff,
        "voice": event.voice,
        "midi_pitch": event.midi_pitch,
        "onset": _beat_payload(event.onset),
        "duration": _beat_payload(event.duration),
        "tie": event.tie.value,
    }


def _event_sort_key(payload: dict[str, Any]) -> tuple[object, ...]:
    return (
        payload["measure_number"],
        payload["staff"],
        payload["voice"],
        payload["midi_pitch"],
        payload["onset"]["numerator"],
        payload["onset"]["denominator"],
        payload["duration"]["numerator"],
        payload["duration"]["denominator"],
        payload["tie"],
    )


def canonical_runtime_frame_identity_payload(
    frame: HarmonicFrame,
    *,
    source_sha256: str,
) -> dict[str, Any]:
    """Return the exact canonical current-frame payload used only for identity.

    ``source_sha256`` must identify the immutable symbolic source presented to the
    runtime adapter. It prevents identical musical frames from different works
    from sharing one join key.
    """

    if not isinstance(frame, HarmonicFrame):
        raise TypeError("frame must be a HarmonicFrame")
    source_sha256 = _normalize_source_sha256(source_sha256)
    events = sorted((_event_payload(event) for event in frame.events), key=_event_sort_key)
    return {
        "schema_name": RUNTIME_FRAME_IDENTITY_SCHEMA_NAME,
        "schema_version": RUNTIME_FRAME_IDENTITY_SCHEMA_VERSION,
        "source_sha256": source_sha256,
        "frame": {
            "measure_number": frame.measure_number,
            "start": _beat_payload(frame.start),
            "end": _beat_payload(frame.end),
            "events": events,
        },
    }


def runtime_frame_id(frame: HarmonicFrame, *, source_sha256: str) -> str:
    """Return a stable SHA-256 join key for one exact current runtime frame."""

    payload = canonical_runtime_frame_identity_payload(frame, source_sha256=source_sha256)
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return RUNTIME_FRAME_ID_PREFIX + hashlib.sha256(encoded).hexdigest()


def build_runtime_frame_identity_trace(
    request: ValidatedPublicRequest,
    *,
    source_sha256: str,
) -> dict[str, Any]:
    """Build a decision-free sidecar trace for a validated runtime request.

    The trace is deliberately unsuitable as a model feature surface. It exposes
    only exact frame join identities plus current musical coordinates needed to
    audit alignment. It contains no resolver decision, no teacher/target label,
    and no future/next-frame context.
    """

    if not isinstance(request, ValidatedPublicRequest):
        raise TypeError("request must be a ValidatedPublicRequest")
    source_sha256 = _normalize_source_sha256(source_sha256)

    entries = []
    seen_ids: set[str] = set()
    for frame_index, frame in enumerate(request.frames):
        frame_id = runtime_frame_id(frame, source_sha256=source_sha256)
        if frame_id in seen_ids:
            raise ValueError("duplicate runtime frame identity in one validated request")
        seen_ids.add(frame_id)
        entries.append(
            {
                "frame_index": frame_index,
                "runtime_frame_id": frame_id,
                "measure_number": frame.measure_number,
                "start": _beat_payload(frame.start),
                "end": _beat_payload(frame.end),
            }
        )

    return {
        "schema_name": RUNTIME_FRAME_TRACE_SCHEMA_NAME,
        "schema_version": RUNTIME_FRAME_TRACE_SCHEMA_VERSION,
        "source_sha256": source_sha256,
        "identity_role": "JOIN_KEY_NOT_MODEL_FEATURE",
        "entries": entries,
        "contains_harmonic_decision": False,
        "contains_teacher_or_target_label": False,
        "contains_future_or_next_context": False,
        "model_feature_authority": False,
        "production_authority": False,
        "deterministic_resolver_authority_unchanged": True,
    }
