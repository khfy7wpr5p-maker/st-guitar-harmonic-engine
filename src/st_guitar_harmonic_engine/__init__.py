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

__all__ = [
    "AnalysisStatus",
    "BassAnalysis",
    "CandidateAnalysis",
    "ChordCandidate",
    "ChordQuality",
    "ContextCandidate",
    "ContextResolution",
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
    "generate_exact_chord_candidates",
    "generate_fifth_omission_candidates",
    "resolve_frame_in_context",
]
