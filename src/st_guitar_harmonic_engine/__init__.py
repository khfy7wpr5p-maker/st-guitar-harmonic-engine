"""ST Guitar Harmonic Engine deterministic core."""

from .analysis import (
    AnalysisStatus,
    CandidateAnalysis,
    FrameAnalysis,
    analyze_frame_exact,
    analyze_measure_exact,
)
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
from .frames import HarmonicFrame, build_harmonic_frames
from .inversion import BassAnalysis, Inversion, analyze_bass_and_inversion
from .models import Measure, NoteEvent, RationalBeat, TieState, TimeSignature
from .nct import NCTKind, NCTObservation, detect_stepwise_ncts
from .omissions import (
    IncompleteChordCandidate,
    OmissionKind,
    generate_fifth_omission_candidates,
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

__all__ = [
    "AnalysisStatus",
    "BassAnalysis",
    "BoundaryDisposition",
    "BoundaryReason",
    "CandidateAnalysis",
    "ChordCandidate",
    "ChordQuality",
    "ContextCandidate",
    "ContextResolution",
    "EXPLAINABILITY_SCHEMA_NAME",
    "EXPLAINABILITY_SCHEMA_V1",
    "EXPLAINABILITY_SCHEMA_VERSION",
    "FrameAnalysis",
    "FrameExplainability",
    "HarmonicFrame",
    "HarmonicRole",
    "IncompleteChordCandidate",
    "Inversion",
    "Measure",
    "MeasureExplainability",
    "NCTKind",
    "NCTObservation",
    "NoteEvent",
    "OmissionKind",
    "PitchStep",
    "RationalBeat",
    "ResolutionStatus",
    "STRUCTURAL_EXPLAINABILITY_SCHEMA_VERSION",
    "StructuralSegment",
    "StructuralSegmentation",
    "StructuralTransition",
    "SuspensionObservation",
    "TieState",
    "TimeSignature",
    "TonalContext",
    "TonalMode",
    "WrittenPitch",
    "analyze_bass_and_inversion",
    "analyze_frame_exact",
    "analyze_measure_exact",
    "analyze_measure_in_context",
    "build_harmonic_frames",
    "build_measure_explainability",
    "detect_stepwise_ncts",
    "detect_suspensions",
    "generate_exact_chord_candidates",
    "generate_fifth_omission_candidates",
    "is_explainability_payload_compatible",
    "is_structural_explainability_payload_compatible",
    "resolve_frame_in_context",
    "segment_measure_structurally",
    "serialize_measure_explainability",
    "serialize_structural_explainability",
    "validate_explainability_payload",
    "validate_structural_explainability_payload",
]
