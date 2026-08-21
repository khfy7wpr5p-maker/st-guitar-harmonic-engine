"""Deterministic non-authoritative candidate ranking for Stage 4-C.

Ranking groups candidates for inspection and later gates. It never selects an
authoritative winner. Equal rank keys remain explicit ties.
"""

from __future__ import annotations

from dataclasses import dataclass

from .confidence import ConfidenceAssessment, ConfidenceState
from .resolver import EVIDENCE_PRECEDENCE, ResolverCandidate
from .strength import assess_candidate_strength


_STATE_ORDER = {
    ConfidenceState.STRONG: 0,
    ConfidenceState.BOUNDED: 1,
    ConfidenceState.WEAK: 2,
    ConfidenceState.INSUFFICIENT: 3,
}


@dataclass(frozen=True, slots=True)
class CandidateRankGroup:
    """One deterministic tie group. Group order is advisory, never authoritative."""

    assessment: ConfidenceAssessment
    candidates: tuple[ResolverCandidate, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.assessment, ConfidenceAssessment):
            raise TypeError("assessment must be a ConfidenceAssessment")
        if not isinstance(self.candidates, tuple) or not self.candidates or any(
            not isinstance(item, ResolverCandidate) for item in self.candidates
        ):
            raise TypeError("candidates must be a non-empty tuple of ResolverCandidate values")
        if len({item.identity for item in self.candidates}) != len(self.candidates):
            raise ValueError("rank group candidate identities must be unique")
        if tuple(sorted(self.candidates, key=lambda item: item.identity)) != self.candidates:
            raise ValueError("rank group candidates must use canonical identity order")
        for candidate in self.candidates:
            if assess_candidate_strength(candidate) != self.assessment:
                raise ValueError("all candidates in a rank group must share one assessment")


def _rank_key(candidate: ResolverCandidate) -> tuple[object, ...]:
    assessment = assess_candidate_strength(candidate)
    evidence = set(candidate.evidence)
    presence = tuple(source not in evidence for source in EVIDENCE_PRECEDENCE)
    return (_STATE_ORDER[assessment.state], presence, assessment.basis)


def rank_candidates(
    candidates: tuple[ResolverCandidate, ...],
) -> tuple[CandidateRankGroup, ...]:
    """Return deterministic advisory rank groups while preserving ties."""

    if not isinstance(candidates, tuple) or any(
        not isinstance(item, ResolverCandidate) for item in candidates
    ):
        raise TypeError("candidates must contain ResolverCandidate values")
    if len({item.identity for item in candidates}) != len(candidates):
        raise ValueError("candidate identities must be unique")
    if not candidates:
        return ()

    ordered = tuple(sorted(candidates, key=lambda item: (_rank_key(item), item.identity)))
    groups: list[CandidateRankGroup] = []
    index = 0
    while index < len(ordered):
        key = _rank_key(ordered[index])
        tied = []
        while index < len(ordered) and _rank_key(ordered[index]) == key:
            tied.append(ordered[index])
            index += 1
        tied_tuple = tuple(tied)
        groups.append(CandidateRankGroup(assess_candidate_strength(tied_tuple[0]), tied_tuple))
    return tuple(groups)
