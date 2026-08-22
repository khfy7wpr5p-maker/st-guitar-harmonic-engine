"""Stage 7-D public execution boundary over the existing deterministic core."""

from __future__ import annotations

from typing import Any

from .abstention import GatedDecision, apply_abstention_policy
from .aggregator import aggregate_frame_evidence
from .public_api import (
    PublicRequestMode,
    ValidatedPublicRequest,
    serialize_public_result,
    validate_public_request,
)
from .sequence import resolve_candidates_by_precedence, resolve_harmonic_sequence


def resolve_validated_public_request(
    request: ValidatedPublicRequest,
) -> tuple[GatedDecision, ...]:
    """Resolve one already-validated public request without adding new authority.

    ``batch`` resolves every canonical frame independently. ``sequence`` delegates
    to the existing deterministic sequence resolver and may use only an explicitly
    validated phrase plan. No AI/model evidence is consulted by this function.
    """

    if not isinstance(request, ValidatedPublicRequest):
        raise TypeError("request must be a ValidatedPublicRequest")

    if request.mode is PublicRequestMode.BATCH:
        decisions = []
        for frame in request.frames:
            candidates = aggregate_frame_evidence(frame)
            source = resolve_candidates_by_precedence(candidates)
            decisions.append(apply_abstention_policy(source))
        return tuple(decisions)

    sequence = resolve_harmonic_sequence(
        request.frames,
        phrase_plan=request.phrase_plan,
    )
    return tuple(apply_abstention_policy(item) for item in sequence.decisions)


def execute_public_request(payload: object) -> dict[str, Any]:
    """Validate, deterministically resolve, and serialize one public request."""

    request = validate_public_request(payload)
    decisions = resolve_validated_public_request(request)
    return serialize_public_result(request.frames, decisions)
