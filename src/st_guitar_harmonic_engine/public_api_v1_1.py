"""Additive spelling-aware public request contract v1.1.

The frozen v1.0 request schema remains unchanged and MIDI-only.  This module
adds a separate request version that carries optional written pitch spelling on
each already-bounded note event.  It reuses the v1.0 validator for all existing
resource, timing, frame, phrase, duplicate, and enum constraints, then attaches
validated ``WrittenPitch`` values to the same canonical core events.

Written spelling is evidence only.  This boundary does not resolve chords,
change evidence precedence, consult AI/model components, or weaken ambiguity /
abstention policy.
"""

from __future__ import annotations

from typing import Any

from .frames import HarmonicFrame
from .models import NoteEvent, RationalBeat
from .public_api import (
    MAX_EVENTS_PER_FRAME,
    MAX_PUBLIC_FRAMES,
    MAX_TOTAL_EVENTS,
    PUBLIC_API_SCHEMA_NAME,
    PUBLIC_API_SCHEMA_VERSION,
    PublicValidationError,
    ValidatedPublicRequest,
    serialize_public_result,
    validate_public_request,
)
from .spelling import PitchStep, WrittenPitch


PUBLIC_API_SCHEMA_VERSION_V1_1 = "1.1"

_OUTER_FIELDS = frozenset({"schema_name", "schema_version", "mode", "frames", "phrase_spans"})
_FRAME_FIELDS = frozenset({"measure_number", "start", "end", "events"})
_EVENT_FIELDS_V1_1 = frozenset(
    {"staff", "voice", "midi_pitch", "onset", "duration", "tie", "written_pitch"}
)
_WRITTEN_PITCH_FIELDS = frozenset({"step", "alter", "octave"})


def _error(message: str) -> PublicValidationError:
    return PublicValidationError(message)


def _require_exact_object(value: object, fields: frozenset[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _error(f"{name} must be an object")
    if set(value) != fields:
        raise _error(f"{name} fields do not match schema")
    return value


def _bounded_int(value: object, *, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _error(f"{name} must be an int")
    if not minimum <= value <= maximum:
        raise _error(f"{name} is outside supported range")
    return value


def _parse_written_pitch(value: object, *, event_index: int) -> WrittenPitch | None:
    if value is None:
        return None
    raw = _require_exact_object(
        value,
        _WRITTEN_PITCH_FIELDS,
        f"event[{event_index}].written_pitch",
    )
    step_raw = raw["step"]
    if not isinstance(step_raw, str):
        raise _error("written_pitch.step must be a string")
    try:
        step = PitchStep(step_raw)
    except ValueError as exc:
        raise _error("written_pitch.step contains an unsupported value") from exc
    alter = _bounded_int(raw["alter"], name="written_pitch.alter", minimum=-2, maximum=2)
    octave = _bounded_int(raw["octave"], name="written_pitch.octave", minimum=-1, maximum=9)
    try:
        return WrittenPitch(step, alter, octave)
    except (TypeError, ValueError) as exc:
        raise _error("written_pitch violates core spelling constraints") from exc


def _beat(raw: object) -> RationalBeat:
    # v1.0 validation has already accepted the stripped payload before this helper
    # is used, so these fields are known to be bounded canonical beat inputs.
    if not isinstance(raw, dict):
        raise _error("beat must be an object")
    return RationalBeat(raw["numerator"], raw["denominator"])


def _raw_locator(frame: dict[str, Any], event: dict[str, Any]) -> tuple[object, ...]:
    return (
        frame["measure_number"],
        _beat(frame["start"]).fraction,
        _beat(frame["end"]).fraction,
        event["staff"],
        event["voice"],
        event["midi_pitch"],
        _beat(event["onset"]).fraction,
        _beat(event["duration"]).fraction,
        event["tie"],
    )


def _validated_locator(frame: HarmonicFrame, event: NoteEvent) -> tuple[object, ...]:
    return (
        frame.measure_number,
        frame.start.fraction,
        frame.end.fraction,
        event.staff,
        event.voice,
        event.midi_pitch,
        event.onset.fraction,
        event.duration.fraction,
        event.tie.value,
    )


def validate_public_request_v1_1(payload: object) -> ValidatedPublicRequest:
    """Validate and canonicalize one spelling-aware public request.

    v1.1 requires every event to carry an explicit ``written_pitch`` field.  Its
    value may be ``null`` when source spelling is unavailable; null spelling must
    not be guessed.  Existing v1.0 request limits and semantics remain the base
    contract and are revalidated unchanged after the additive field is removed.
    """

    raw = _require_exact_object(payload, _OUTER_FIELDS, "request")
    if raw["schema_name"] != PUBLIC_API_SCHEMA_NAME:
        raise _error("schema_name is unsupported")
    if raw["schema_version"] != PUBLIC_API_SCHEMA_VERSION_V1_1:
        raise _error("schema_version is unsupported")

    raw_frames = raw["frames"]
    if not isinstance(raw_frames, list) or not raw_frames:
        raise _error("frames must be a non-empty list")
    if len(raw_frames) > MAX_PUBLIC_FRAMES:
        raise _error("request exceeds maximum frame count")

    stripped_frames: list[dict[str, Any]] = []
    canonical_raw_frames: list[dict[str, Any]] = []
    total_events = 0
    for frame_index, frame_value in enumerate(raw_frames):
        frame = _require_exact_object(frame_value, _FRAME_FIELDS, f"frame[{frame_index}]")
        events_value = frame["events"]
        if not isinstance(events_value, list) or not events_value:
            raise _error("events must be a non-empty list")
        if len(events_value) > MAX_EVENTS_PER_FRAME:
            raise _error("frame exceeds maximum event count")
        total_events += len(events_value)
        if total_events > MAX_TOTAL_EVENTS:
            raise _error("request exceeds maximum total event count")

        stripped_events: list[dict[str, Any]] = []
        checked_events: list[dict[str, Any]] = []
        for event_index, event_value in enumerate(events_value):
            event = _require_exact_object(
                event_value,
                _EVENT_FIELDS_V1_1,
                f"frame[{frame_index}].event[{event_index}]",
            )
            checked_events.append(event)
            stripped_events.append(
                {key: event[key] for key in _EVENT_FIELDS_V1_1 if key != "written_pitch"}
            )

        canonical_raw_frames.append({**frame, "events": checked_events})
        stripped_frames.append({**frame, "events": stripped_events})

    stripped_payload = {
        "schema_name": PUBLIC_API_SCHEMA_NAME,
        "schema_version": PUBLIC_API_SCHEMA_VERSION,
        "mode": raw["mode"],
        "frames": stripped_frames,
        "phrase_spans": raw["phrase_spans"],
    }
    base = validate_public_request(stripped_payload)

    spelling_by_locator: dict[tuple[object, ...], WrittenPitch | None] = {}
    for frame_index, frame in enumerate(canonical_raw_frames):
        for event_index, event in enumerate(frame["events"]):
            locator = _raw_locator(frame, event)
            if locator in spelling_by_locator:
                # The v1.0 duplicate checks should already make this unreachable.
                raise _error("duplicate event locator is not allowed")
            spelling_by_locator[locator] = _parse_written_pitch(
                event["written_pitch"],
                event_index=event_index,
            )

    frames: list[HarmonicFrame] = []
    for base_frame in base.frames:
        events: list[NoteEvent] = []
        for event in base_frame.events:
            locator = _validated_locator(base_frame, event)
            if locator not in spelling_by_locator:
                raise _error("validated event could not be matched to source spelling")
            events.append(
                NoteEvent(
                    measure_number=event.measure_number,
                    staff=event.staff,
                    voice=event.voice,
                    midi_pitch=event.midi_pitch,
                    onset=event.onset,
                    duration=event.duration,
                    tie=event.tie,
                    written_pitch=spelling_by_locator[locator],
                )
            )
        frames.append(
            HarmonicFrame(
                measure_number=base_frame.measure_number,
                start=base_frame.start,
                end=base_frame.end,
                events=tuple(events),
            )
        )

    return ValidatedPublicRequest(
        mode=base.mode,
        frames=tuple(frames),
        phrase_plan=base.phrase_plan,
    )


def execute_public_request_v1_1(payload: object) -> dict[str, Any]:
    """Validate v1.1, run the existing deterministic runtime, and emit result v1.0."""

    # Local import prevents a module cycle: public_runtime intentionally remains
    # the frozen v1.0 entrypoint and does not import this additive contract.
    from .public_runtime import resolve_validated_public_request

    request = validate_public_request_v1_1(payload)
    decisions = resolve_validated_public_request(request)
    return serialize_public_result(request.frames, decisions)
