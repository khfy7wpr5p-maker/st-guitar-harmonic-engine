"""Conservative deterministic voice-leading evidence.

This layer compares implied pitch-class sets for basic harmonic candidates. It
only adds lowest-tier support when an unambiguous neighboring basic candidate
has at least two common-or-stepwise pitch-class links to the current candidate.
It never creates candidates or makes an authoritative decision.
"""

from __future__ import annotations

from dataclasses import dataclass

from .chords import ChordQuality
from .resolver import (
    CandidateFamily,
    EvidenceSource,
    HarmonicIdentity,
    ResolverCandidate,
    evidence_precedence_index,
)

_INTERVALS = {
    ChordQuality.MAJOR: frozenset({0, 4, 7}),
    ChordQuality.MINOR: frozenset({0, 3, 7}),
    ChordQuality.DIMINISHED: frozenset({0, 3, 6}),
    ChordQuality.AUGMENTED: frozenset({0, 4, 8}),
    ChordQuality.DOMINANT_SEVENTH: frozenset({0, 4, 7, 10}),
    ChordQuality.MAJOR_SEVENTH: frozenset({0, 4, 7, 11}),
    ChordQuality.MINOR_SEVENTH: frozenset({0, 3, 7, 10}),
    ChordQuality.HALF_DIMINISHED_SEVENTH: frozenset({0, 3, 6, 10}),
    ChordQuality.DIMINISHED_SEVENTH: frozenset({0, 3, 6, 9}),
}


@dataclass(frozen=True, slots=True)
class VoiceLeadingObservation:
    identity: HarmonicIdentity
    previous_links: int
    next_links: int

    def __post_init__(self) -> None:
        if not isinstance(self.identity, HarmonicIdentity):
            raise TypeError("identity must be a HarmonicIdentity")
        for value in (self.previous_links, self.next_links):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError("link counts must be ints")
            if value < 0:
                raise ValueError("link counts cannot be negative")
        if self.previous_links < 2 and self.next_links < 2:
            raise ValueError("voice-leading observation requires at least two bounded links")


def _pitch_classes(identity: HarmonicIdentity) -> frozenset[int] | None:
    if identity.family is not CandidateFamily.BASIC:
        return None
    try:
        quality = ChordQuality(identity.variant)
    except ValueError:
        return None
    return frozenset((identity.root_pc + interval) % 12 for interval in _INTERVALS[quality])


def _circular_distance(left: int, right: int) -> int:
    distance = abs(left - right) % 12
    return min(distance, 12 - distance)


def _bounded_links(source: HarmonicIdentity, target: HarmonicIdentity) -> int:
    source_pcs = _pitch_classes(source)
    target_pcs = _pitch_classes(target)
    if source_pcs is None or target_pcs is None:
        return 0
    return sum(
        1
        for target_pc in target_pcs
        if any(_circular_distance(source_pc, target_pc) <= 2 for source_pc in source_pcs)
    )


def observe_voice_leading(
    current: tuple[ResolverCandidate, ...],
    previous: tuple[ResolverCandidate, ...] = (),
    next_: tuple[ResolverCandidate, ...] = (),
) -> tuple[VoiceLeadingObservation, ...]:
    for name, values in (("current", current), ("previous", previous), ("next_", next_)):
        if not isinstance(values, tuple) or any(not isinstance(item, ResolverCandidate) for item in values):
            raise TypeError(f"{name} must contain ResolverCandidate values")

    previous_identity = previous[0].identity if len(previous) == 1 else None
    next_identity = next_[0].identity if len(next_) == 1 else None
    result = []
    for item in current:
        previous_links = _bounded_links(previous_identity, item.identity) if previous_identity is not None else 0
        next_links = _bounded_links(item.identity, next_identity) if next_identity is not None else 0
        if previous_links >= 2 or next_links >= 2:
            result.append(VoiceLeadingObservation(item.identity, previous_links, next_links))
    return tuple(result)


def annotate_voice_leading(
    current: tuple[ResolverCandidate, ...],
    previous: tuple[ResolverCandidate, ...] = (),
    next_: tuple[ResolverCandidate, ...] = (),
) -> tuple[ResolverCandidate, ...]:
    """Add lowest-tier voice-leading support without changing candidate identities."""

    supported = {item.identity for item in observe_voice_leading(current, previous, next_)}
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
