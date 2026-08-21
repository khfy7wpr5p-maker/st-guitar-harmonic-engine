"""ST Guitar Harmonic Engine deterministic core."""

from .adjacency import AdjacentContextObservation, annotate_adjacent_context, observe_adjacent_context
from .aggregator import aggregate_frame_evidence
from .alterations import (
    AlterationKind,
    AlteredTensionCandidate,
    SuspendedChordCandidate,
    SuspendedChordKind,
    generate_altered_tension_candidates,
    generate_suspended_chord_candidates,
)
from .analysis import (
    AnalysisStatus,
    CandidateAnalysis,
    FrameAnalysis,
    analyze_frame_exact,
    analyze_measure_exact,
)
from .anticipation import AnticipationObservation, detect_anticipations
from .chords import ChordCandidate, ChordQuality, generate_exact_chord_candidates
from .context import (
    ContextCandidate,
    ContextResolution,
    HarmonicRole,
    ResolutionStatus,
    TonalContext,
    TonalMode,
    analyze_measure_in_context,
    resolve_frame_in_context,
)
from .explainability import (
    FrameExplainability,
    MeasureExplainability,
    build_measure_explainability,
)
from .explainability_schema import (
    EXPLAINABILITY_SCHEMA_NAME,
    EXPLAINABILITY_SCHEMA_V1,
    EXPLAINABILITY_SCHEMA_VERSION,
    is_explainability_payload_compatible,
    serialize_measure_explainability,
    validate_explainability_payload,
)
from .extensions import ExtensionCandidate, ExtensionKind, generate_extension_candidates
from .frames import HarmonicFrame, build_harmonic_frames
from .functional import (
    FunctionalObservation,
    FunctionalRelation,
    annotate_functional_relations,
    observe_functional_relations,
)
from .inversion import BassAnalysis, Inversion, analyze_bass_and_inversion
from .local_context import LocalTonalContextPlan, LocalTonalContextSpan
from .models import Measure, NoteEvent, RationalBeat, TieState, TimeSignature
from .nct import NCTKind, NCTObservation, detect_stepwise_ncts
from .omissions import (
    IncompleteChordCandidate,
    OmissionKind,
    generate_fifth_omission_candidates,
    generate_incomplete_chord_candidates,
)
from .ornamental_nct import (
    OrnamentalNCTKind,
    OrnamentalNCTObservation,
    detect_ornamental_ncts,
)
from .pedal import PedalFrameEvidence, PedalObservation, detect_pedals
from .phrase import PhrasePlan, PhraseSpan, phrase_bounded_neighbors
from .resolver import (
    EVIDENCE_PRECEDENCE,
    CandidateFamily,
    EvidenceSource,
    HarmonicIdentity,
    ResolverCandidate,
    ResolverDecision,
    ResolverStatus,
    evidence_precedence_index,
    stronger_evidence,
)
from .spelling import PitchStep, WrittenPitch
from .structural import (
    BoundaryDisposition,
    BoundaryReason,
    StructuralSegment,
    StructuralSegmentation,
    StructuralTransition,
    segment_measure_structurally,
)
from .structural_explainability import (
    STRUCTURAL_EXPLAINABILITY_SCHEMA_VERSION,
    is_structural_explainability_payload_compatible,
    serialize_structural_explainability,
    validate_structural_explainability_payload,
)
from .suspension import SuspensionObservation, detect_suspensions
from .voice_leading import VoiceLeadingObservation, annotate_voice_leading, observe_voice_leading

__all__ = [
    "AdjacentContextObservation",
    "AlterationKind",
    "AlteredTensionCandidate",
    "AnalysisStatus",
    "AnticipationObservation",
    "BassAnalysis",
    "BoundaryDisposition",
    "BoundaryReason",
    "CandidateAnalysis",
    "CandidateFamily",
    "ChordCandidate",
    "ChordQuality",
    "ContextCandidate",
    "ContextResolution",
    "EVIDENCE_PRECEDENCE",
    "EXPLAINABILITY_SCHEMA_NAME",
    "EXPLAINABILITY_SCHEMA_V1",
    "EXPLAINABILITY_SCHEMA_VERSION",
    "EvidenceSource",
    "ExtensionCandidate",
    "ExtensionKind",
    "FrameAnalysis",
    "FrameExplainability",
    "FunctionalObservation",
    "FunctionalRelation",
    "HarmonicFrame",
    "HarmonicIdentity",
    "HarmonicRole",
    "IncompleteChordCandidate",
    "Inversion",
    "LocalTonalContextPlan",
    "LocalTonalContextSpan",
    "Measure",
    "MeasureExplainability",
    "NCTKind",
    "NCTObservation",
    "NoteEvent",
    "OmissionKind",
    "OrnamentalNCTKind",
    "OrnamentalNCTObservation",
    "PedalFrameEvidence",
    "PedalObservation",
    "PhrasePlan",
    "PhraseSpan",
    "PitchStep",
    "RationalBeat",
    "ResolutionStatus",
    "ResolverCandidate",
    "ResolverDecision",
    "ResolverStatus",
    "STRUCTURAL_EXPLAINABILITY_SCHEMA_VERSION",
    "StructuralSegment",
    "StructuralSegmentation",
    "StructuralTransition",
    "SuspendedChordCandidate",
    "SuspendedChordKind",
    "SuspensionObservation",
    "TieState",
    "TimeSignature",
    "TonalContext",
    "TonalMode",
    "VoiceLeadingObservation",
    "WrittenPitch",
    "aggregate_frame_evidence",
    "analyze_bass_and_inversion",
    "analyze_frame_exact",
    "analyze_measure_exact",
    "analyze_measure_in_context",
    "annotate_adjacent_context",
    "annotate_functional_relations",
    "annotate_voice_leading",
    "build_harmonic_frames",
    "build_measure_explainability",
    "detect_anticipations",
    "detect_ornamental_ncts",
    "detect_pedals",
    "detect_stepwise_ncts",
    "detect_suspensions",
    "evidence_precedence_index",
    "generate_altered_tension_candidates",
    "generate_exact_chord_candidates",
    "generate_extension_candidates",
    "generate_fifth_omission_candidates",
    "generate_incomplete_chord_candidates",
    "generate_suspended_chord_candidates",
    "is_explainability_payload_compatible",
    "is_structural_explainability_payload_compatible",
    "observe_adjacent_context",
    "observe_functional_relations",
    "observe_voice_leading",
    "phrase_bounded_neighbors",
    "resolve_frame_in_context",
    "segment_measure_structurally",
    "serialize_measure_explainability",
    "serialize_structural_explainability",
    "stronger_evidence",
    "validate_explainability_payload",
    "validate_structural_explainability_payload",
]
