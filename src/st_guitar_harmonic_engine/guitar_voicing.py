"""Stage 6 guitar-specific voicing evidence with no harmonic authority.

String/fret/TAB information is normalized here into descriptive evidence only.
This module does not import the resolver, create harmonic candidates, alter
confidence, or infer a final chord.  Pitch-class identity and occurrence count
are kept separate so octave/string doubling cannot amplify harmonic evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


GUITAR_VOICING_SCHEMA_NAME = "st_guitar_harmonic_engine.guitar_voicing"
GUITAR_VOICING_SCHEMA_VERSION = "1.0"
GUITAR_VOICING_AUTHORITY = "descriptive_bounded_evidence_not_harmonic_authority"
MAX_GUITAR_STRINGS = 12
MAX_GUITAR_FRET = 36


class GuitarStringState(str, Enum):
    SOUNDING = "sounding"
    MUTED = "muted"
    MISSING = "missing"


class CandidateBassRelation(str, Enum):
    ROOT = "root"
    CHORD_TONE_NON_ROOT = "chord_tone_non_root"
    OUTSIDE_CANDIDATE = "outside_candidate"
    SILENT = "silent"


class ContextualBassState(str, Enum):
    UNKNOWN = "unknown"
    POSSIBLE = "possible"
    VERIFIED = "verified"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True, order=True)
class GuitarStringObservation:
    """One normalized guitar-string observation.

    No standard tuning is assumed.  Sounding pitch is supplied by the caller so
    alternate tunings, capos, and extended-range guitars remain representable.
    """

    string_number: int
    state: GuitarStringState
    fret: int | None = None
    midi_pitch: int | None = None

    def __post_init__(self) -> None:
        if isinstance(self.string_number, bool) or not isinstance(self.string_number, int):
            raise TypeError("string_number must be an int")
        if not 1 <= self.string_number <= MAX_GUITAR_STRINGS:
            raise ValueError("string_number is outside the bounded guitar domain")
        if not isinstance(self.state, GuitarStringState):
            raise TypeError("state must be a GuitarStringState")

        if self.state is GuitarStringState.SOUNDING:
            if isinstance(self.fret, bool) or not isinstance(self.fret, int):
                raise TypeError("sounding string fret must be an int")
            if not 0 <= self.fret <= MAX_GUITAR_FRET:
                raise ValueError("fret is outside the bounded guitar domain")
            if isinstance(self.midi_pitch, bool) or not isinstance(self.midi_pitch, int):
                raise TypeError("sounding string midi_pitch must be an int")
            if not 0 <= self.midi_pitch <= 127:
                raise ValueError("midi_pitch must be between 0 and 127")
        elif self.fret is not None or self.midi_pitch is not None:
            raise ValueError("muted/missing strings cannot carry fret or pitch")

    @property
    def is_open(self) -> bool:
        return self.state is GuitarStringState.SOUNDING and self.fret == 0


@dataclass(frozen=True, slots=True, order=True)
class PitchClassMultiplicity:
    pitch_class: int
    occurrence_count: int

    def __post_init__(self) -> None:
        if isinstance(self.pitch_class, bool) or not isinstance(self.pitch_class, int):
            raise TypeError("pitch_class must be an int")
        if not 0 <= self.pitch_class <= 11:
            raise ValueError("pitch_class must be between 0 and 11")
        if isinstance(self.occurrence_count, bool) or not isinstance(self.occurrence_count, int):
            raise TypeError("occurrence_count must be an int")
        if self.occurrence_count < 1:
            raise ValueError("occurrence_count must be at least 1")


@dataclass(frozen=True, slots=True)
class GuitarVoicingEvidence:
    """Canonical descriptive evidence derived from guitar-string observations."""

    strings: tuple[GuitarStringObservation, ...]
    pitch_classes: tuple[int, ...]
    multiplicities: tuple[PitchClassMultiplicity, ...]
    repeated_pitch_classes: tuple[int, ...]
    sounding_bass_pitch: int | None
    sounding_bass_pitch_class: int | None
    open_string_numbers: tuple[int, ...]
    muted_string_numbers: tuple[int, ...]
    missing_string_numbers: tuple[int, ...]
    voicing_span_semitones: int | None

    def __post_init__(self) -> None:
        if not isinstance(self.strings, tuple) or any(
            not isinstance(item, GuitarStringObservation) for item in self.strings
        ):
            raise TypeError("strings must contain GuitarStringObservation values")
        if tuple(sorted(self.strings, key=lambda item: item.string_number)) != self.strings:
            raise ValueError("strings must use canonical string-number ordering")
        if len({item.string_number for item in self.strings}) != len(self.strings):
            raise ValueError("string numbers must be unique")

        expected = _derive_fields(self.strings)
        actual = (
            self.pitch_classes,
            self.multiplicities,
            self.repeated_pitch_classes,
            self.sounding_bass_pitch,
            self.sounding_bass_pitch_class,
            self.open_string_numbers,
            self.muted_string_numbers,
            self.missing_string_numbers,
            self.voicing_span_semitones,
        )
        if actual != expected:
            raise ValueError("voicing evidence fields must match canonical string observations")

    @property
    def sounding_occurrence_count(self) -> int:
        return sum(item.occurrence_count for item in self.multiplicities)


@dataclass(frozen=True, slots=True)
class GuitarBassEvidence:
    """Candidate-relative bass description, still non-authoritative.

    A non-root bass can indicate an inversion or slash-chord representation, but
    the same pitch may instead be contextual/pedal material.  Pedal status is
    therefore unknown unless an independent contextual detector supplies it.
    """

    sounding_bass_pitch: int | None
    sounding_bass_pitch_class: int | None
    candidate_relation: CandidateBassRelation
    inversion_possible: bool
    slash_chord_possible: bool
    pedal_bass_state: ContextualBassState = ContextualBassState.UNKNOWN

    def __post_init__(self) -> None:
        if self.sounding_bass_pitch is None:
            if self.sounding_bass_pitch_class is not None:
                raise ValueError("silent bass cannot carry a pitch class")
            if self.candidate_relation is not CandidateBassRelation.SILENT:
                raise ValueError("missing bass requires SILENT candidate relation")
            if self.inversion_possible or self.slash_chord_possible:
                raise ValueError("silent bass cannot imply inversion or slash chord")
        else:
            if isinstance(self.sounding_bass_pitch, bool) or not isinstance(
                self.sounding_bass_pitch, int
            ):
                raise TypeError("sounding_bass_pitch must be an int or None")
            if not 0 <= self.sounding_bass_pitch <= 127:
                raise ValueError("sounding_bass_pitch must be between 0 and 127")
            if self.sounding_bass_pitch_class != self.sounding_bass_pitch % 12:
                raise ValueError("bass pitch class must match sounding bass")
            if self.candidate_relation is CandidateBassRelation.SILENT:
                raise ValueError("sounding bass cannot have SILENT relation")
        if not isinstance(self.candidate_relation, CandidateBassRelation):
            raise TypeError("candidate_relation must be a CandidateBassRelation")
        if not isinstance(self.inversion_possible, bool) or not isinstance(
            self.slash_chord_possible, bool
        ):
            raise TypeError("possibility fields must be bool")
        if not isinstance(self.pedal_bass_state, ContextualBassState):
            raise TypeError("pedal_bass_state must be a ContextualBassState")
        if self.candidate_relation is CandidateBassRelation.ROOT and self.inversion_possible:
            raise ValueError("root bass cannot be marked as inversion")
        if self.candidate_relation is CandidateBassRelation.ROOT and self.slash_chord_possible:
            raise ValueError("root bass cannot require slash-chord representation")


def _derive_fields(
    strings: tuple[GuitarStringObservation, ...],
) -> tuple[
    tuple[int, ...],
    tuple[PitchClassMultiplicity, ...],
    tuple[int, ...],
    int | None,
    int | None,
    tuple[int, ...],
    tuple[int, ...],
    tuple[int, ...],
    int | None,
]:
    sounding = tuple(
        item for item in strings if item.state is GuitarStringState.SOUNDING
    )
    pitches = tuple(item.midi_pitch for item in sounding if item.midi_pitch is not None)
    counts: dict[int, int] = {}
    for pitch in pitches:
        pitch_class = pitch % 12
        counts[pitch_class] = counts.get(pitch_class, 0) + 1
    multiplicities = tuple(
        PitchClassMultiplicity(pitch_class, count)
        for pitch_class, count in sorted(counts.items())
    )
    pitch_classes = tuple(item.pitch_class for item in multiplicities)
    repeated = tuple(
        item.pitch_class for item in multiplicities if item.occurrence_count > 1
    )
    bass = min(pitches) if pitches else None
    span = max(pitches) - min(pitches) if pitches else None
    return (
        pitch_classes,
        multiplicities,
        repeated,
        bass,
        bass % 12 if bass is not None else None,
        tuple(item.string_number for item in sounding if item.is_open),
        tuple(item.string_number for item in strings if item.state is GuitarStringState.MUTED),
        tuple(item.string_number for item in strings if item.state is GuitarStringState.MISSING),
        span,
    )


def build_guitar_voicing_evidence(
    strings: tuple[GuitarStringObservation, ...],
) -> GuitarVoicingEvidence:
    """Normalize guitar observations into canonical non-authoritative evidence."""

    if not isinstance(strings, tuple) or any(
        not isinstance(item, GuitarStringObservation) for item in strings
    ):
        raise TypeError("strings must contain GuitarStringObservation values")
    canonical = tuple(sorted(strings, key=lambda item: item.string_number))
    if len({item.string_number for item in canonical}) != len(canonical):
        raise ValueError("string numbers must be unique")
    fields = _derive_fields(canonical)
    return GuitarVoicingEvidence(canonical, *fields)


def describe_candidate_tone_doubling(
    voicing: GuitarVoicingEvidence,
    candidate_pitch_classes: tuple[int, ...],
) -> tuple[PitchClassMultiplicity, ...]:
    """Report repeated candidate tones without increasing evidence strength.

    ``candidate_pitch_classes`` must already come from a validated candidate;
    this function does not infer one.
    """

    if not isinstance(voicing, GuitarVoicingEvidence):
        raise TypeError("voicing must be GuitarVoicingEvidence")
    if not isinstance(candidate_pitch_classes, tuple) or any(
        isinstance(item, bool) or not isinstance(item, int) for item in candidate_pitch_classes
    ):
        raise TypeError("candidate_pitch_classes must contain ints")
    if tuple(sorted(set(candidate_pitch_classes))) != candidate_pitch_classes:
        raise ValueError("candidate_pitch_classes must be unique and sorted")
    if any(not 0 <= item <= 11 for item in candidate_pitch_classes):
        raise ValueError("candidate pitch classes must be between 0 and 11")
    candidate_set = set(candidate_pitch_classes)
    return tuple(
        item
        for item in voicing.multiplicities
        if item.pitch_class in candidate_set and item.occurrence_count > 1
    )


def describe_bass_against_candidate(
    voicing: GuitarVoicingEvidence,
    *,
    root_pc: int,
    candidate_pitch_classes: tuple[int, ...],
    pedal_bass_state: ContextualBassState = ContextualBassState.UNKNOWN,
) -> GuitarBassEvidence:
    """Describe bass/root relation without deciding chord identity.

    Non-root chord tones are inversion/slash *possibilities*.  A bass outside the
    supplied candidate can be a slash/pedal/contextual tone, so it remains a
    possibility rather than causing candidate creation or rejection.
    """

    if not isinstance(voicing, GuitarVoicingEvidence):
        raise TypeError("voicing must be GuitarVoicingEvidence")
    if isinstance(root_pc, bool) or not isinstance(root_pc, int):
        raise TypeError("root_pc must be an int")
    if not 0 <= root_pc <= 11:
        raise ValueError("root_pc must be between 0 and 11")
    if not isinstance(candidate_pitch_classes, tuple) or any(
        isinstance(item, bool) or not isinstance(item, int) for item in candidate_pitch_classes
    ):
        raise TypeError("candidate_pitch_classes must contain ints")
    if tuple(sorted(set(candidate_pitch_classes))) != candidate_pitch_classes:
        raise ValueError("candidate_pitch_classes must be unique and sorted")
    if any(not 0 <= item <= 11 for item in candidate_pitch_classes):
        raise ValueError("candidate pitch classes must be between 0 and 11")
    if root_pc not in candidate_pitch_classes:
        raise ValueError("root_pc must belong to the validated candidate pitch classes")
    if not isinstance(pedal_bass_state, ContextualBassState):
        raise TypeError("pedal_bass_state must be a ContextualBassState")

    bass_pitch = voicing.sounding_bass_pitch
    bass_pc = voicing.sounding_bass_pitch_class
    if bass_pitch is None or bass_pc is None:
        return GuitarBassEvidence(
            None,
            None,
            CandidateBassRelation.SILENT,
            False,
            False,
            pedal_bass_state,
        )
    if bass_pc == root_pc:
        relation = CandidateBassRelation.ROOT
        inversion_possible = False
        slash_possible = False
    elif bass_pc in candidate_pitch_classes:
        relation = CandidateBassRelation.CHORD_TONE_NON_ROOT
        inversion_possible = True
        slash_possible = True
    else:
        relation = CandidateBassRelation.OUTSIDE_CANDIDATE
        inversion_possible = False
        slash_possible = True
    return GuitarBassEvidence(
        bass_pitch,
        bass_pc,
        relation,
        inversion_possible,
        slash_possible,
        pedal_bass_state,
    )


def serialize_guitar_voicing(evidence: GuitarVoicingEvidence) -> dict[str, Any]:
    """Return stable JSON-compatible Stage 6 guitar evidence."""

    if not isinstance(evidence, GuitarVoicingEvidence):
        raise TypeError("evidence must be GuitarVoicingEvidence")
    return {
        "schema_name": GUITAR_VOICING_SCHEMA_NAME,
        "schema_version": GUITAR_VOICING_SCHEMA_VERSION,
        "authority": GUITAR_VOICING_AUTHORITY,
        "strings": [
            {
                "string_number": item.string_number,
                "state": item.state.value,
                "fret": item.fret,
                "midi_pitch": item.midi_pitch,
            }
            for item in evidence.strings
        ],
        "pitch_classes": list(evidence.pitch_classes),
        "multiplicities": [
            {
                "pitch_class": item.pitch_class,
                "occurrence_count": item.occurrence_count,
            }
            for item in evidence.multiplicities
        ],
        "repeated_pitch_classes": list(evidence.repeated_pitch_classes),
        "sounding_bass_pitch": evidence.sounding_bass_pitch,
        "sounding_bass_pitch_class": evidence.sounding_bass_pitch_class,
        "open_string_numbers": list(evidence.open_string_numbers),
        "muted_string_numbers": list(evidence.muted_string_numbers),
        "missing_string_numbers": list(evidence.missing_string_numbers),
        "voicing_span_semitones": evidence.voicing_span_semitones,
    }


def is_guitar_voicing_payload_compatible(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    return (
        set(payload)
        == {
            "schema_name",
            "schema_version",
            "authority",
            "strings",
            "pitch_classes",
            "multiplicities",
            "repeated_pitch_classes",
            "sounding_bass_pitch",
            "sounding_bass_pitch_class",
            "open_string_numbers",
            "muted_string_numbers",
            "missing_string_numbers",
            "voicing_span_semitones",
        }
        and payload.get("schema_name") == GUITAR_VOICING_SCHEMA_NAME
        and payload.get("schema_version") == GUITAR_VOICING_SCHEMA_VERSION
        and payload.get("authority") == GUITAR_VOICING_AUTHORITY
    )
