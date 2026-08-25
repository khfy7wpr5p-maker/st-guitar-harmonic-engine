"""Frozen OpenScore source-snapshot contract for Stage 8 research.

The module records only provenance metadata for approved CC0 source repositories.
It does not download corpus data, copy score payloads into this repository, parse
music, mine labels, start model training, or grant production authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re


STAGE8_OPENSCORE_SNAPSHOT_VERSION = "0.1"
_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class OpenScoreSnapshotStatus(str, Enum):
    BLOCKED_EMPTY = "blocked_empty"
    BLOCKED_SOURCE_SET = "blocked_source_set"
    BLOCKED_INTEGRITY = "blocked_integrity"
    BLOCKED_RIGHTS = "blocked_rights"
    SNAPSHOT_PLAN_FROZEN = "snapshot_plan_frozen"


@dataclass(frozen=True, slots=True, order=True)
class OpenScoreRepositorySnapshot:
    source_id: str
    repository: str
    commit_sha: str
    license_path: str
    license_blob_sha: str
    license_id: str
    score_root: str
    source_extension: str
    conversion_extension: str
    frozen_snapshot: bool
    training_rights_confirmed: bool
    commercial_use_allowed: bool

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id:
            raise TypeError("source_id must be a non-empty string")
        if not isinstance(self.repository, str) or _REPO_RE.fullmatch(self.repository) is None:
            raise ValueError("repository must be owner/name")
        for name in ("commit_sha", "license_blob_sha"):
            value = getattr(self, name)
            if not isinstance(value, str) or _SHA40_RE.fullmatch(value) is None:
                raise ValueError(f"{name} must be lowercase 40-character SHA")
        if self.license_path != "LICENSE.txt":
            raise ValueError("OpenScore snapshot license_path must be LICENSE.txt")
        if self.license_id != "CC0-1.0":
            raise ValueError("OpenScore training source must be pinned to CC0-1.0")
        if self.score_root != "scores":
            raise ValueError("OpenScore score_root must be scores")
        if self.source_extension != ".mscx":
            raise ValueError("OpenScore source_extension must be .mscx")
        if self.conversion_extension != ".mxl":
            raise ValueError("OpenScore conversion_extension must be .mxl")
        for name in ("frozen_snapshot", "training_rights_confirmed", "commercial_use_allowed"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")


@dataclass(frozen=True, slots=True)
class OpenScoreSnapshotAssessment:
    status: OpenScoreSnapshotStatus
    reasons: tuple[str, ...]
    source_count: int
    model_training_authorized: bool = False
    production_authority_granted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.status, OpenScoreSnapshotStatus):
            raise TypeError("status must be OpenScoreSnapshotStatus")
        if not isinstance(self.reasons, tuple) or any(not isinstance(item, str) or not item for item in self.reasons):
            raise TypeError("reasons must contain non-empty strings")
        if tuple(sorted(set(self.reasons))) != self.reasons:
            raise ValueError("reasons must be unique canonical order")
        if isinstance(self.source_count, bool) or not isinstance(self.source_count, int) or self.source_count < 0:
            raise ValueError("source_count must be a non-negative int")
        if self.model_training_authorized or self.production_authority_granted:
            raise ValueError("snapshot planning cannot authorize training or production")
        frozen = self.status is OpenScoreSnapshotStatus.SNAPSHOT_PLAN_FROZEN
        if frozen and self.reasons:
            raise ValueError("frozen snapshot plan cannot contain reasons")
        if not frozen and not self.reasons:
            raise ValueError("blocked snapshot assessment requires reasons")


_EXPECTED = {
    "openscore-string-quartets": OpenScoreRepositorySnapshot(
        source_id="openscore-string-quartets",
        repository="OpenScore/StringQuartets",
        commit_sha="91c780acf1502e7b4f745dc100836c501f41d8e3",
        license_path="LICENSE.txt",
        license_blob_sha="0e259d42c996742e9e3cba14c677129b2c1b6311",
        license_id="CC0-1.0",
        score_root="scores",
        source_extension=".mscx",
        conversion_extension=".mxl",
        frozen_snapshot=True,
        training_rights_confirmed=True,
        commercial_use_allowed=True,
    ),
    "openscore-lieder": OpenScoreRepositorySnapshot(
        source_id="openscore-lieder",
        repository="OpenScore/Lieder",
        commit_sha="6b2dc542ce2e8aa4b78c8ee62103b210efc07015",
        license_path="LICENSE.txt",
        license_blob_sha="0e259d42c996742e9e3cba14c677129b2c1b6311",
        license_id="CC0-1.0",
        score_root="scores",
        source_extension=".mscx",
        conversion_extension=".mxl",
        frozen_snapshot=True,
        training_rights_confirmed=True,
        commercial_use_allowed=True,
    ),
}


def canonical_openscore_snapshots() -> tuple[OpenScoreRepositorySnapshot, ...]:
    """Return the exact externally verified repository snapshots for v0.1."""

    return tuple(_EXPECTED[key] for key in sorted(_EXPECTED))


def assess_openscore_snapshots(
    snapshots: tuple[OpenScoreRepositorySnapshot, ...],
) -> OpenScoreSnapshotAssessment:
    """Fail closed unless snapshots exactly match the approved frozen source set."""

    if not isinstance(snapshots, tuple) or any(not isinstance(item, OpenScoreRepositorySnapshot) for item in snapshots):
        raise TypeError("snapshots must contain OpenScoreRepositorySnapshot values")
    if not snapshots:
        return OpenScoreSnapshotAssessment(
            OpenScoreSnapshotStatus.BLOCKED_EMPTY,
            ("openscore_snapshot_set_is_empty",),
            0,
        )

    ids = [item.source_id for item in snapshots]
    if len(ids) != len(set(ids)) or set(ids) != set(_EXPECTED):
        return OpenScoreSnapshotAssessment(
            OpenScoreSnapshotStatus.BLOCKED_SOURCE_SET,
            ("snapshot_source_set_must_match_approved_v0_1_sources",),
            len(snapshots),
        )

    integrity: list[str] = []
    rights: list[str] = []
    for item in snapshots:
        expected = _EXPECTED[item.source_id]
        if item != expected:
            integrity.append(f"{item.source_id}:snapshot_metadata_drift")
        if not item.frozen_snapshot:
            integrity.append(f"{item.source_id}:snapshot_not_frozen")
        if not item.training_rights_confirmed:
            rights.append(f"{item.source_id}:training_rights_not_confirmed")
        if not item.commercial_use_allowed:
            rights.append(f"{item.source_id}:commercial_use_not_allowed")
        if item.license_id != "CC0-1.0":
            rights.append(f"{item.source_id}:license_not_cc0")

    if rights:
        return OpenScoreSnapshotAssessment(
            OpenScoreSnapshotStatus.BLOCKED_RIGHTS,
            tuple(sorted(set(rights))),
            len(snapshots),
        )
    if integrity:
        return OpenScoreSnapshotAssessment(
            OpenScoreSnapshotStatus.BLOCKED_INTEGRITY,
            tuple(sorted(set(integrity))),
            len(snapshots),
        )

    return OpenScoreSnapshotAssessment(
        OpenScoreSnapshotStatus.SNAPSHOT_PLAN_FROZEN,
        (),
        len(snapshots),
    )
