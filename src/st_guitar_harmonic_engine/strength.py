"""Deterministic evidence-strength classification for Stage 4-B.

The classification is categorical and rule-based. It deliberately contains no
numeric score, learned weight, or probability.
"""

from __future__ import annotations

from .confidence import ConfidenceAssessment, ConfidenceState
from .resolver import EvidenceSource, ResolverCandidate


_DIRECT_BOUNDED = frozenset(
    {
        EvidenceSource.TONAL_CONTEXT,
        EvidenceSource.STRUCTURAL,
        EvidenceSource.BASS_INVERSION,
        EvidenceSource.VERIFIED_NCT,
    }
)
_PRIMARY_WEAK = frozenset(
    {
        EvidenceSource.INCOMPLETE_CHORD,
        EvidenceSource.COLOR_TONE,
    }
)
_CORROBORATING = frozenset(
    {
        EvidenceSource.ADJACENT_CONTEXT,
        EvidenceSource.VOICE_FUNCTION,
    }
)


def assess_candidate_strength(candidate: ResolverCandidate) -> ConfidenceAssessment:
    """Classify one validated candidate using only its declared evidence."""

    if not isinstance(candidate, ResolverCandidate):
        raise TypeError("candidate must be a ResolverCandidate")

    evidence = candidate.evidence
    evidence_set = set(evidence)
    if EvidenceSource.EXACT in evidence_set:
        state = ConfidenceState.STRONG
    elif evidence_set & _DIRECT_BOUNDED:
        state = ConfidenceState.BOUNDED
    elif evidence_set & _PRIMARY_WEAK and evidence_set & _CORROBORATING:
        state = ConfidenceState.BOUNDED
    elif evidence:
        state = ConfidenceState.WEAK
    else:
        state = ConfidenceState.INSUFFICIENT

    return ConfidenceAssessment(state, evidence if evidence else ())
