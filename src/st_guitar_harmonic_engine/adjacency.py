"""Bounded previous/next harmonic-context evidence.

Adjacent frames may add continuity evidence to candidates already present in the
current frame. They cannot create candidates, remove exact evidence, or select a
winner. This keeps neighboring context below all structural evidence in the
Stage 3 precedence contract.
"""

from __future__ import annotations

from dataclasses import dataclass

from .resolver import EvidenceSource, HarmonicIdentity, ResolverCandidate, evidence_precedence_index


@dataclass(frozen=True, slots=True)
class AdjacentContextObservation:
    identity: HarmonicIdentity
    previous_match: bool
    next_match: bool

    def __post_init__(self) -> None:
        if not isinstance(self.identity, HarmonicIdentity):
            raise TypeError("identity must be a HarmonicIdentity")
        if not isinstance(self.previous_match, bool) or not isinstance(self.next_match, bool):
            raise TypeError("adjacent match flags must be bool values")
        if not self.previous_match and not self.next_match:
            raise ValueError("observation requires at least one adjacent match")


def observe_adjacent_context(
    current: tuple[ResolverCandidate, ...],
    previous: tuple[ResolverCandidate, ...] = (),
    next_: tuple[ResolverCandidate, ...] = (),
) -> tuple[AdjacentContextObservation, ...]:
    for name, values in (("current", current), ("previous", previous), ("next_", next_)):
        if not isinstance(values, tuple) or any(not isinstance(item, ResolverCandidate) for item in values):
            raise TypeError(f"{name} must contain ResolverCandidate values")

    previous_ids = {item.identity for item in previous}
    next_ids = {item.identity for item in next_}
    return tuple(
        AdjacentContextObservation(
            identity=item.identity,
            previous_match=item.identity in previous_ids,
            next_match=item.identity in next_ids,
        )
        for item in current
        if item.identity in previous_ids or item.identity in next_ids
    )


def annotate_adjacent_context(
    current: tuple[ResolverCandidate, ...],
    previous: tuple[ResolverCandidate, ...] = (),
    next_: tuple[ResolverCandidate, ...] = (),
) -> tuple[ResolverCandidate, ...]:
    """Add low-precedence continuity evidence without changing candidate cardinality."""

    observations = observe_adjacent_context(current, previous, next_)
    supported = {item.identity for item in observations}
    result = []
    for candidate in current:
        evidence = set(candidate.evidence)
        if candidate.identity in supported:
            evidence.add(EvidenceSource.ADJACENT_CONTEXT)
        result.append(
            ResolverCandidate(
                identity=candidate.identity,
                evidence=tuple(sorted(evidence, key=evidence_precedence_index)),
            )
        )
    return tuple(result)
