"""Additive explicit-tonal-context public request contract v1.2.

v1.2 layers bounded caller-supplied tonal-context spans on top of the spelling-
aware v1.1 request contract. v1.0 and v1.1 remain frozen and strict. No key
estimation, modulation inference, probabilistic smoothing, or model evidence is
introduced at this boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .abstention import GatedDecision, apply_abstention_policy
from .aggregator import aggregate_frame_evidence
from .context import TonalContext, TonalMode
from .local_context import LocalTonalContextPlan, LocalTonalContextSpan
from .public_api import (
    PUBLIC_API_SCHEMA_NAME,
    PublicRequestMode,
    PublicValidationError,
    ValidatedPublicRequest,
    serialize_public_result,
)
from .public_api_v1_1 import (
    PUBLIC_API_SCHEMA_VERSION_V1_1,
    validate_public_request_v1_1,
)
from .sequence import resolve_candidates_by_precedence, resolve_harmonic_sequence


PUBLIC_API_SCHEMA_VERSION_V1_2 = "1.2"
_OUTER_FIELDS_V1_2 = frozenset(
    {"schema_name", "schema_version", "mode", "frames", "phrase_spans", "tonal_context_spans"}
)
_CONTEXT_SPAN_FIELDS = frozenset({"start_index", "end_index", "tonic_pc", "mode"})


@dataclass(frozen=True, slots=True)
class ValidatedPublicRequestV12:
    """Frozen v1.1 request plus optional explicit local tonal context."""

    request: ValidatedPublicRequest
    local_context: LocalTonalContextPlan | None

    def __post_init__(self) -> None:
        if not isinstance(self.request, ValidatedPublicRequest):
            raise TypeError("request must be a ValidatedPublicRequest")
        if self.local_context is not None and not isinstance(
            self.local_context, LocalTonalContextPlan
        ):
            raise TypeError("local_context must be a LocalTonalContextPlan or None")
        if self.local_context is not None:
            self.local_context.contexts_for(len(self.request.frames))


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


def _parse_local_context_plan(
    value: object,
    *,
    frame_count: int,
) -> LocalTonalContextPlan | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise _error("tonal_context_spans must be a list or null")
    if len(value) > frame_count:
        raise _error("tonal_context_spans exceeds frame count")

    spans: list[LocalTonalContextSpan] = []
    for index, item in enumerate(value):
        raw = _require_exact_object(item, _CONTEXT_SPAN_FIELDS, f"tonal_context_span[{index}]")
        start_index = _bounded_int(
            raw["start_index"],
            name="tonal_context_span.start_index",
            minimum=0,
            maximum=frame_count,
        )
        end_index = _bounded_int(
            raw["end_index"],
            name="tonal_context_span.end_index",
            minimum=0,
            maximum=frame_count,
        )
        tonic_pc = _bounded_int(
            raw["tonic_pc"],
            name="tonal_context_span.tonic_pc",
            minimum=0,
            maximum=11,
        )
        try:
            mode = TonalMode(raw["mode"])
        except (TypeError, ValueError) as exc:
            raise _error("tonal_context_span.mode contains an unsupported value") from exc
        try:
            spans.append(
                LocalTonalContextSpan(
                    start_index,
                    end_index,
                    TonalContext(tonic_pc, mode),
                )
            )
        except (TypeError, ValueError) as exc:
            raise _error("tonal_context_span violates core context constraints") from exc

    if not spans:
        return None
    try:
        plan = LocalTonalContextPlan(tuple(sorted(spans)))
        plan.contexts_for(frame_count)
        return plan
    except (TypeError, ValueError) as exc:
        raise _error("tonal_context_spans overlap or exceed the request") from exc


def validate_public_request_v1_2(payload: object) -> ValidatedPublicRequestV12:
    """Validate spelling-aware request data plus explicit bounded tonal context."""

    raw = _require_exact_object(payload, _OUTER_FIELDS_V1_2, "request")
    if raw["schema_name"] != PUBLIC_API_SCHEMA_NAME:
        raise _error("schema_name is unsupported")
    if raw["schema_version"] != PUBLIC_API_SCHEMA_VERSION_V1_2:
        raise _error("schema_version is unsupported")

    v1_1_payload = {
        "schema_name": raw["schema_name"],
        "schema_version": PUBLIC_API_SCHEMA_VERSION_V1_1,
        "mode": raw["mode"],
        "frames": raw["frames"],
        "phrase_spans": raw["phrase_spans"],
    }
    base = validate_public_request_v1_1(v1_1_payload)
    local_context = _parse_local_context_plan(
        raw["tonal_context_spans"],
        frame_count=len(base.frames),
    )
    return ValidatedPublicRequestV12(base, local_context)


def resolve_validated_public_request_v1_2(
    validated: ValidatedPublicRequestV12,
) -> tuple[GatedDecision, ...]:
    """Run existing deterministic core with only the validated explicit contexts."""

    if not isinstance(validated, ValidatedPublicRequestV12):
        raise TypeError("validated must be a ValidatedPublicRequestV12")
    request = validated.request
    contexts = (
        validated.local_context.contexts_for(len(request.frames))
        if validated.local_context is not None
        else (None,) * len(request.frames)
    )

    if request.mode is PublicRequestMode.BATCH:
        decisions = []
        for frame, context in zip(request.frames, contexts):
            candidates = aggregate_frame_evidence(frame, context)
            decisions.append(
                apply_abstention_policy(resolve_candidates_by_precedence(candidates))
            )
        return tuple(decisions)

    sequence = resolve_harmonic_sequence(
        request.frames,
        local_context=validated.local_context,
        phrase_plan=request.phrase_plan,
    )
    return tuple(apply_abstention_policy(item) for item in sequence.decisions)


def execute_public_request_v1_2(payload: object) -> dict[str, Any]:
    """Validate v1.2, execute deterministically, and emit frozen result v1.0."""

    validated = validate_public_request_v1_2(payload)
    decisions = resolve_validated_public_request_v1_2(validated)
    return serialize_public_result(validated.request.frames, decisions)
