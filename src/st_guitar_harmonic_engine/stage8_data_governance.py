"""Fail-closed Stage 8-A data governance contract v0.1.

This module governs research-data provenance and rights metadata only. It does not
load training examples, start training, tune from Teacher-Gold/HOLDOUT, grant model
authority, or change the deterministic harmonic resolver.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re


STAGE8_DATA_GOVERNANCE_VERSION = "0.1"
_SOURCE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
_LICENSE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+_-]{1,63}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class Stage8DatasetRole(str, Enum):
    TRAIN_CANDIDATE = "train_candidate"
    VALIDATION_CANDIDATE = "validation_candidate"
    REFERENCE_ONLY = "reference_only"


class Stage8LicenseClass(str, Enum):
    OWNED = "owned"
    PERMISSIVE_COMMERCIAL = "permissive_commercial"
    EXPLICIT_TRAINING_GRANT = "explicit_training_grant"
    NONCOMMERCIAL = "noncommercial"
    UNKNOWN = "unknown"


class Stage8DataGovernanceStatus(str, Enum):
    BLOCKED_EMPTY_MANIFEST = "blocked_empty_manifest"
    BLOCKED_DATA_LEAKAGE = "blocked_data_leakage"
    BLOCKED_PRIVACY_RISK = "blocked_privacy_risk"
    BLOCKED_RIGHTS = "blocked_rights"
    BLOCKED_INTEGRITY = "blocked_integrity"
    DATASET_DESIGN_ELIGIBLE = "dataset_design_eligible"


_TRAINING_RIGHTS_LICENSES = frozenset(
    {
        Stage8LicenseClass.OWNED,
        Stage8LicenseClass.PERMISSIVE_COMMERCIAL,
        Stage8LicenseClass.EXPLICIT_TRAINING_GRANT,
    }
)


@dataclass(frozen=True, slots=True)
class Stage8DataSourceManifest:
    """Aggregate provenance/rights metadata for one source snapshot.

    No raw examples or labels are carried by this contract.
    """

    source_id: str
    role: Stage8DatasetRole
    case_count: int
    license_id: str
    license_class: Stage8LicenseClass
    provenance_sha256: str
    content_sha256: str
    frozen_snapshot: bool
    training_rights_confirmed: bool
    commercial_use_allowed: bool
    teacher_gold_overlap_count: int
    holdout_overlap_count: int
    derived_from_holdout_labels: bool
    contains_personal_data: bool

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or _SOURCE_ID_RE.fullmatch(self.source_id) is None:
            raise ValueError("source_id must be a canonical 3..64 character token")
        if not isinstance(self.role, Stage8DatasetRole):
            raise TypeError("role must be Stage8DatasetRole")
        if isinstance(self.case_count, bool) or not isinstance(self.case_count, int) or self.case_count < 0:
            raise ValueError("case_count must be a non-negative int")
        if not isinstance(self.license_id, str) or _LICENSE_ID_RE.fullmatch(self.license_id) is None:
            raise ValueError("license_id must be a canonical token")
        if not isinstance(self.license_class, Stage8LicenseClass):
            raise TypeError("license_class must be Stage8LicenseClass")
        for name in ("provenance_sha256", "content_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
                raise ValueError(f"{name} must be lowercase SHA-256")
        for name in (
            "frozen_snapshot",
            "training_rights_confirmed",
            "commercial_use_allowed",
            "derived_from_holdout_labels",
            "contains_personal_data",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")
        for name in ("teacher_gold_overlap_count", "holdout_overlap_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative int")
            if value > self.case_count:
                raise ValueError(f"{name} cannot exceed case_count")

    @property
    def has_reference_leakage(self) -> bool:
        return (
            self.teacher_gold_overlap_count > 0
            or self.holdout_overlap_count > 0
            or self.derived_from_holdout_labels
        )

    @property
    def is_training_role(self) -> bool:
        return self.role in {
            Stage8DatasetRole.TRAIN_CANDIDATE,
            Stage8DatasetRole.VALIDATION_CANDIDATE,
        }

    @property
    def has_training_rights(self) -> bool:
        return (
            self.license_class in _TRAINING_RIGHTS_LICENSES
            and self.training_rights_confirmed
            and self.commercial_use_allowed
        )


@dataclass(frozen=True, slots=True)
class Stage8DataGovernanceAssessment:
    status: Stage8DataGovernanceStatus
    reasons: tuple[str, ...]
    source_count: int
    case_count: int
    training_candidate_case_count: int
    validation_candidate_case_count: int
    reference_only_case_count: int
    model_training_authorized: bool = False
    production_authority_granted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.status, Stage8DataGovernanceStatus):
            raise TypeError("status must be Stage8DataGovernanceStatus")
        if not isinstance(self.reasons, tuple) or any(
            not isinstance(item, str) or not item for item in self.reasons
        ):
            raise TypeError("reasons must contain non-empty strings")
        if tuple(sorted(set(self.reasons))) != self.reasons:
            raise ValueError("reasons must be unique canonical order")
        for name in (
            "source_count",
            "case_count",
            "training_candidate_case_count",
            "validation_candidate_case_count",
            "reference_only_case_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative int")
        if (
            self.training_candidate_case_count
            + self.validation_candidate_case_count
            + self.reference_only_case_count
            != self.case_count
        ):
            raise ValueError("role case counts must sum to case_count")
        if self.model_training_authorized or self.production_authority_granted:
            raise ValueError("data governance cannot authorize training or production")
        if self.status is Stage8DataGovernanceStatus.DATASET_DESIGN_ELIGIBLE and self.reasons:
            raise ValueError("eligible assessment cannot contain blocking reasons")
        if self.status is not Stage8DataGovernanceStatus.DATASET_DESIGN_ELIGIBLE and not self.reasons:
            raise ValueError("blocked assessment requires reasons")


def _assessment(
    status: Stage8DataGovernanceStatus,
    reasons: tuple[str, ...],
    sources: tuple[Stage8DataSourceManifest, ...],
) -> Stage8DataGovernanceAssessment:
    return Stage8DataGovernanceAssessment(
        status=status,
        reasons=tuple(sorted(set(reasons))),
        source_count=len(sources),
        case_count=sum(item.case_count for item in sources),
        training_candidate_case_count=sum(
            item.case_count for item in sources if item.role is Stage8DatasetRole.TRAIN_CANDIDATE
        ),
        validation_candidate_case_count=sum(
            item.case_count for item in sources if item.role is Stage8DatasetRole.VALIDATION_CANDIDATE
        ),
        reference_only_case_count=sum(
            item.case_count for item in sources if item.role is Stage8DatasetRole.REFERENCE_ONLY
        ),
    )


def assess_stage8_data_governance(
    sources: tuple[Stage8DataSourceManifest, ...],
) -> Stage8DataGovernanceAssessment:
    """Assess whether a source manifest is safe enough for dataset design.

    DATASET_DESIGN_ELIGIBLE is not training authorization. It only means the
    aggregate source manifest passes provenance, leakage, privacy, and rights gates
    required before a separate training-plan review could even be proposed.
    """

    if not isinstance(sources, tuple) or any(
        not isinstance(item, Stage8DataSourceManifest) for item in sources
    ):
        raise TypeError("sources must contain Stage8DataSourceManifest values")
    if not sources:
        return _assessment(
            Stage8DataGovernanceStatus.BLOCKED_EMPTY_MANIFEST,
            ("source_manifest_is_empty",),
            sources,
        )

    source_ids = [item.source_id for item in sources]
    content_hashes = [item.content_sha256 for item in sources]
    if len(set(source_ids)) != len(source_ids) or len(set(content_hashes)) != len(content_hashes):
        return _assessment(
            Stage8DataGovernanceStatus.BLOCKED_INTEGRITY,
            ("duplicate_source_identity_or_content_snapshot",),
            sources,
        )

    leakage: list[str] = []
    for item in sources:
        if item.teacher_gold_overlap_count:
            leakage.append(f"{item.source_id}:teacher_gold_overlap")
        if item.holdout_overlap_count:
            leakage.append(f"{item.source_id}:holdout_overlap")
        if item.derived_from_holdout_labels:
            leakage.append(f"{item.source_id}:derived_from_holdout_labels")
    if leakage:
        return _assessment(
            Stage8DataGovernanceStatus.BLOCKED_DATA_LEAKAGE,
            tuple(leakage),
            sources,
        )

    privacy = tuple(
        f"{item.source_id}:contains_personal_data"
        for item in sources
        if item.contains_personal_data
    )
    if privacy:
        return _assessment(
            Stage8DataGovernanceStatus.BLOCKED_PRIVACY_RISK,
            privacy,
            sources,
        )

    integrity: list[str] = []
    for item in sources:
        if item.case_count == 0:
            integrity.append(f"{item.source_id}:empty_source")
        if not item.frozen_snapshot:
            integrity.append(f"{item.source_id}:snapshot_not_frozen")
    if integrity:
        return _assessment(
            Stage8DataGovernanceStatus.BLOCKED_INTEGRITY,
            tuple(integrity),
            sources,
        )

    rights: list[str] = []
    for item in sources:
        if not item.is_training_role:
            continue
        if item.license_class in {Stage8LicenseClass.NONCOMMERCIAL, Stage8LicenseClass.UNKNOWN}:
            rights.append(f"{item.source_id}:license_not_training_eligible")
        if not item.training_rights_confirmed:
            rights.append(f"{item.source_id}:training_rights_not_confirmed")
        if not item.commercial_use_allowed:
            rights.append(f"{item.source_id}:commercial_use_not_allowed")
        if item.license_class not in _TRAINING_RIGHTS_LICENSES:
            rights.append(f"{item.source_id}:license_class_not_approved")
    if rights:
        return _assessment(
            Stage8DataGovernanceStatus.BLOCKED_RIGHTS,
            tuple(rights),
            sources,
        )

    if not any(item.role is Stage8DatasetRole.TRAIN_CANDIDATE for item in sources):
        return _assessment(
            Stage8DataGovernanceStatus.BLOCKED_RIGHTS,
            ("no_training_candidate_source",),
            sources,
        )

    return _assessment(Stage8DataGovernanceStatus.DATASET_DESIGN_ELIGIBLE, (), sources)
