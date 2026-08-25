"""Fail-closed MusicXML intake for converted OpenScore Stage 8 sources.

This module converts one integrity-bound MXL artifact into the engine's existing
``Measure``/``NoteEvent``/``WrittenPitch`` contracts. It performs no harmonic
inference, ambiguity selection, human annotation, feature extraction, or model
training.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import hashlib
from pathlib import Path, PurePosixPath
import re
import xml.etree.ElementTree as ET
import zipfile

from .models import Measure, NoteEvent, RationalBeat, TieState, TimeSignature
from .spelling import PitchStep, WrittenPitch
from .stage8_openscore_conversion import OpenScoreConversionReceipt


STAGE8_OPENSCORE_MUSICXML_VERSION = "0.1"
_MAX_MXL_BYTES = 128 * 1024 * 1024
_MAX_ROOTFILE_BYTES = 64 * 1024 * 1024
_MAX_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
_MAX_ZIP_ENTRIES = 256
_MAX_PARTS = 32
_MAX_MEASURES_PER_PART = 5000
_MAX_EVENTS = 2_000_000
_MAX_STAVES_PER_PART = 16
_MAX_VOICE = 64
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_NATURAL_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


class OpenScoreMusicXMLError(RuntimeError):
    """Raised when the symbolic intake cannot prove a safe deterministic parse."""


@dataclass(frozen=True, slots=True)
class ParsedOpenScoreScore:
    source_id: str
    snapshot_commit_sha: str
    score_relative_path: str
    source_sha256: str
    mxl_sha256: str
    source_measure_labels: tuple[str, ...]
    measures: tuple[Measure, ...]
    part_count: int
    model_training_authorized: bool = False
    production_authority_granted: bool = False

    def __post_init__(self) -> None:
        for name in ("source_sha256", "mxl_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
                raise ValueError(f"{name} must be lowercase SHA-256")
        if not isinstance(self.source_measure_labels, tuple) or any(
            not isinstance(item, str) or not item for item in self.source_measure_labels
        ):
            raise TypeError("source_measure_labels must contain non-empty strings")
        if not isinstance(self.measures, tuple) or any(not isinstance(item, Measure) for item in self.measures):
            raise TypeError("measures must contain Measure values")
        if len(self.source_measure_labels) != len(self.measures):
            raise ValueError("measure labels and measures must have equal length")
        if isinstance(self.part_count, bool) or not isinstance(self.part_count, int) or self.part_count <= 0:
            raise ValueError("part_count must be a positive int")
        if self.model_training_authorized or self.production_authority_granted:
            raise ValueError("MusicXML intake cannot authorize training or production")


@dataclass(frozen=True, slots=True)
class _PartMeasure:
    label: str
    time_signature: TimeSignature
    actual_duration: RationalBeat
    events: tuple[NoteEvent, ...]


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in element if _local(child.tag) == name]


def _child(element: ET.Element, name: str) -> ET.Element | None:
    matches = _children(element, name)
    if len(matches) > 1:
        raise OpenScoreMusicXMLError(f"duplicate {name} element")
    return matches[0] if matches else None


def _required_child(element: ET.Element, name: str) -> ET.Element:
    value = _child(element, name)
    if value is None:
        raise OpenScoreMusicXMLError(f"missing required {name} element")
    return value


def _text(element: ET.Element, *, name: str) -> str:
    value = (element.text or "").strip()
    if not value:
        raise OpenScoreMusicXMLError(f"{name} text is empty")
    return value


def _positive_int_text(element: ET.Element, *, name: str, maximum: int | None = None) -> int:
    raw = _text(element, name=name)
    try:
        value = int(raw)
    except ValueError as exc:
        raise OpenScoreMusicXMLError(f"{name} must be an integer") from exc
    if value <= 0 or (maximum is not None and value > maximum):
        raise OpenScoreMusicXMLError(f"{name} is outside approved bounds")
    return value


def _signed_int_text(element: ET.Element, *, name: str, minimum: int, maximum: int) -> int:
    raw = _text(element, name=name)
    try:
        value = int(raw)
    except ValueError as exc:
        raise OpenScoreMusicXMLError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise OpenScoreMusicXMLError(f"{name} is outside approved bounds")
    return value


def _duration_fraction(element: ET.Element, divisions: int) -> Fraction:
    duration_element = _required_child(element, "duration")
    units = _positive_int_text(duration_element, name="duration", maximum=10_000_000)
    return Fraction(units, divisions)


def _measure_label(element: ET.Element, ordinal: int) -> str:
    raw = element.attrib.get("number")
    value = raw.strip() if isinstance(raw, str) and raw.strip() else str(ordinal)
    if len(value) > 128 or any(ord(char) < 32 for char in value):
        raise OpenScoreMusicXMLError("measure number label is unsafe")
    return value


def _parse_time(attributes: ET.Element, inherited: TimeSignature | None) -> TimeSignature | None:
    time = _child(attributes, "time")
    if time is None:
        return inherited
    if _child(time, "senza-misura") is not None:
        raise OpenScoreMusicXMLError("senza-misura is unsupported in v0.1")
    beats = _positive_int_text(_required_child(time, "beats"), name="beats", maximum=64)
    beat_type = _positive_int_text(_required_child(time, "beat-type"), name="beat-type", maximum=64)
    return TimeSignature(beats, beat_type)


def _parse_transpose(attributes: ET.Element, inherited: int) -> int:
    transpose = _child(attributes, "transpose")
    if transpose is None:
        return inherited
    chromatic = _signed_int_text(
        _required_child(transpose, "chromatic"),
        name="transpose chromatic",
        minimum=-24,
        maximum=24,
    )
    octave_element = _child(transpose, "octave-change")
    octave_change = (
        _signed_int_text(octave_element, name="transpose octave-change", minimum=-4, maximum=4)
        if octave_element is not None
        else 0
    )
    semitones = chromatic + 12 * octave_change
    if not -60 <= semitones <= 60:
        raise OpenScoreMusicXMLError("combined transposition is outside approved bounds")
    return semitones


def _parse_written_pitch(note: ET.Element) -> tuple[WrittenPitch, int]:
    pitch = _required_child(note, "pitch")
    step_text = _text(_required_child(pitch, "step"), name="pitch step")
    try:
        step = PitchStep(step_text)
    except ValueError as exc:
        raise OpenScoreMusicXMLError("pitch step must be A..G") from exc

    alter_element = _child(pitch, "alter")
    alter = 0
    if alter_element is not None:
        raw = _text(alter_element, name="pitch alter")
        try:
            decimal = Decimal(raw)
        except InvalidOperation as exc:
            raise OpenScoreMusicXMLError("pitch alter is invalid") from exc
        if decimal != decimal.to_integral_value():
            raise OpenScoreMusicXMLError("microtonal/non-integral pitch alter is unsupported")
        alter = int(decimal)
        if not -2 <= alter <= 2:
            raise OpenScoreMusicXMLError("pitch alter is outside WrittenPitch bounds")

    octave = _signed_int_text(
        _required_child(pitch, "octave"),
        name="pitch octave",
        minimum=-1,
        maximum=9,
    )
    written = WrittenPitch(step=step, alter=alter, octave=octave)
    written_midi = 12 * (octave + 1) + _NATURAL_PC[step.value] + alter
    return written, written_midi


def _tie_state(note: ET.Element) -> TieState:
    types = {
        item.attrib.get("type", "").strip()
        for item in _children(note, "tie")
        if item.attrib.get("type", "").strip()
    }
    if not types:
        return TieState.NONE
    if not types <= {"start", "stop"}:
        raise OpenScoreMusicXMLError("unsupported MusicXML tie type")
    if types == {"start", "stop"}:
        return TieState.CONTINUE
    return TieState.START if "start" in types else TieState.STOP


def _global_staff(part_index: int, local_staff: int) -> int:
    if not 1 <= local_staff <= _MAX_STAVES_PER_PART:
        raise OpenScoreMusicXMLError("staff number is outside approved per-part bounds")
    return (part_index - 1) * _MAX_STAVES_PER_PART + local_staff


def _parse_part(
    part: ET.Element,
    *,
    part_index: int,
    event_budget: list[int],
) -> tuple[_PartMeasure, ...]:
    measures = _children(part, "measure")
    if not measures or len(measures) > _MAX_MEASURES_PER_PART:
        raise OpenScoreMusicXMLError("part measure count is outside approved bounds")

    divisions: int | None = None
    time_signature: TimeSignature | None = None
    transpose_semitones = 0
    result: list[_PartMeasure] = []

    for ordinal, measure_element in enumerate(measures, start=1):
        label = _measure_label(measure_element, ordinal)
        cursor = Fraction(0)
        max_extent = Fraction(0)
        last_note_onset: Fraction | None = None
        events: list[NoteEvent] = []

        for item in measure_element:
            tag = _local(item.tag)
            if tag == "attributes":
                divisions_element = _child(item, "divisions")
                if divisions_element is not None:
                    divisions = _positive_int_text(divisions_element, name="divisions", maximum=1_000_000)
                time_signature = _parse_time(item, time_signature)
                transpose_semitones = _parse_transpose(item, transpose_semitones)
                continue

            if tag in {"backup", "forward"}:
                if divisions is None:
                    raise OpenScoreMusicXMLError("timing operation appears before divisions")
                delta = _duration_fraction(item, divisions)
                cursor = cursor - delta if tag == "backup" else cursor + delta
                if cursor < 0:
                    raise OpenScoreMusicXMLError("MusicXML backup moved cursor before measure start")
                max_extent = max(max_extent, cursor)
                last_note_onset = None
                continue

            if tag != "note":
                continue

            if _child(item, "grace") is not None:
                last_note_onset = None
                continue
            if divisions is None:
                raise OpenScoreMusicXMLError("note appears before divisions")
            if time_signature is None:
                raise OpenScoreMusicXMLError("note appears before a defined time signature")

            duration = _duration_fraction(item, divisions)
            is_chord = _child(item, "chord") is not None
            if is_chord:
                if last_note_onset is None:
                    raise OpenScoreMusicXMLError("chord note has no preceding onset")
                onset = last_note_onset
            else:
                onset = cursor
                last_note_onset = onset
                cursor += duration
            max_extent = max(max_extent, onset + duration, cursor)

            is_rest = _child(item, "rest") is not None
            is_unpitched = _child(item, "unpitched") is not None
            is_cue = _child(item, "cue") is not None
            if is_rest or is_unpitched or is_cue:
                if not is_chord:
                    last_note_onset = None
                continue

            written, written_midi = _parse_written_pitch(item)
            sounding_midi = written_midi + transpose_semitones
            if not 0 <= sounding_midi <= 127:
                raise OpenScoreMusicXMLError("sounding MIDI pitch is outside 0..127")

            voice_element = _child(item, "voice")
            voice = (
                _positive_int_text(voice_element, name="voice", maximum=_MAX_VOICE)
                if voice_element is not None
                else 1
            )
            staff_element = _child(item, "staff")
            local_staff = (
                _positive_int_text(staff_element, name="staff", maximum=_MAX_STAVES_PER_PART)
                if staff_element is not None
                else 1
            )
            event_budget[0] += 1
            if event_budget[0] > _MAX_EVENTS:
                raise OpenScoreMusicXMLError("score event count exceeds approved bound")
            events.append(
                NoteEvent(
                    measure_number=ordinal,
                    staff=_global_staff(part_index, local_staff),
                    voice=voice,
                    midi_pitch=sounding_midi,
                    onset=RationalBeat(onset.numerator, onset.denominator),
                    duration=RationalBeat(duration.numerator, duration.denominator),
                    tie=_tie_state(item),
                    written_pitch=written,
                )
            )

        if time_signature is None:
            raise OpenScoreMusicXMLError("measure has no inherited or explicit time signature")
        actual = max_extent if max_extent > 0 else time_signature.quarter_length.fraction
        result.append(
            _PartMeasure(
                label=label,
                time_signature=time_signature,
                actual_duration=RationalBeat(actual.numerator, actual.denominator),
                events=tuple(events),
            )
        )

    return tuple(result)


def _merge_parts(parts: tuple[tuple[_PartMeasure, ...], ...]) -> tuple[tuple[str, ...], tuple[Measure, ...]]:
    counts = {len(part) for part in parts}
    if len(counts) != 1:
        raise OpenScoreMusicXMLError("MusicXML parts have different measure counts")
    measure_count = next(iter(counts))
    labels: list[str] = []
    merged: list[Measure] = []

    for index in range(measure_count):
        current = tuple(part[index] for part in parts)
        label_set = {item.label for item in current}
        if len(label_set) != 1:
            raise OpenScoreMusicXMLError("MusicXML part measure labels are misaligned")
        time_set = {(item.time_signature.numerator, item.time_signature.denominator) for item in current}
        if len(time_set) != 1:
            raise OpenScoreMusicXMLError("MusicXML parts disagree on time signature")
        duration = max(item.actual_duration.fraction for item in current)
        events = tuple(event for item in current for event in item.events)
        labels.append(current[0].label)
        merged.append(
            Measure(
                number=index + 1,
                time_signature=current[0].time_signature,
                events=events,
                actual_duration=RationalBeat(duration.numerator, duration.denominator),
            )
        )
    return tuple(labels), tuple(merged)


def _validated_archive_member(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise OpenScoreMusicXMLError("unsafe MXL archive member")
    return path


def _read_rootfile(path: Path, receipt: OpenScoreConversionReceipt) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise OpenScoreMusicXMLError("MXL path must be a regular file")
    size = path.stat().st_size
    if size <= 0 or size > _MAX_MXL_BYTES or size != receipt.output_bytes:
        raise OpenScoreMusicXMLError("MXL byte size does not match conversion receipt")

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != receipt.output_sha256:
        raise OpenScoreMusicXMLError("MXL SHA-256 does not match conversion receipt")
    if not zipfile.is_zipfile(path):
        raise OpenScoreMusicXMLError("MXL is not a ZIP archive")

    try:
        with zipfile.ZipFile(path, "r") as archive:
            infos = archive.infolist()
            if not infos or len(infos) > _MAX_ZIP_ENTRIES:
                raise OpenScoreMusicXMLError("MXL entry count is outside approved bounds")
            total = 0
            names: set[str] = set()
            for info in infos:
                name = _validated_archive_member(info.filename).as_posix()
                if name in names:
                    raise OpenScoreMusicXMLError("MXL contains duplicate archive members")
                names.add(name)
                if info.flag_bits & 0x1:
                    raise OpenScoreMusicXMLError("encrypted MXL members are forbidden")
                total += info.file_size
                if total > _MAX_UNCOMPRESSED_BYTES:
                    raise OpenScoreMusicXMLError("MXL uncompressed size exceeds approved bound")
            rootfile = _validated_archive_member(receipt.rootfile_path).as_posix()
            if rootfile not in names:
                raise OpenScoreMusicXMLError("receipt rootfile is missing from MXL")
            info = archive.getinfo(rootfile)
            if info.file_size <= 0 or info.file_size > _MAX_ROOTFILE_BYTES:
                raise OpenScoreMusicXMLError("MusicXML rootfile size is outside approved bounds")
            payload = archive.read(info)
    except zipfile.BadZipFile as exc:
        raise OpenScoreMusicXMLError("MXL ZIP structure is malformed") from exc

    upper = payload.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise OpenScoreMusicXMLError("DTD/entity declarations are forbidden")
    return payload


def parse_openscore_mxl(
    mxl_path: str,
    receipt: OpenScoreConversionReceipt,
) -> ParsedOpenScoreScore:
    """Parse one integrity-bound MXL into existing symbolic engine contracts."""

    if not isinstance(mxl_path, str) or not mxl_path or not Path(mxl_path).is_absolute():
        raise ValueError("mxl_path must be a non-empty absolute path")
    if not isinstance(receipt, OpenScoreConversionReceipt):
        raise TypeError("receipt must be OpenScoreConversionReceipt")

    payload = _read_rootfile(Path(mxl_path), receipt)
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise OpenScoreMusicXMLError("MusicXML rootfile is malformed") from exc
    if _local(root.tag) != "score-partwise":
        raise OpenScoreMusicXMLError("only score-partwise MusicXML is supported in v0.1")

    parts = _children(root, "part")
    if not parts or len(parts) > _MAX_PARTS:
        raise OpenScoreMusicXMLError("MusicXML part count is outside approved bounds")
    part_ids = [part.attrib.get("id", "").strip() for part in parts]
    if any(not item for item in part_ids) or len(set(part_ids)) != len(part_ids):
        raise OpenScoreMusicXMLError("MusicXML part IDs must be non-empty and unique")

    event_budget = [0]
    parsed_parts = tuple(
        _parse_part(part, part_index=index, event_budget=event_budget)
        for index, part in enumerate(parts, start=1)
    )
    labels, measures = _merge_parts(parsed_parts)
    return ParsedOpenScoreScore(
        source_id=receipt.source_id,
        snapshot_commit_sha=receipt.snapshot_commit_sha,
        score_relative_path=receipt.score_relative_path,
        source_sha256=receipt.source_sha256,
        mxl_sha256=receipt.output_sha256,
        source_measure_labels=labels,
        measures=measures,
        part_count=len(parts),
    )
