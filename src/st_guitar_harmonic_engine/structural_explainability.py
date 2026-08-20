"""Schema-1.1 additive explainability for Stage 2-A structural evidence.

The existing schema-1.0 serializer remains unchanged. This module adds only
non-authoritative transition evidence and intentionally exposes no disposition,
selection, status, confidence, or authoritative decision field.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .explainability import MeasureExplainability
from .explainability_schema import (
    EXPLAINABILITY_SCHEMA_NAME,
    serialize_measure_explainability,
    validate_explainability_payload,
)
from .structural import BoundaryReason, StructuralSegmentation


STRUCTURAL_EXPLAINABILITY_SCHEMA_VERSION = "1.1"
_STRUCTURAL_FIELD = "structural_boundary_evidence"
_FORBIDDEN_DECISION_FIELDS = frozenset(
    {"status", "selected", "decision", "resolution", "authoritative", "disposition"}
)
_REQUIRED_TRANSITION_FIELDS = (
    "left_frame_index",
    "right_frame_index",
    "position",
    "signals",
)


def _beat(value) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def serialize_structural_explainability(
    report: MeasureExplainability,
    segmentation: StructuralSegmentation,
) -> dict[str, Any]:
    """Return schema-1.1 payload while preserving all schema-1.0 frame evidence."""

    if not isinstance(report, MeasureExplainability):
        raise TypeError("report must be a MeasureExplainability")
    if not isinstance(segmentation, StructuralSegmentation):
        raise TypeError("segmentation must be a StructuralSegmentation")
    if report.measure_number != segmentation.measure_number:
        raise ValueError("report and segmentation must belong to the same measure")

    payload = serialize_measure_explainability(report)
    payload["schema_version"] = STRUCTURAL_EXPLAINABILITY_SCHEMA_VERSION
    payload[_STRUCTURAL_FIELD] = [
        {
            "left_frame_index": transition.left_frame_index,
            "right_frame_index": transition.right_frame_index,
            "position": _beat(transition.position),
            "signals": [transition.reason.value],
        }
        for transition in segmentation.transitions
    ]
    validate_structural_explainability_payload(payload)
    return payload


def _as_mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("structural evidence item must be a mapping")
    return value


def _validate_position(value: object) -> None:
    position = _as_mapping(value)
    if "numerator" not in position or "denominator" not in position:
        raise ValueError("position must contain numerator and denominator")
    if type(position["numerator"]) is not int or type(position["denominator"]) is not int:
        raise TypeError("position numerator/denominator must be ints")
    if position["denominator"] <= 0:
        raise ValueError("position denominator must be positive")


def validate_structural_explainability_payload(payload: object) -> None:
    """Validate the additive structural extension and the underlying v1 contract."""

    validate_explainability_payload(payload)
    root = _as_mapping(payload)
    if root.get("schema_name") != EXPLAINABILITY_SCHEMA_NAME:
        raise ValueError("schema_name does not match the explainability contract")

    version = root.get("schema_version")
    if not isinstance(version, str):
        raise TypeError("schema_version must be a string")
    pieces = version.split(".")
    if len(pieces) != 2 or any(not piece.isdigit() for piece in pieces):
        raise ValueError("schema_version must use MAJOR.MINOR form")
    if int(pieces[0]) != 1 or int(pieces[1]) < 1:
        raise ValueError("structural evidence requires schema version 1.1 or later 1.x")

    if _STRUCTURAL_FIELD not in root:
        raise ValueError("structural_boundary_evidence is required for the structural extension")
    evidence = root[_STRUCTURAL_FIELD]
    if not isinstance(evidence, list):
        raise TypeError("structural_boundary_evidence must be a list")

    frames = root.get("frames")
    if not isinstance(frames, list):
        raise TypeError("frames must be a list")

    allowed_signals = {reason.value for reason in BoundaryReason}
    for item_value in evidence:
        item = _as_mapping(item_value)
        missing = [field for field in _REQUIRED_TRANSITION_FIELDS if field not in item]
        if missing:
            raise ValueError(
                "structural evidence is missing required fields: " + ", ".join(missing)
            )
        forbidden = sorted(_FORBIDDEN_DECISION_FIELDS.intersection(item))
        if forbidden:
            raise ValueError(
                "structural evidence contains forbidden decision fields: "
                + ", ".join(forbidden)
            )

        left = item["left_frame_index"]
        right = item["right_frame_index"]
        if type(left) is not int or type(right) is not int:
            raise TypeError("structural frame indexes must be ints")
        if left < 0 or right != left + 1 or right >= len(frames):
            raise ValueError("structural evidence must reference adjacent existing frames")

        _validate_position(item["position"])
        if item["position"] != frames[right]["start"]:
            raise ValueError("structural position must equal the right frame start")

        signals = item["signals"]
        if not isinstance(signals, list) or not signals:
            raise ValueError("signals must be a non-empty list")
        if any(not isinstance(signal, str) for signal in signals):
            raise TypeError("signals must contain strings")
        if len(set(signals)) != len(signals):
            raise ValueError("signals must be unique")
        if any(signal not in allowed_signals for signal in signals):
            raise ValueError("signals contain an unsupported structural reason")


def is_structural_explainability_payload_compatible(payload: object) -> bool:
    try:
        validate_structural_explainability_payload(payload)
    except (TypeError, ValueError):
        return False
    return True
