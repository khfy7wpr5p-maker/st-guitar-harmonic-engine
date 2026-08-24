"""Deterministic Stage 3-B candidate evidence aggregation.

Existing evidence producers stay authoritative for what they recognize. This
module only normalizes their outputs onto the Stage 3 resolver candidate
contract; it does not rank candidates or infer new musical facts.
"""

from __future__ import annotations

from .alterations import (
    SuspendedChordKind,
    generate_altered_tension_candidates,
    generate_suspended_chord_candidates,
)
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
from .sixth_collision import SixthChordKind, build_sixth_chord_collision
from .spelling_resolution import select_spelling_supported_symmetric_candidate


def _candidate(identity: HarmonicIdentity, sources: tuple[EvidenceSource, ...]) -> ResolverCandidate:
    return ResolverCandidate(
        identity=identity,
        evidence=tuple(sorted(set(sources), key=evidence_precedence_index)),
    )


def _sixth_collision_identity(
    frame: HarmonicFrame,
    exact_identity: HarmonicIdentity,
) -> HarmonicIdentity | None:
    """Return the equal-pitch-set sixth identity for one exact seventh, if any.

    This is deliberately inverse-only: a sixth candidate is introduced only when
    the frozen exact analyzer has already recognized the mathematically colliding
    relative seventh quality and the observed pitch-class set matches the collision
    contract exactly. Root-position seventh evidence is protected: when the lowest
    sounding pitch is the recognized seventh root, the existing exact seventh result
    is retained and no sixth alternative is injected.
    """

    if exact_identity.family is not CandidateFamily.BASIC:
        return None
    if exact_identity.variant == "minor_seventh":
        kind = SixthChordKind.MAJOR_SIXTH
    elif exact_identity.variant == "half_diminished_seventh":
        kind = SixthChordKind.MINOR_SIXTH
    else:
        return None

    bass_pc = min(event.midi_pitch for event in frame.events) % 12
    if bass_pc == exact_identity.root_pc:
        return None

    sixth_root_pc = (exact_identity.root_pc + 3) % 12
    collision = build_sixth_chord_collision(sixth_root_pc, kind)
    if collision.competing_root_pc != exact_identity.root_pc:
        return None
    if collision.competing_variant != exact_identity.variant:
        return None
    if collision.pitch_classes != frame.pitch_classes:
        return None
    return HarmonicIdentity(
        sixth_root_pc,
        CandidateFamily.BASIC,
        kind.value,
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

    Equal-pitch-set major-sixth/minor-seventh and minor-sixth/half-diminished-
    seventh collisions are special safety cases. A sixth identity is added only as
    an equal EXACT alternative to the already-recognized exact seventh identity,
    and only when the existing exact seventh is not root-position in the bass.
    Until a separate candidate-specific tonal-context contract is merged, tonal
    context is intentionally withheld from both collision candidates so the
    authoritative resolver must preserve ambiguity.

    Complete-base extension and altered-dominant producers contribute structural
    support in addition to color-tone evidence because those producers already
    require the entire supported base chord plus exactly one validated color tone.
    Suspended triads remain weak color-tone evidence because their pitch sets may
    preserve dual-root ambiguity. Complete 7sus2/7sus4 candidates carry structural
    support because all four structural tones are present and the pitch-set root is
    unique within the supported suspended-seventh vocabulary.

    For symmetric exact augmented/diminished-seventh ties, validated written
    spelling may add STRUCTURAL support to exactly one candidate. Candidate
    identities are never removed here; the resolver decides whether that support
    is sufficient to narrow the exact tie.
    """

    if not isinstance(frame, HarmonicFrame):
        raise TypeError("frame must be a HarmonicFrame")
    if context is not None and not isinstance(context, TonalContext):
        raise TypeError("context must be a TonalContext or None")

    exact = analyze_frame_exact(frame)
    if exact.candidates:
        exact_identities = tuple(
            HarmonicIdentity(
                root_pc=item.candidate.root_pc,
                family=CandidateFamily.BASIC,
                variant=item.candidate.quality.value,
            )
            for item in exact.candidates
        )
        sixth_collision = (
            _sixth_collision_identity(frame, exact_identities[0])
            if len(exact_identities) == 1
            else None
        )

        contextual = (
            resolve_frame_in_context(exact, context)
            if context is not None and sixth_collision is None
            else None
        )
        in_context = (
            {item.analysis.candidate for item in contextual.candidates if item.in_context}
            if contextual is not None
            else set()
        )
        spelling_supported = select_spelling_supported_symmetric_candidate(
            frame,
            tuple(item.candidate for item in exact.candidates),
        )
        candidates = []
        for item, identity in zip(exact.candidates, exact_identities):
            sources = [EvidenceSource.EXACT, EvidenceSource.BASS_INVERSION]
            if item.candidate in in_context:
                sources.append(EvidenceSource.TONAL_CONTEXT)
            if spelling_supported is not None and item.candidate == spelling_supported:
                sources.append(EvidenceSource.STRUCTURAL)
            candidates.append(_candidate(identity, tuple(sources)))

        if sixth_collision is not None:
            candidates.append(
                _candidate(
                    sixth_collision,
                    (EvidenceSource.EXACT, EvidenceSource.BASS_INVERSION),
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
                (EvidenceSource.STRUCTURAL, EvidenceSource.COLOR_TONE),
            )
        )
    for item in generate_suspended_chord_candidates(frame):
        suspended_sources = (
            (EvidenceSource.STRUCTURAL, EvidenceSource.COLOR_TONE)
            if item.kind
            in {SuspendedChordKind.SEVENTH_SUS2, SuspendedChordKind.SEVENTH_SUS4}
            else (EvidenceSource.COLOR_TONE,)
        )
        candidates.append(
            _candidate(
                HarmonicIdentity(item.root_pc, CandidateFamily.SUSPENDED, item.kind.value),
                suspended_sources,
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
                (EvidenceSource.STRUCTURAL, EvidenceSource.COLOR_TONE),
            )
        )

    merged: dict[HarmonicIdentity, set[EvidenceSource]] = {}
    for item in candidates:
        merged.setdefault(item.identity, set()).update(item.evidence)
    return tuple(
        _candidate(identity, tuple(sources))
        for identity, sources in sorted(merged.items(), key=lambda pair: pair[0])
    )
