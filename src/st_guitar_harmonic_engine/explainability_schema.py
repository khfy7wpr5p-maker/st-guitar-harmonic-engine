"""Stable JSON-compatible schema for non-authoritative explainability evidence."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from .explainability import MeasureExplainability


EXPLAINABILITY_SCHEMA_NAME = "st-guitar-harmonic-engine.explainability"
EXPLAINABILITY_SCHEMA_VERSION = "1.0"

_FORBIDDEN_DECISION_FIELDS = frozenset(
    {"status", "selected", "decision", "resolution", "authoritative"}
)
_REQUIRED = MappingProxyType(
    {
        "measure": ("schema_name", "schema_version", "measure_number", "frames"),
        "frame": ("measure_number", "frame_index", "start", "end", "ncts", "omissions"),
        "beat": ("numerator", "denominator"),
        "nct": (
            "measure_number",
            "frame_index",
            "start",
            "end",
            "staff",
            "voice",
            "midi_pitch",
            "pitch_class",
            "kind",
            "anchor_root_pc",
            "anchor_quality",
        ),
        "omission": (
            "root_pc",
            "quality",
            "observed_pitch_classes",
            "omitted_pc",
            "omission",
        ),
    }
)

EXPLAINABILITY_SCHEMA_V1 = MappingProxyType(
    {
        "schema_name": EXPLAINABILITY_SCHEMA_NAME,
        "schema_version": EXPLAINABILITY_SCHEMA_VERSION,
        "compatible_versions": "1.x",
        "required_fields": _REQUIRED,
        "unknown_fields": "allowed",
        "breaking_changes": "require a new major version",
        "forbidden_decision_fields": tuple(sorted(_FORBIDDEN_DECISION_FIELDS)),
    }
)


def _beat(value) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def serialize_measure_explainability(report: MeasureExplainability) -> dict[str, Any]:
    """Return the canonical schema-1 payload for one explainability report."""

    if not isinstance(report, MeasureExplainability):
        raise TypeError("report must be a MeasureExplainability")

    payload: dict[str, Any] = {
        "schema_name": EXPLAINABILITY_SCHEMA_NAME,
        "schema_version": EXPLAINABILITY_SCHEMA_VERSION,
        "measure_number": report.measure_number,
        "frames": [
            {
                "measure_number": frame.measure_number,
                "frame_index": frame.frame_index,
                "start": _beat(frame.start),
                "end": _beat(frame.end),
                "ncts": [
                    {
                        "measure_number": item.measure_number,
                        "frame_index": item.frame_index,
                        "start": _beat(item.start),
                        "end": _beat(item.end),
                        "staff": item.staff,
                        "voice": item.voice,
                        "midi_pitch": item.midi_pitch,
                        "pitch_class": item.pitch_class,
                        "kind": item.kind.value,
                        "anchor_root_pc": item.anchor_root_pc,
                        "anchor_quality": item.anchor_quality.value,
                    }
                    for item in frame.ncts
                ],
                "omissions": [
                    {
                        "root_pc": item.root_pc,
                        "quality": item.quality.value,
                        "observed_pitch_classes": list(item.observed_pitch_classes),
                        "omitted_pc": item.omitted_pc,
                        "omission": item.omission.value,
                    }
                    for item in frame.omissions
                ],
            }
            for frame in report.frames
        ],
    }
    validate_explainability_payload(payload)
    return payload


def _as_mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("schema object must be a mapping")
    return value


def _require(value: Mapping[str, Any], kind: str) -> None:
    missing = [key for key in _REQUIRED[kind] if key not in value]
    if missing:
        raise ValueError(f"{kind} is missing required fields: {', '.join(missing)}")
    forbidden = sorted(_FORBIDDEN_DECISION_FIELDS.intersection(value))
    if forbidden:
        raise ValueError(
            f"{kind} contains forbidden decision fields: {', '.join(forbidden)}"
        )


def _validate_beat(value: object) -> None:
    beat = _as_mapping(value)
    _require(beat, "beat")
    if type(beat["numerator"]) is not int or type(beat["denominator"]) is not int:
        raise TypeError("beat numerator/denominator must be ints")
    if beat["denominator"] <= 0:
        raise ValueError("beat denominator must be positive")


def _validate_version(value: object) -> None:
    if not isinstance(value, str):
        raise TypeError("schema_version must be a string")
    pieces = value.split(".")
    if len(pieces) != 2 or any(not piece.isdigit() for piece in pieces):
        raise ValueError("schema_version must use MAJOR.MINOR form")
    if int(pieces[0]) != 1:
        raise ValueError("schema major version is incompatible with v1")


def validate_explainability_payload(payload: object) -> None:
    """Validate v1 required fields while allowing additive 1.x fields."""

    root = _as_mapping(payload)
    _require(root, "measure")
    if root["schema_name"] != EXPLAINABILITY_SCHEMA_NAME:
        raise ValueError("schema_name does not match the explainability contract")
    _validate_version(root["schema_version"])
    if type(root["measure_number"]) is not int or root["measure_number"] < 1:
        raise ValueError("measure_number must be a positive int")
    if not isinstance(root["frames"], list):
        raise TypeError("frames must be a list")

    for expected_index, frame_value in enumerate(root["frames"]):
        frame = _as_mapping(frame_value)
        _require(frame, "frame")
        if frame["measure_number"] != root["measure_number"]:
            raise ValueError("frame measure_number must match the report")
        if frame["frame_index"] != expected_index:
            raise ValueError("frame_index must preserve canonical order")
        _validate_beat(frame["start"])
        _validate_beat(frame["end"])
        if not isinstance(frame["ncts"], list) or not isinstance(frame["omissions"], list):
            raise TypeError("ncts and omissions must be lists")

        for nct_value in frame["ncts"]:
            nct = _as_mapping(nct_value)
            _require(nct, "nct")
            if nct["measure_number"] != root["measure_number"]:
                raise ValueError("NCT measure_number must match the report")
            if nct["frame_index"] != expected_index:
                raise ValueError("NCT frame_index must match the frame")
            _validate_beat(nct["start"])
            _validate_beat(nct["end"])

        for omission_value in frame["omissions"]:
            omission = _as_mapping(omission_value)
            _require(omission, "omission")
            if not isinstance(omission["observed_pitch_classes"], list):
                raise TypeError("observed_pitch_classes must be a list")


def is_explainability_payload_compatible(payload: object) -> bool:
    """Return True when a payload is safely consumable by schema-v1 readers."""

    try:
        validate_explainability_payload(payload)
    except (TypeError, ValueError):
        return False
    return True
