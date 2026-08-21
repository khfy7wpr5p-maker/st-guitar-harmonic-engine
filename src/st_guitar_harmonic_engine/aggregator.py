"""Deterministic Stage 3-B candidate evidence aggregation.

Existing evidence producers stay authoritative for what they recognize. This
module only normalizes their outputs onto the Stage 3 resolver candidate
contract; it does not rank candidates or infer new musical facts.
"""

from __future__ import annotations

from .alterations import generate_altered_tension_candidates, generate_suspended_chord_candidates
from .analysis import analyze_frame_exact
from .context import TonalContext, resolve_frame_in_context
from .extensions import generate_extension_candidates
from .frames import HarmonicFrame
from .omissions import generate_incomplete_chord_candidates
from .resolver import (
    CandidateFamily,
    EvidenceSource,
    HarmonicIdentity,
    ResolverCandidate,
    evidence_precedence_index,
)


def _candidate(identity: HarmonicIdentity, sources: tuple[EvidenceSource, ...]) -> ResolverCandidate:
    return ResolverCandidate(
        identity=identity,
        evidence=tuple(sorted(set(sources), key=evidence_precedence_index)),
    )


def aggregate_frame_evidence(
    frame: HarmonicFrame,
    context: TonalContext | None = None,
) -> tuple[ResolverCandidate, ...]:
    """Normalize existing frame-local evidence into deterministic resolver candidates.

    Exact candidates are never discarded or overridden here. When exact analysis
    succeeds, lower-confidence omission/extension/suspension/alteration producers
    are not consulted. With no exact candidate, all bounded Stage 2 candidate
    evidence is retained and sorted canonically without ranking.
    """

    if not isinstance(frame, HarmonicFrame):
        raise TypeError("frame must be a HarmonicFrame")
    if context is not None and not isinstance(context, TonalContext):
        raise TypeError("context must be a TonalContext or None")

    exact = analyze_frame_exact(frame)
    if exact.candidates:
        contextual = resolve_frame_in_context(exact, context) if context is not None else None
        in_context = (
            {item.analysis.candidate for item in contextual.candidates if item.in_context}
            if contextual is not None
            else set()
        )
        candidates = []
        for item in exact.candidates:
            sources = [EvidenceSource.EXACT, EvidenceSource.BASS_INVERSION]
            if item.candidate in in_context:
                sources.append(EvidenceSource.TONAL_CONTEXT)
            candidates.append(
                _candidate(
                    HarmonicIdentity(
                        root_pc=item.candidate.root_pc,
                        family=CandidateFamily.BASIC,
                        variant=item.candidate.quality.value,
                    ),
                    tuple(sources),
                )
            )
        return tuple(sorted(candidates, key=lambda item: item.identity))

    candidates: list[ResolverCandidate] = []
    for item in generate_incomplete_chord_candidates(frame):
        candidates.append(
            _candidate(
                HarmonicIdentity(item.root_pc, CandidateFamily.BASIC, item.quality.value),
                (EvidenceSource.INCOMPLETE_CHORD,),
            )
        )
    for item in generate_extension_candidates(frame):
        candidates.append(
            _candidate(
                HarmonicIdentity(
                    item.root_pc,
                    CandidateFamily.EXTENSION,
                    f"{item.base_quality.value}:{item.extension.value}",
                ),
                (EvidenceSource.COLOR_TONE,),
            )
        )
    for item in generate_suspended_chord_candidates(frame):
        candidates.append(
            _candidate(
                HarmonicIdentity(item.root_pc, CandidateFamily.SUSPENDED, item.kind.value),
                (EvidenceSource.COLOR_TONE,),
            )
        )
    for item in generate_altered_tension_candidates(frame):
        candidates.append(
            _candidate(
                HarmonicIdentity(
                    item.root_pc,
                    CandidateFamily.ALTERED,
                    f"{item.base_quality.value}:{item.alteration.value}",
                ),
                (EvidenceSource.COLOR_TONE,),
            )
        )

    merged: dict[HarmonicIdentity, set[EvidenceSource]] = {}
    for item in candidates:
        merged.setdefault(item.identity, set()).update(item.evidence)
    return tuple(
        _candidate(identity, tuple(sources))
        for identity, sources in sorted(merged.items(), key=lambda pair: pair[0])
    )
