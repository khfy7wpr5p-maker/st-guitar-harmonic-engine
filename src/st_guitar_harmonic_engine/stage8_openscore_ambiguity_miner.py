"""Causal metadata-only ambiguity miner for Stage 8 OpenScore research.

The miner reuses the existing deterministic harmonic engine. It retains only
frames whose *final* abstention-gated state is AMBIGUOUS. It does not consume
OpenScore automatic analyses, lyrics, Teacher-Gold/HOLDOUT labels, future frames,
or any model output, and it never chooses a preferred candidate.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import PurePosixPath
import re

from .abstention import FinalDecisionState, apply_abstention_policy
from .aggregator import aggregate_frame_evidence
from .frames import HarmonicFrame, build_harmonic_frames
from .resolver import HarmonicIdentity
from .sequence import resolve_candidates_by_precedence
from .stage8_openscore_musicxml import ParsedOpenScoreScore


STAGE8_OPENSCORE_AMBIGUITY_MINER_VERSION = "0.1"
_MAX_PREVIOUS_FRAMES = 4
_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class OpenScoreAmbiguityCandidate:
    source_id: str
    snapshot_commit_sha: str
    score_relative_path: str
    source_group_id: str
    source_sha256: str
    mxl_sha256: str
    deterministic_engine_sha: str
    measure_ordinal: int
    source_measure_label: str
    frame_ordinal_in_measure: int
    frame_start_numerator: int
    frame_start_denominator: int
    frame_end_numerator: int
    frame_end_denominator: int
    current_frame_sha256: str
    candidate_ids: tuple[str, ...]
    candidate_set_sha256: str
    previous_frame_sha256: tuple[str, ...]
    preferred_candidate_id: None = None
    annotation_status: str = "draft"
    model_training_authorized: bool = False
    production_authority_granted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id:
            raise TypeError("source_id must be a non-empty string")
        if not isinstance(self.score_relative_path, str) or not self.score_relative_path:
            raise TypeError("score_relative_path must be a non-empty string")
        if not isinstance(self.source_group_id, str) or not self.source_group_id:
            raise TypeError("source_group_id must be a non-empty string")
        if not isinstance(self.snapshot_commit_sha, str) or _SHA40_RE.fullmatch(self.snapshot_commit_sha) is None:
            raise ValueError("snapshot_commit_sha must be lowercase 40-character SHA")
        if not isinstance(self.deterministic_engine_sha, str) or _SHA40_RE.fullmatch(self.deterministic_engine_sha) is None:
            raise ValueError("deterministic_engine_sha must be lowercase 40-character SHA")
        for name in ("source_sha256", "mxl_sha256", "current_frame_sha256", "candidate_set_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
                raise ValueError(f"{name} must be lowercase SHA-256")
        if isinstance(self.measure_ordinal, bool) or not isinstance(self.measure_ordinal, int) or self.measure_ordinal < 1:
            raise ValueError("measure_ordinal must be a positive int")
        if not isinstance(self.source_measure_label, str) or not self.source_measure_label:
            raise TypeError("source_measure_label must be a non-empty string")
        if isinstance(self.frame_ordinal_in_measure, bool) or not isinstance(self.frame_ordinal_in_measure, int) or self.frame_ordinal_in_measure < 1:
            raise ValueError("frame_ordinal_in_measure must be a positive int")
        for name in ("frame_start_numerator", "frame_end_numerator"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative int")
        for name in ("frame_start_denominator", "frame_end_denominator"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive int")
        if not isinstance(self.candidate_ids, tuple) or len(self.candidate_ids) < 2:
            raise ValueError("candidate_ids must contain at least two candidates")
        if tuple(sorted(set(self.candidate_ids))) != self.candidate_ids:
            raise ValueError("candidate_ids must be unique canonical order")
        if any(not isinstance(item, str) or not item for item in self.candidate_ids):
            raise TypeError("candidate_ids must contain non-empty strings")
        if not isinstance(self.previous_frame_sha256, tuple) or len(self.previous_frame_sha256) > _MAX_PREVIOUS_FRAMES:
            raise ValueError("previous_frame_sha256 must contain at most four fingerprints")
        if any(not isinstance(item, str) or _SHA256_RE.fullmatch(item) is None for item in self.previous_frame_sha256):
            raise ValueError("previous_frame_sha256 entries must be lowercase SHA-256")
        if self.preferred_candidate_id is not None:
            raise ValueError("mined candidates cannot contain a preferred candidate")
        if self.annotation_status != "draft":
            raise ValueError("mined candidates must enter human review as draft")
        if self.model_training_authorized or self.production_authority_granted:
            raise ValueError("ambiguity mining cannot authorize training or production")


@dataclass(frozen=True, slots=True)
class OpenScoreAmbiguityMiningResult:
    source_id: str
    score_relative_path: str
    deterministic_engine_sha: str
    harmonic_frame_count: int
    ambiguous_candidate_count: int
    candidates: tuple[OpenScoreAmbiguityCandidate, ...]
    model_training_authorized: bool = False
    production_authority_granted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.deterministic_engine_sha, str) or _SHA40_RE.fullmatch(self.deterministic_engine_sha) is None:
            raise ValueError("deterministic_engine_sha must be lowercase 40-character SHA")
        for name in ("harmonic_frame_count", "ambiguous_candidate_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative int")
        if not isinstance(self.candidates, tuple) or any(not isinstance(item, OpenScoreAmbiguityCandidate) for item in self.candidates):
            raise TypeError("candidates must contain OpenScoreAmbiguityCandidate values")
        if self.ambiguous_candidate_count != len(self.candidates):
            raise ValueError("ambiguous_candidate_count must equal candidates length")
        if self.ambiguous_candidate_count > self.harmonic_frame_count:
            raise ValueError("ambiguous candidates cannot exceed harmonic frames")
        if self.model_training_authorized or self.production_authority_granted:
            raise ValueError("mining result cannot authorize training or production")


def _identity_token(identity: HarmonicIdentity) -> str:
    return f"pc:{identity.root_pc}:{identity.family.value}:{identity.variant}"


def _candidate_set_hash(candidate_ids: tuple[str, ...]) -> str:
    payload = json.dumps(candidate_ids, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _fraction_pair(value) -> tuple[int, int]:
    fraction = value.fraction
    return fraction.numerator, fraction.denominator


def _frame_hash(frame: HarmonicFrame) -> str:
    events = []
    for event in frame.events:
        onset_n, onset_d = _fraction_pair(event.onset)
        duration_n, duration_d = _fraction_pair(event.duration)
        events.append(
            {
                "staff": event.staff,
                "voice": event.voice,
                "midi_pitch": event.midi_pitch,
                "written_pitch": event.written_pitch.name if event.written_pitch is not None else None,
                "onset": [onset_n, onset_d],
                "duration": [duration_n, duration_d],
                "tie": event.tie.value,
            }
        )
    start_n, start_d = _fraction_pair(frame.start)
    end_n, end_d = _fraction_pair(frame.end)
    payload = {
        "measure_ordinal": frame.measure_number,
        "start": [start_n, start_d],
        "end": [end_n, end_d],
        "events": events,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _source_group_id(score: ParsedOpenScoreScore) -> str:
    path = PurePosixPath(score.score_relative_path)
    if path.is_absolute() or ".." in path.parts or len(path.parts) < 3 or path.parts[0] != "scores":
        raise ValueError("score_relative_path cannot define a safe source group")

    if score.source_id == "openscore-string-quartets":
        # scores/<composer>/<set>/sq*.mscx -- group the full work/set directory.
        group_parts = path.parent.parts
    elif score.source_id == "openscore-lieder":
        # scores/<composer>/<set>/<song>/lc*.mscx -- group the enclosing set/cycle.
        # Standalone songs use '_' as the set, intentionally making this grouping conservative.
        if len(path.parts) < 5:
            raise ValueError("OpenScore Lieder path is too short for safe source grouping")
        group_parts = path.parts[:3]
    else:
        raise ValueError("source_id is not an approved OpenScore miner source")

    group_path = PurePosixPath(*group_parts).as_posix()
    digest = hashlib.sha256(group_path.encode("utf-8")).hexdigest()[:24]
    return f"{score.source_id}:{digest}"


def _flatten_frames(score: ParsedOpenScoreScore) -> tuple[tuple[HarmonicFrame, str, int], ...]:
    result: list[tuple[HarmonicFrame, str, int]] = []
    for measure, source_label in zip(score.measures, score.source_measure_labels):
        frames = build_harmonic_frames(measure)
        for ordinal, frame in enumerate(frames, start=1):
            result.append((frame, source_label, ordinal))
    return tuple(result)


def mine_openscore_ambiguities(
    score: ParsedOpenScoreScore,
    *,
    deterministic_engine_sha: str,
) -> OpenScoreAmbiguityMiningResult:
    """Mine final AMBIGUOUS frames using only causal frame-local deterministic evidence.

    No phrase plan, adjacency annotator, voice-function annotator, inferred key, or
    future frame is used. The previous-frame fingerprints are metadata for later
    human review/feature construction only; they do not influence mining decisions.
    """

    if not isinstance(score, ParsedOpenScoreScore):
        raise TypeError("score must be ParsedOpenScoreScore")
    if not isinstance(deterministic_engine_sha, str) or _SHA40_RE.fullmatch(deterministic_engine_sha) is None:
        raise ValueError("deterministic_engine_sha must be lowercase 40-character SHA")

    source_group_id = _source_group_id(score)
    flattened = _flatten_frames(score)
    frame_hashes = tuple(_frame_hash(item[0]) for item in flattened)
    retained: list[OpenScoreAmbiguityCandidate] = []

    for index, ((frame, source_label, frame_ordinal), frame_sha) in enumerate(zip(flattened, frame_hashes)):
        candidates = aggregate_frame_evidence(frame, None)
        decision = resolve_candidates_by_precedence(candidates)
        gated = apply_abstention_policy(decision)
        if gated.state is not FinalDecisionState.AMBIGUOUS:
            continue

        candidate_ids = tuple(sorted(_identity_token(item.identity) for item in gated.source_decision.candidates))
        if len(candidate_ids) < 2:
            raise RuntimeError("final AMBIGUOUS decision must expose at least two candidates")
        start_n, start_d = _fraction_pair(frame.start)
        end_n, end_d = _fraction_pair(frame.end)
        previous = frame_hashes[max(0, index - _MAX_PREVIOUS_FRAMES) : index]
        retained.append(
            OpenScoreAmbiguityCandidate(
                source_id=score.source_id,
                snapshot_commit_sha=score.snapshot_commit_sha,
                score_relative_path=score.score_relative_path,
                source_group_id=source_group_id,
                source_sha256=score.source_sha256,
                mxl_sha256=score.mxl_sha256,
                deterministic_engine_sha=deterministic_engine_sha,
                measure_ordinal=frame.measure_number,
                source_measure_label=source_label,
                frame_ordinal_in_measure=frame_ordinal,
                frame_start_numerator=start_n,
                frame_start_denominator=start_d,
                frame_end_numerator=end_n,
                frame_end_denominator=end_d,
                current_frame_sha256=frame_sha,
                candidate_ids=candidate_ids,
                candidate_set_sha256=_candidate_set_hash(candidate_ids),
                previous_frame_sha256=previous,
            )
        )

    return OpenScoreAmbiguityMiningResult(
        source_id=score.source_id,
        score_relative_path=score.score_relative_path,
        deterministic_engine_sha=deterministic_engine_sha,
        harmonic_frame_count=len(flattened),
        ambiguous_candidate_count=len(retained),
        candidates=tuple(retained),
    )
