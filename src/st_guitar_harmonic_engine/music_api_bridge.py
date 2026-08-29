"""Transport-neutral Music API bridge over the frozen public contracts.

This module deliberately contains no HTTP, authentication, retry, provider SDK,
filesystem, subprocess, UI, or model code.  A network/service adapter may wrap
this bridge, but harmonic authority remains inside the existing deterministic
public runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .public_api import (
    PUBLIC_API_SCHEMA_NAME,
    PUBLIC_API_SCHEMA_VERSION,
    PublicValidationError,
)
from .public_api_v1_1 import (
    PUBLIC_API_SCHEMA_VERSION_V1_1,
    execute_public_request_v1_1,
)
from .public_api_v1_2 import (
    PUBLIC_API_SCHEMA_VERSION_V1_2,
    execute_public_request_v1_2,
)
from .public_runtime import execute_public_request


MUSIC_API_BRIDGE_SCHEMA_NAME = "st_guitar_harmonic_engine.music_api_bridge"
MUSIC_API_BRIDGE_SCHEMA_VERSION = "1.0"
MUSIC_API_RESULT_SCHEMA_NAME = "st_guitar_harmonic_engine.music_api_result"
MUSIC_API_RESULT_SCHEMA_VERSION = "1.0"
MAX_REQUEST_ID_LENGTH = 128

_BRIDGE_FIELDS = frozenset(
    {"schema_name", "schema_version", "request_id", "harmonic_request"}
)
_SUPPORTED_HARMONIC_VERSIONS = frozenset(
    {
        PUBLIC_API_SCHEMA_VERSION,
        PUBLIC_API_SCHEMA_VERSION_V1_1,
        PUBLIC_API_SCHEMA_VERSION_V1_2,
    }
)


class MusicApiBridgeValidationError(ValueError):
    """Raised when an outer Music API bridge envelope is invalid."""


@dataclass(frozen=True, slots=True)
class ValidatedMusicApiBridgeRequest:
    """Validated outer envelope plus an unmodified ST public request payload."""

    request_id: str
    harmonic_request: dict[str, Any]
    harmonic_schema_version: str


def _error(message: str) -> MusicApiBridgeValidationError:
    return MusicApiBridgeValidationError(message)


def _require_exact_object(
    value: object,
    fields: frozenset[str],
    name: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _error(f"{name} must be an object")
    if set(value) != fields:
        raise _error(f"{name} fields do not match schema")
    return value


def _validate_request_id(value: object) -> str:
    if not isinstance(value, str):
        raise _error("request_id must be a string")
    if not value or len(value) > MAX_REQUEST_ID_LENGTH:
        raise _error("request_id is empty or exceeds supported length")
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in value):
        raise _error("request_id contains control characters")
    return value


def validate_music_api_bridge_request(
    payload: object,
) -> ValidatedMusicApiBridgeRequest:
    """Validate only the transport envelope and identify the ST contract version.

    The nested harmonic request is intentionally not translated or enriched here.
    It is delegated unchanged to its versioned ST validator so provider data cannot
    bypass the existing strict schema, resource bounds, ambiguity, or abstention
    policy.
    """

    raw = _require_exact_object(payload, _BRIDGE_FIELDS, "music_api_request")
    if raw["schema_name"] != MUSIC_API_BRIDGE_SCHEMA_NAME:
        raise _error("schema_name is unsupported")
    if raw["schema_version"] != MUSIC_API_BRIDGE_SCHEMA_VERSION:
        raise _error("schema_version is unsupported")

    request_id = _validate_request_id(raw["request_id"])
    harmonic_request = raw["harmonic_request"]
    if not isinstance(harmonic_request, dict):
        raise _error("harmonic_request must be an object")
    if harmonic_request.get("schema_name") != PUBLIC_API_SCHEMA_NAME:
        raise _error("harmonic_request.schema_name is unsupported")

    harmonic_schema_version = harmonic_request.get("schema_version")
    if harmonic_schema_version not in _SUPPORTED_HARMONIC_VERSIONS:
        raise _error("harmonic_request.schema_version is unsupported")

    return ValidatedMusicApiBridgeRequest(
        request_id=request_id,
        harmonic_request=harmonic_request,
        harmonic_schema_version=harmonic_schema_version,
    )


def _execute_harmonic_request(validated: ValidatedMusicApiBridgeRequest) -> dict[str, Any]:
    version = validated.harmonic_schema_version
    payload = validated.harmonic_request
    if version == PUBLIC_API_SCHEMA_VERSION:
        return execute_public_request(payload)
    if version == PUBLIC_API_SCHEMA_VERSION_V1_1:
        return execute_public_request_v1_1(payload)
    if version == PUBLIC_API_SCHEMA_VERSION_V1_2:
        return execute_public_request_v1_2(payload)
    # validate_music_api_bridge_request makes this unreachable; keep fail-closed.
    raise PublicValidationError("validated harmonic schema version is unsupported")


def execute_music_api_bridge_request(payload: object) -> dict[str, Any]:
    """Execute a Music API envelope through the existing deterministic ST runtime."""

    validated = validate_music_api_bridge_request(payload)
    harmonic_result = _execute_harmonic_request(validated)
    return {
        "schema_name": MUSIC_API_RESULT_SCHEMA_NAME,
        "schema_version": MUSIC_API_RESULT_SCHEMA_VERSION,
        "request_id": validated.request_id,
        "harmonic_result": harmonic_result,
    }
