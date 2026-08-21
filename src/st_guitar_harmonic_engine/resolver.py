"""Stage 3 authoritative harmonic resolver contracts.

This module defines deterministic resolver state and evidence precedence only.
It does not aggregate evidence or change any Stage 1/2 decision path.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ResolverStatus(str, Enum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    NO_MATCH = "no_match"


class CandidateFamily(str, Enum):
    BASIC = "basic"
    EXTENSION = "extension"
    SUSPENDED = "suspended"
    ALTERED = "altered"


class EvidenceSource(str, Enum):
    EXACT = "exact"
    TONAL_CONTEXT = "tonal_context"
    STRUCTURAL = "structural"
    BASS_INVERSION = "bass_inversion"
    VERIFIED_NCT = "verified_nct"
    INCOMPLETE_CHORD = "incomplete_chord"
    COLOR_TONE = "color_tone"
    ADJACENT_CONTEXT = "adjacent_context"
    VOICE_FUNCTION = "voice_function"


EVIDENCE_PRECEDENCE: tuple[EvidenceSource, ...] = (
    EvidenceSource.EXACT,
    EvidenceSource.TONAL_CONTEXT,
    EvidenceSource.STRUCTURAL,
    EvidenceSource.BASS_INVERSION,
    EvidenceSource.VERIFIED_NCT,
    EvidenceSource.INCOMPLETE_CHORD,
    EvidenceSource.COLOR_TONE,
    EvidenceSource.ADJACENT_CONTEXT,
    EvidenceSource.VOICE_FUNCTION,
)


@dataclass(frozen=True, slots=True, order=True)
class HarmonicIdentity:
    """Stable identity for one harmonic candidate across evidence layers."""

    root_pc: int
    family: CandidateFamily
    variant: str

    def __post_init__(self) -> None:
        if isinstance(self.root_pc, bool) or not isinstance(self.root_pc, int):
            raise TypeError("root_pc must be an int")
        if not 0 <= self.root_pc <= 11:
            raise ValueError("root_pc must be between 0 and 11")
        if not isinstance(self.family, CandidateFamily):
            raise TypeError("family must be a CandidateFamily")
        if not isinstance(self.variant, str):
            raise TypeError("variant must be a str")
        if not self.variant or self.variant != self.variant.strip():
            raise ValueError("variant must be a non-empty canonical token")


@dataclass(frozen=True, slots=True)
class ResolverCandidate:
    identity: HarmonicIdentity
    evidence: tuple[EvidenceSource, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.identity, HarmonicIdentity):
            raise TypeError("identity must be a HarmonicIdentity")
        if not isinstance(self.evidence, tuple) or any(
            not isinstance(item, EvidenceSource) for item in self.evidence
        ):
            raise TypeError("evidence must contain EvidenceSource values")
        if len(set(self.evidence)) != len(self.evidence):
            raise ValueError("evidence sources must be unique")
        expected = tuple(sorted(self.evidence, key=evidence_precedence_index))
        if self.evidence != expected:
            raise ValueError("evidence must follow canonical precedence order")


@dataclass(frozen=True, slots=True)
class ResolverDecision:
    """Authoritative Stage 3 decision contract before Stage 4 abstention."""

    status: ResolverStatus
    candidates: tuple[ResolverCandidate, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, ResolverStatus):
            raise TypeError("status must be a ResolverStatus")
        if not isinstance(self.candidates, tuple) or any(
            not isinstance(item, ResolverCandidate) for item in self.candidates
        ):
            raise TypeError("candidates must contain ResolverCandidate values")
        if len({item.identity for item in self.candidates}) != len(self.candidates):
            raise ValueError("candidate identities must be unique")
        expected = (
            ResolverStatus.NO_MATCH
            if not self.candidates
            else ResolverStatus.RESOLVED
            if len(self.candidates) == 1
            else ResolverStatus.AMBIGUOUS
        )
        if self.status is not expected:
            raise ValueError("status does not match candidate cardinality")


def evidence_precedence_index(source: EvidenceSource) -> int:
    if not isinstance(source, EvidenceSource):
        raise TypeError("source must be an EvidenceSource")
    return EVIDENCE_PRECEDENCE.index(source)


def stronger_evidence(left: EvidenceSource, right: EvidenceSource) -> EvidenceSource:
    """Return the higher-precedence source without applying any candidate policy."""

    return left if evidence_precedence_index(left) <= evidence_precedence_index(right) else right
