"""Conservative cadential / functional evidence for Stage 3-E.

Only an explicit tonal context and an unambiguous adjacent basic candidate may
support the bounded dominant-to-tonic relation. This layer annotates candidates
only; it never creates, removes, ranks, or resolves them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .context import TonalContext, TonalMode
from .resolver import (
    CandidateFamily,
    EvidenceSource,
    HarmonicIdentity,
    ResolverCandidate,
    evidence_precedence_index,
)


class FunctionalRelation(str, Enum):
    DOMINANT_TO_TONIC = "dominant_to_tonic"


@dataclass(frozen=True, slots=True)
class FunctionalObservation:
    identity: HarmonicIdentity
    relation: FunctionalRelation
    from_previous: bool
    to_next: bool

    def __post_init__(self) -> None:
        if not isinstance(self.identity, HarmonicIdentity):
            raise TypeError("identity must be a HarmonicIdentity")
        if not isinstance(self.relation, FunctionalRelation):
            raise TypeError("relation must be a FunctionalRelation")
        if not isinstance(self.from_previous, bool) or not isinstance(self.to_next, bool):
            raise TypeError("relation flags must be bool values")
        if not self.from_previous and not self.to_next:
            raise ValueError("functional observation requires a realized relation")


def _is_tonic(identity: HarmonicIdentity, context: TonalContext) -> bool:
    if identity.family is not CandidateFamily.BASIC or identity.root_pc != context.tonic_pc:
        return False
    expected = "major" if context.mode is TonalMode.MAJOR else "minor"
    return identity.variant in {expected, f"{expected}_seventh"}


def _is_dominant(identity: HarmonicIdentity, context: TonalContext) -> bool:
    if identity.family is not CandidateFamily.BASIC:
        return False
    if identity.root_pc != (context.tonic_pc + 7) % 12:
        return False
    if context.mode is TonalMode.MAJOR:
        return identity.variant in {"major", "dominant_seventh"}
    return identity.variant in {"minor", "minor_seventh", "major", "dominant_seventh"}


def observe_functional_relations(
    current: tuple[ResolverCandidate, ...],
    context: TonalContext,
    previous: tuple[ResolverCandidate, ...] = (),
    next_: tuple[ResolverCandidate, ...] = (),
) -> tuple[FunctionalObservation, ...]:
    if not isinstance(context, TonalContext):
        raise TypeError("context must be a TonalContext")
    for name, values in (("current", current), ("previous", previous), ("next_", next_)):
        if not isinstance(values, tuple) or any(not isinstance(item, ResolverCandidate) for item in values):
            raise TypeError(f"{name} must contain ResolverCandidate values")

    previous_identity = previous[0].identity if len(previous) == 1 else None
    next_identity = next_[0].identity if len(next_) == 1 else None
    result = []
    for candidate in current:
        from_previous = (
            previous_identity is not None
            and _is_dominant(previous_identity, context)
            and _is_tonic(candidate.identity, context)
        )
        to_next = (
            next_identity is not None
            and _is_dominant(candidate.identity, context)
            and _is_tonic(next_identity, context)
        )
        if from_previous or to_next:
            result.append(
                FunctionalObservation(
                    identity=candidate.identity,
                    relation=FunctionalRelation.DOMINANT_TO_TONIC,
                    from_previous=from_previous,
                    to_next=to_next,
                )
            )
    return tuple(result)


def annotate_functional_relations(
    current: tuple[ResolverCandidate, ...],
    context: TonalContext,
    previous: tuple[ResolverCandidate, ...] = (),
    next_: tuple[ResolverCandidate, ...] = (),
) -> tuple[ResolverCandidate, ...]:
    supported = {
        item.identity
        for item in observe_functional_relations(current, context, previous, next_)
    }
    result = []
    for candidate in current:
        evidence = set(candidate.evidence)
        if candidate.identity in supported:
            evidence.add(EvidenceSource.VOICE_FUNCTION)
        result.append(
            ResolverCandidate(
                candidate.identity,
                tuple(sorted(evidence, key=evidence_precedence_index)),
            )
        )
    return tuple(result)
