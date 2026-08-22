"""Stage 7 framework-independent public API boundary.

External payloads are treated as untrusted JSON-compatible values.  Validation
is strict, bounded, versioned, and converts data into existing core domain types
before any harmonic policy is invoked.  This module contains no network, file,
subprocess, framework, parser-SDK, or AI types.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .abstention import GatedDecision
from .frames import HarmonicFrame
from .models import NoteEvent, RationalBeat, TieState
from .phrase import PhrasePlan, PhraseSpan


PUBLIC_API_SCHEMA_NAME = "st_guitar_harmonic_engine.public_request"
PUBLIC_API_SCHEMA_VERSION = "1.0"
PUBLIC_RESULT_SCHEMA_NAME = "st_guitar_harmonic_engine.public_result"
PUBLIC_RESULT_SCHEMA_VERSION = "1.0"

MAX_PUBLIC_FRAMES = 512
MAX_EVENTS_PER_FRAME = 64
MAX_TOTAL_EVENTS = 8192
MAX_ABS_BEAT_NUMERATOR = 1_000_000
MAX_BEAT_DENOMINATOR = 1_000_000


class PublicRequestMode(str, Enum):
    BATCH = "batch"
    SEQUENCE = "sequence"


class PublicValidationError(ValueError):
    """Raised when untrusted public-API input fails closed."""


@dataclass(frozen=True, slots=True)
class ValidatedPublicRequest:
    mode: PublicRequestMode
    frames: tuple[HarmonicFrame, ...]
    phrase_plan: PhrasePlan | None

    def __post_init__(self) -> None:
        if not isinstance(self.mode, PublicRequestMode):
            raise TypeError("mode must be a PublicRequestMode")
        if not isinstance(self.frames, tuple) or any(
            not isinstance(item, HarmonicFrame) for item in self.frames
        ):
            raise TypeError("frames must contain HarmonicFrame values")
        if self.phrase_plan is not None and not isinstance(self.phrase_plan, PhrasePlan):
            raise TypeError("phrase_plan must be a PhrasePlan or None")
        if self.mode is PublicRequestMode.BATCH and self.phrase_plan is not None:
            raise ValueError("batch requests cannot carry a phrase plan")
        if self.phrase_plan is not None:
            self.phrase_plan.validate_frame_count(len(self.frames))


def _public_error(message: str) -> PublicValidationError:
    return PublicValidationError(message)


def _require_object(value: object, *, fields: frozenset[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _public_error(f"{name} must be an object")
    if set(value) != fields:
        raise _public_error(f"{name} fields do not match schema")
    return value


def _bounded_int(
    value: object,
    *,
    name: str,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _public_error(f"{name} must be an int")
    if minimum is not None and value < minimum:
        raise _public_error(f"{name} is below supported range")
    if maximum is not None and value > maximum:
        raise _public_error(f"{name} is above supported range")
    return value


def _parse_beat(value: object, *, name: str) -> RationalBeat:
    raw = _require_object(
        value,
        fields=frozenset({"numerator", "denominator"}),
        name=name,
    )
    numerator = _bounded_int(
        raw["numerator"],
        name=f"{name}.numerator",
        minimum=-MAX_ABS_BEAT_NUMERATOR,
        maximum=MAX_ABS_BEAT_NUMERATOR,
    )
    denominator = _bounded_int(
        raw["denominator"],
        name=f"{name}.denominator",
        minimum=1,
        maximum=MAX_BEAT_DENOMINATOR,
    )
    try:
        return RationalBeat(numerator, denominator)
    except (TypeError, ValueError) as exc:
        raise _public_error(f"{name} is invalid") from exc


def _event_key(event: NoteEvent) -> tuple[object, ...]:
    return (
        event.measure_number,
        event.staff,
        event.voice,
        event.midi_pitch,
        event.onset.fraction,
        event.duration.fraction,
        event.tie.value,
    )


def _parse_event(value: object, *, measure_number: int, index: int) -> NoteEvent:
    raw = _require_object(
        value,
        fields=frozenset({"staff", "voice", "midi_pitch", "onset", "duration", "tie"}),
        name=f"event[{index}]",
    )
    staff = _bounded_int(raw["staff"], name="staff", minimum=1, maximum=64)
    voice = _bounded_int(raw["voice"], name="voice", minimum=1, maximum=1024)
    pitch = _bounded_int(raw["midi_pitch"], name="midi_pitch", minimum=0, maximum=127)
    onset = _parse_beat(raw["onset"], name="onset")
    duration = _parse_beat(raw["duration"], name="duration")
    try:
        tie = TieState(raw["tie"])
    except (TypeError, ValueError) as exc:
        raise _public_error("tie contains an unsupported enum value") from exc
    try:
        return NoteEvent(
            measure_number=measure_number,
            staff=staff,
            voice=voice,
            midi_pitch=pitch,
            onset=onset,
            duration=duration,
            tie=tie,
        )
    except (TypeError, ValueError) as exc:
        raise _public_error("event violates core domain constraints") from exc


def _frame_key(frame: HarmonicFrame) -> tuple[object, ...]:
    return (
        frame.measure_number,
        frame.start.fraction,
        frame.end.fraction,
        tuple(sorted(_event_key(event) for event in frame.events)),
    )


def _parse_frame(value: object, *, index: int) -> HarmonicFrame:
    raw = _require_object(
        value,
        fields=frozenset({"measure_number", "start", "end", "events"}),
        name=f"frame[{index}]",
    )
    measure_number = _bounded_int(
        raw["measure_number"],
        name="measure_number",
        minimum=1,
        maximum=1_000_000,
    )
    start = _parse_beat(raw["start"], name="start")
    end = _parse_beat(raw["end"], name="end")
    if start.fraction < 0 or end.fraction <= start.fraction:
        raise _public_error("frame boundaries are invalid")

    raw_events = raw["events"]
    if not isinstance(raw_events, list) or not raw_events:
        raise _public_error("events must be a non-empty list")
    if len(raw_events) > MAX_EVENTS_PER_FRAME:
        raise _public_error("frame exceeds maximum event count")
    events = tuple(
        _parse_event(item, measure_number=measure_number, index=event_index)
        for event_index, item in enumerate(raw_events)
    )
    keys = tuple(_event_key(event) for event in events)
    if len(set(keys)) != len(keys):
        raise _public_error("duplicate event entries are not allowed")
    canonical_events = tuple(sorted(events, key=_event_key))
    try:
        return HarmonicFrame(measure_number, start, end, canonical_events)
    except (TypeError, ValueError) as exc:
        raise _public_error("frame violates core domain constraints") from exc


def _parse_phrase_plan(value: object, *, frame_count: int) -> PhrasePlan | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise _public_error("phrase_spans must be a list or null")
    spans: list[PhraseSpan] = []
    for index, item in enumerate(value):
        raw = _require_object(
            item,
            fields=frozenset({"start_index", "end_index"}),
            name=f"phrase_span[{index}]",
        )
        start_index = _bounded_int(
            raw["start_index"],
            name="start_index",
            minimum=0,
            maximum=frame_count,
        )
        end_index = _bounded_int(
            raw["end_index"],
            name="end_index",
            minimum=0,
            maximum=frame_count,
        )
        try:
            spans.append(PhraseSpan(start_index, end_index))
        except (TypeError, ValueError) as exc:
            raise _public_error("phrase span is invalid") from exc
    canonical = tuple(sorted(spans))
    if len(set(canonical)) != len(canonical):
        raise _public_error("duplicate phrase spans are not allowed")
    try:
        plan = PhrasePlan(canonical)
        plan.validate_frame_count(frame_count)
        return plan
    except (TypeError, ValueError) as exc:
        raise _public_error("phrase plan is invalid") from exc


def validate_public_request(payload: object) -> ValidatedPublicRequest:
    """Validate and normalize one external batch/sequence request.

    Frame order is canonicalized by musical position and content so equivalent
    batch/sequence payload permutations produce the same validated request.
    Phrase span indexes always refer to this canonical frame order.
    """

    raw = _require_object(
        payload,
        fields=frozenset({
            "schema_name",
            "schema_version",
            "mode",
            "frames",
            "phrase_spans",
        }),
        name="request",
    )
    if raw["schema_name"] != PUBLIC_API_SCHEMA_NAME:
        raise _public_error("unsupported public API schema name")
    if raw["schema_version"] != PUBLIC_API_SCHEMA_VERSION:
        raise _public_error("unsupported public API schema version")
    try:
        mode = PublicRequestMode(raw["mode"])
    except (TypeError, ValueError) as exc:
        raise _public_error("mode contains an unsupported enum value") from exc

    raw_frames = raw["frames"]
    if not isinstance(raw_frames, list) or not raw_frames:
        raise _public_error("frames must be a non-empty list")
    if len(raw_frames) > MAX_PUBLIC_FRAMES:
        raise _public_error("request exceeds maximum frame count")
    frames = tuple(_parse_frame(item, index=index) for index, item in enumerate(raw_frames))
    if sum(len(item.events) for item in frames) > MAX_TOTAL_EVENTS:
        raise _public_error("request exceeds maximum total event count")
    keys = tuple(_frame_key(item) for item in frames)
    if len(set(keys)) != len(keys):
        raise _public_error("duplicate frames are not allowed")
    frames = tuple(sorted(frames, key=_frame_key))

    phrase_plan = _parse_phrase_plan(raw["phrase_spans"], frame_count=len(frames))
    if mode is PublicRequestMode.BATCH and phrase_plan is not None:
        raise _public_error("batch mode cannot carry phrase spans")
    return ValidatedPublicRequest(mode, frames, phrase_plan)


def _serialize_identity(candidate) -> dict[str, Any]:
    return {
        "root_pc": candidate.identity.root_pc,
        "family": candidate.identity.family.value,
        "variant": candidate.identity.variant,
    }


def serialize_gated_decision(decision: GatedDecision) -> dict[str, Any]:
    """Serialize one final decision without changing its authority semantics."""

    if not isinstance(decision, GatedDecision):
        raise TypeError("decision must be a GatedDecision")
    source = decision.source_decision
    return {
        "state": decision.state.value,
        "source_status": source.status.value,
        "candidates": [
            {
                "identity": _serialize_identity(item),
                "evidence": [source.value for source in item.evidence],
            }
            for item in source.candidates
        ],
        "confidence": (
            {
                "state": decision.confidence.state.value,
                "basis": [source.value for source in decision.confidence.basis],
            }
            if decision.confidence is not None
            else None
        ),
        "abstention_reason": (
            decision.abstention_reason.value
            if decision.abstention_reason is not None
            else None
        ),
    }


def serialize_public_result(
    frames: tuple[HarmonicFrame, ...],
    decisions: tuple[GatedDecision, ...],
) -> dict[str, Any]:
    """Return canonical versioned output for a validated public request."""

    if not isinstance(frames, tuple) or any(not isinstance(item, HarmonicFrame) for item in frames):
        raise TypeError("frames must contain HarmonicFrame values")
    if not isinstance(decisions, tuple) or any(not isinstance(item, GatedDecision) for item in decisions):
        raise TypeError("decisions must contain GatedDecision values")
    if len(frames) != len(decisions):
        raise ValueError("frame and decision counts must match")
    return {
        "schema_name": PUBLIC_RESULT_SCHEMA_NAME,
        "schema_version": PUBLIC_RESULT_SCHEMA_VERSION,
        "results": [
            {
                "measure_number": frame.measure_number,
                "start": {
                    "numerator": frame.start.numerator,
                    "denominator": frame.start.denominator,
                },
                "end": {
                    "numerator": frame.end.numerator,
                    "denominator": frame.end.denominator,
                },
                "decision": serialize_gated_decision(decision),
            }
            for frame, decision in zip(frames, decisions)
        ],
    }


def is_public_result_payload_compatible(payload: object) -> bool:
    return (
        isinstance(payload, dict)
        and set(payload) == {"schema_name", "schema_version", "results"}
        and payload.get("schema_name") == PUBLIC_RESULT_SCHEMA_NAME
        and payload.get("schema_version") == PUBLIC_RESULT_SCHEMA_VERSION
        and isinstance(payload.get("results"), list)
    )
