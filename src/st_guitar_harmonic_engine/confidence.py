"""Deterministic Stage 4 confidence contract.

Confidence states are categorical evidence assessments. They are not calibrated
probabilities, accuracy estimates, or percentages. Empirical calibration belongs
to a separate benchmark-backed layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .resolver import EvidenceSource, evidence_precedence_index


class ConfidenceState(str, Enum):
    STRONG = "strong"
    BOUNDED = "bounded"
    WEAK = "weak"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True, slots=True)
class ConfidenceAssessment:
    state: ConfidenceState
    basis: tuple[EvidenceSource, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.state, ConfidenceState):
            raise TypeError("state must be a ConfidenceState")
        if not isinstance(self.basis, tuple) or any(
            not isinstance(item, EvidenceSource) for item in self.basis
        ):
            raise TypeError("basis must contain EvidenceSource values")
        if len(set(self.basis)) != len(self.basis):
            raise ValueError("confidence basis must not contain duplicates")
        expected = tuple(sorted(self.basis, key=evidence_precedence_index))
        if self.basis != expected:
            raise ValueError("confidence basis must follow canonical evidence precedence")
        if self.state is ConfidenceState.INSUFFICIENT and self.basis:
            raise ValueError("insufficient confidence cannot claim supporting evidence")


CONFIDENCE_SEMANTICS = "categorical_evidence_state_not_probability"
