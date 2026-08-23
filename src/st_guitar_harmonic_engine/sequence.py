"""Deterministic Stage 3-H global harmonic sequence resolver.

The resolver composes validated Stage 3 evidence without probabilistic scoring.
Exact ambiguity is never broken by weak sequential evidence. Explicit tonal
context may narrow exact candidates, and validated written-spelling support may
narrow only a symmetric exact tie through STRUCTURAL evidence. Non-exact
candidates are narrowed lexicographically by the published evidence precedence,
preserving ties.
"""

from __future__ import annotations

from dataclasses import dataclass

from .adjacency import annotate_adjacent_context
from .aggregator import aggregate_frame_evidence
from .frames import HarmonicFrame
from .functional import annotate_functional_relations
from .local_context import LocalTonalContextPlan
from .phrase import PhrasePlan, phrase_bounded_neighbors
from .resolver import (
    EVIDENCE_PRECEDENCE,
    EvidenceSource,
    ResolverCandidate,
    ResolverDecision,
    ResolverStatus,
)
from .voice_leading import annotate_voice_leading


@dataclass(frozen=True, slots=True)
class SequenceResolution:
    candidates: tuple[tuple[ResolverCandidate, ...], ...]
    decisions: tuple[ResolverDecision, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.candidates, tuple) or any(
            not isinstance(frame, tuple) or any(not isinstance(item, ResolverCandidate) for item in frame)
            for frame in self.candidates
        ):
            raise TypeError("candidates must contain tuples of ResolverCandidate values")
        if not isinstance(self.decisions, tuple) or any(
            not isinstance(item, ResolverDecision) for item in self.decisions
        ):
            raise TypeError("decisions must contain ResolverDecision values")
        if len(self.candidates) != len(self.decisions):
            raise ValueError("candidate and decision sequences must have equal length")
        for candidates, decision in zip(self.candidates, self.decisions):
            candidate_ids = {item.identity for item in candidates}
            if any(item.identity not in candidate_ids for item in decision.candidates):
                raise ValueError("decision cannot reference a candidate outside its frame")


def resolve_candidates_by_precedence(
    candidates: tuple[ResolverCandidate, ...],
) -> ResolverDecision:
    """Resolve one candidate set using explicit lexicographic precedence.

    Exact ambiguity is deliberately special-cased. Explicit tonal context may
    narrow it. A unique STRUCTURAL marker may also narrow it, but the only exact
    path that emits such a marker is the fail-closed symmetric written-spelling
    check in the evidence aggregator. If tonal and structural support conflict,
    exact ambiguity is preserved rather than forcing a root.
    """

    if not isinstance(candidates, tuple) or any(
        not isinstance(item, ResolverCandidate) for item in candidates
    ):
        raise TypeError("candidates must contain ResolverCandidate values")
    if len({item.identity for item in candidates}) != len(candidates):
        raise ValueError("candidate identities must be unique")

    pool = tuple(sorted(candidates, key=lambda item: item.identity))
    if not pool:
        return ResolverDecision(ResolverStatus.NO_MATCH, ())
    if len(pool) == 1:
        return ResolverDecision(ResolverStatus.RESOLVED, pool)

    exact = tuple(item for item in pool if EvidenceSource.EXACT in item.evidence)
    if exact:
        contextual = tuple(
            item for item in exact if EvidenceSource.TONAL_CONTEXT in item.evidence
        )
        structural = tuple(
            item for item in exact if EvidenceSource.STRUCTURAL in item.evidence
        )
        if len(contextual) == 1 and len(structural) == 1:
            if contextual[0].identity != structural[0].identity:
                return ResolverDecision(ResolverStatus.AMBIGUOUS, exact)
            return ResolverDecision(ResolverStatus.RESOLVED, contextual)
        if len(contextual) == 1:
            return ResolverDecision(ResolverStatus.RESOLVED, contextual)
        if len(structural) == 1:
            return ResolverDecision(ResolverStatus.RESOLVED, structural)
        if len(exact) == 1:
            return ResolverDecision(ResolverStatus.RESOLVED, exact)
        return ResolverDecision(ResolverStatus.AMBIGUOUS, exact)

    narrowed = pool
    for source in EVIDENCE_PRECEDENCE[1:]:
        supported = tuple(item for item in narrowed if source in item.evidence)
        if supported:
            narrowed = supported
        if len(narrowed) == 1:
            return ResolverDecision(ResolverStatus.RESOLVED, narrowed)
    return ResolverDecision(ResolverStatus.AMBIGUOUS, narrowed)


def resolve_harmonic_sequence(
    frames: tuple[HarmonicFrame, ...],
    local_context: LocalTonalContextPlan | None = None,
    phrase_plan: PhrasePlan | None = None,
) -> SequenceResolution:
    """Aggregate, annotate, and deterministically resolve an ordered frame sequence.

    Sequential evidence is enabled only when an explicit ``phrase_plan`` places
    neighboring frames in the same phrase. Without one, frames remain isolated.
    """

    if not isinstance(frames, tuple) or any(not isinstance(frame, HarmonicFrame) for frame in frames):
        raise TypeError("frames must contain HarmonicFrame values")
    if local_context is not None and not isinstance(local_context, LocalTonalContextPlan):
        raise TypeError("local_context must be a LocalTonalContextPlan or None")
    if phrase_plan is not None and not isinstance(phrase_plan, PhrasePlan):
        raise TypeError("phrase_plan must be a PhrasePlan or None")

    contexts = (
        local_context.contexts_for(len(frames))
        if local_context is not None
        else (None,) * len(frames)
    )
    if phrase_plan is not None:
        phrase_plan.validate_frame_count(len(frames))

    base = tuple(
        aggregate_frame_evidence(frame, context)
        for frame, context in zip(frames, contexts)
    )

    annotated: list[tuple[ResolverCandidate, ...]] = []
    for index, current in enumerate(base):
        if phrase_plan is None:
            previous, next_ = (), ()
        else:
            previous, next_ = phrase_bounded_neighbors(base, index, phrase_plan)

        current = annotate_adjacent_context(current, previous, next_)
        current = annotate_voice_leading(current, previous, next_)
        context = contexts[index]
        if context is not None:
            current = annotate_functional_relations(current, context, previous, next_)
        annotated.append(current)

    candidate_sequence = tuple(annotated)
    decisions = tuple(resolve_candidates_by_precedence(frame) for frame in candidate_sequence)
    return SequenceResolution(candidate_sequence, decisions)
