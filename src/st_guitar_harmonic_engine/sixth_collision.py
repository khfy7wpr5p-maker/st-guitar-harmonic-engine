"""Fail-closed sixth-chord collision contract.

Major-sixth and minor-sixth pitch sets collide exactly with relative minor-seventh
and half-diminished-seventh pitch sets. This module documents and validates that
collision without adding any sixth-chord runtime producer or resolver authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .resolver import EvidenceSource


SIXTH_COLLISION_CONTRACT_VERSION = "0.1"


class SixthChordKind(str, Enum):
    MAJOR_SIXTH = "major_sixth"
    MINOR_SIXTH = "minor_sixth"


class SixthCollisionDisposition(str, Enum):
    PRESERVE_AMBIGUITY = "preserve_ambiguity"
    CONTEXT_ELIGIBLE = "context_eligible"


# Bass, spelling, generic structure, adjacency, or voice-leading do not by
# themselves establish a safe root choice for an equal pitch-set sixth collision.
# Explicit tonal context is the only currently permitted evidence class that may
# make a future candidate-specific disambiguation attempt eligible. Eligibility is
# not a resolution decision and does not grant authority by itself.
SIXTH_COLLISION_PERMITTED_DISAMBIGUATORS: tuple[EvidenceSource, ...] = (
    EvidenceSource.TONAL_CONTEXT,
)


@dataclass(frozen=True, slots=True)
class SixthChordCollision:
    sixth_root_pc: int
    sixth_kind: SixthChordKind
    competing_root_pc: int
    competing_variant: str
    pitch_classes: tuple[int, ...]

    def __post_init__(self) -> None:
        for field_name in ("sixth_root_pc", "competing_root_pc"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{field_name} must be an int")
            if not 0 <= value <= 11:
                raise ValueError(f"{field_name} must be between 0 and 11")
        if not isinstance(self.sixth_kind, SixthChordKind):
            raise TypeError("sixth_kind must be a SixthChordKind")
        if self.competing_variant not in {"minor_seventh", "half_diminished_seventh"}:
            raise ValueError("competing_variant is unsupported")
        if tuple(sorted(set(self.pitch_classes))) != self.pitch_classes:
            raise ValueError("pitch_classes must be unique canonical order")
        if len(self.pitch_classes) != 4:
            raise ValueError("sixth collision must contain four pitch classes")
        if any(not 0 <= pc <= 11 for pc in self.pitch_classes):
            raise ValueError("pitch_classes must be between 0 and 11")


def build_sixth_chord_collision(
    root_pc: int,
    kind: SixthChordKind,
) -> SixthChordCollision:
    """Return the exact equal-pitch-set seventh-chord collision for one sixth chord."""

    if isinstance(root_pc, bool) or not isinstance(root_pc, int):
        raise TypeError("root_pc must be an int")
    if not 0 <= root_pc <= 11:
        raise ValueError("root_pc must be between 0 and 11")
    if not isinstance(kind, SixthChordKind):
        raise TypeError("kind must be a SixthChordKind")

    if kind is SixthChordKind.MAJOR_SIXTH:
        sixth_intervals = (0, 4, 7, 9)
        competing_variant = "minor_seventh"
    else:
        sixth_intervals = (0, 3, 7, 9)
        competing_variant = "half_diminished_seventh"

    competing_root_pc = (root_pc + 9) % 12
    pitch_classes = tuple(sorted((root_pc + interval) % 12 for interval in sixth_intervals))
    return SixthChordCollision(
        sixth_root_pc=root_pc,
        sixth_kind=kind,
        competing_root_pc=competing_root_pc,
        competing_variant=competing_variant,
        pitch_classes=pitch_classes,
    )


def assess_sixth_collision_evidence(
    evidence: tuple[EvidenceSource, ...],
) -> SixthCollisionDisposition:
    """Return whether candidate-specific contextual disambiguation may be attempted.

    This gate never chooses a root. Without explicit tonal-context evidence the
    collision must remain ambiguous. Even with tonal context the caller still
    needs a separate deterministic, candidate-specific rule before any resolution
    is allowed.
    """

    if not isinstance(evidence, tuple) or any(
        not isinstance(item, EvidenceSource) for item in evidence
    ):
        raise TypeError("evidence must contain EvidenceSource values")
    if len(set(evidence)) != len(evidence):
        raise ValueError("evidence sources must be unique")

    if any(source in evidence for source in SIXTH_COLLISION_PERMITTED_DISAMBIGUATORS):
        return SixthCollisionDisposition.CONTEXT_ELIGIBLE
    return SixthCollisionDisposition.PRESERVE_AMBIGUITY
