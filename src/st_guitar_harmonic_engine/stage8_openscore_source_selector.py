"""Deterministic diversified OpenScore source selector for Stage 8 v0.1.

The selector chooses score files to *mine*, not musical answers or final corpus
labels. It is metadata-only, input-order independent, and fail-closed when the
requested source diversity cannot be satisfied.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import PurePosixPath

from .stage8_sequence_context_sampling_policy import (
    Stage8SamplingSourcePolicy,
    canonical_stage8_sequence_context_sampling_policy,
)


STAGE8_OPENSCORE_SOURCE_SELECTOR_VERSION = "0.1"
_APPROVED_SOURCES = frozenset({"openscore-string-quartets", "openscore-lieder"})


class OpenScoreSourceSelectionError(RuntimeError):
    """Raised when a safe deterministic diversified selection cannot be proven."""


@dataclass(frozen=True, slots=True)
class OpenScoreSourceDescriptor:
    source_id: str
    score_relative_path: str
    composer_component: str
    source_group_id: str

    def __post_init__(self) -> None:
        if self.source_id not in _APPROVED_SOURCES:
            raise ValueError("source_id is not approved for OpenScore source selection")
        for name in ("score_relative_path", "composer_component", "source_group_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise TypeError(f"{name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class OpenScoreSourceSelection:
    source_id: str
    requested_source_items: int
    selected: tuple[OpenScoreSourceDescriptor, ...]
    distinct_composer_count: int
    distinct_source_group_count: int
    selection_sha256: str
    model_training_authorized: bool = False
    production_authority_granted: bool = False

    def __post_init__(self) -> None:
        if self.source_id not in _APPROVED_SOURCES:
            raise ValueError("source_id is not approved")
        if isinstance(self.requested_source_items, bool) or not isinstance(self.requested_source_items, int):
            raise TypeError("requested_source_items must be int")
        if self.requested_source_items <= 0:
            raise ValueError("requested_source_items must be positive")
        if not isinstance(self.selected, tuple) or any(
            not isinstance(item, OpenScoreSourceDescriptor) for item in self.selected
        ):
            raise TypeError("selected must contain OpenScoreSourceDescriptor values")
        if len(self.selected) != self.requested_source_items:
            raise ValueError("selected count must equal requested_source_items")
        if any(item.source_id != self.source_id for item in self.selected):
            raise ValueError("selected descriptors must match source_id")
        if len({item.score_relative_path for item in self.selected}) != len(self.selected):
            raise ValueError("selected paths must be unique")
        if len({item.source_group_id for item in self.selected}) != len(self.selected):
            raise ValueError("v0.1 selector requires one score per source group")
        composers = {item.composer_component for item in self.selected}
        groups = {item.source_group_id for item in self.selected}
        if self.distinct_composer_count != len(composers):
            raise ValueError("distinct_composer_count mismatch")
        if self.distinct_source_group_count != len(groups):
            raise ValueError("distinct_source_group_count mismatch")
        if not isinstance(self.selection_sha256, str) or len(self.selection_sha256) != 64:
            raise ValueError("selection_sha256 must be lowercase SHA-256")
        if any(ch not in "0123456789abcdef" for ch in self.selection_sha256):
            raise ValueError("selection_sha256 must be lowercase SHA-256")
        if self.model_training_authorized or self.production_authority_granted:
            raise ValueError("source selection cannot authorize training or production")


def _sampling_policy(source_id: str) -> Stage8SamplingSourcePolicy:
    if source_id not in _APPROVED_SOURCES:
        raise ValueError("source_id is not approved for OpenScore selection")
    policy = canonical_stage8_sequence_context_sampling_policy()
    by_id = {item.source_id: item for item in policy.sources}
    return by_id[source_id]


def _canonical_score_path(source_id: str, value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("score path must be a non-empty NUL-free string")
    path = PurePosixPath(value)
    if path.is_absolute() or "." in path.parts or ".." in path.parts:
        raise ValueError("score path must be safe relative POSIX form")
    if path.as_posix() != value or path.suffix.lower() != ".mscx":
        raise ValueError("score path must be canonical .mscx POSIX form")
    if not path.parts or path.parts[0] != "scores":
        raise ValueError("score path must live below scores/")
    if source_id == "openscore-string-quartets":
        if len(path.parts) < 4:
            raise ValueError("String Quartets score path is too short")
    elif source_id == "openscore-lieder":
        if len(path.parts) < 5:
            raise ValueError("Lieder score path is too short")
    else:
        raise ValueError("source_id is not approved")
    return path


def _group_id(source_id: str, path: PurePosixPath) -> str:
    if source_id == "openscore-string-quartets":
        group_path = path.parent.as_posix()
    elif source_id == "openscore-lieder":
        # Match the ambiguity miner: scores/<composer>/<set-or-cycle>/...
        group_path = PurePosixPath(*path.parts[:3]).as_posix()
    else:
        raise ValueError("source_id is not approved")
    digest = hashlib.sha256(group_path.encode("utf-8")).hexdigest()[:24]
    return f"{source_id}:{digest}"


def describe_openscore_source(source_id: str, score_relative_path: str) -> OpenScoreSourceDescriptor:
    """Return the canonical composer/group metadata used by the selector."""

    path = _canonical_score_path(source_id, score_relative_path)
    composer = path.parts[1]
    if not composer:
        raise ValueError("composer path component cannot be empty")
    return OpenScoreSourceDescriptor(
        source_id=source_id,
        score_relative_path=path.as_posix(),
        composer_component=composer,
        source_group_id=_group_id(source_id, path),
    )


def _rank(source_id: str, category: str, value: str) -> str:
    payload = (
        f"{STAGE8_OPENSCORE_SOURCE_SELECTOR_VERSION}|{source_id}|{category}|{value}"
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _selection_digest(source_id: str, selected: tuple[OpenScoreSourceDescriptor, ...]) -> str:
    payload = {
        "version": STAGE8_OPENSCORE_SOURCE_SELECTOR_VERSION,
        "source_id": source_id,
        "selected": [
            {
                "score_relative_path": item.score_relative_path,
                "composer_component": item.composer_component,
                "source_group_id": item.source_group_id,
            }
            for item in selected
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def select_diversified_openscore_sources(
    *,
    source_id: str,
    score_relative_paths: tuple[str, ...],
    requested_source_items: int,
    excluded_score_relative_paths: frozenset[str] = frozenset(),
    excluded_source_group_ids: frozenset[str] = frozenset(),
) -> OpenScoreSourceSelection:
    """Select diverse source items deterministically, independent of input order.

    v0.1 selects at most one score from each source group. Composer caps are
    derived from the frozen final-case sampling policy so source mining cannot
    quietly reintroduce the concentration that the final policy forbids.
    """

    if source_id not in _APPROVED_SOURCES:
        raise ValueError("source_id is not approved for OpenScore selection")
    if not isinstance(score_relative_paths, tuple) or any(
        not isinstance(item, str) for item in score_relative_paths
    ):
        raise TypeError("score_relative_paths must be tuple[str, ...]")
    if not score_relative_paths:
        raise OpenScoreSourceSelectionError("source pool is empty")
    if isinstance(requested_source_items, bool) or not isinstance(requested_source_items, int):
        raise TypeError("requested_source_items must be int")
    if requested_source_items <= 0:
        raise ValueError("requested_source_items must be positive")
    for name, values in (
        ("excluded_score_relative_paths", excluded_score_relative_paths),
        ("excluded_source_group_ids", excluded_source_group_ids),
    ):
        if not isinstance(values, frozenset) or any(not isinstance(item, str) or not item for item in values):
            raise TypeError(f"{name} must be frozenset[str]")

    if len(set(score_relative_paths)) != len(score_relative_paths):
        raise OpenScoreSourceSelectionError("source pool contains duplicate score paths")

    descriptors = tuple(describe_openscore_source(source_id, path) for path in score_relative_paths)
    valid_excluded_paths = {
        describe_openscore_source(source_id, path).score_relative_path
        for path in excluded_score_relative_paths
    }
    expected_group_prefix = f"{source_id}:"
    if any(not item.startswith(expected_group_prefix) for item in excluded_source_group_ids):
        raise ValueError("excluded source-group id does not match source_id")

    eligible = tuple(
        item
        for item in descriptors
        if item.score_relative_path not in valid_excluded_paths
        and item.source_group_id not in excluded_source_group_ids
    )
    if not eligible:
        raise OpenScoreSourceSelectionError("no eligible source items remain after exclusions")

    policy = _sampling_policy(source_id)
    if policy.max_cases_per_composer is None or policy.min_distinct_composers is None:
        raise RuntimeError("OpenScore source policy must define composer diversity")
    max_items_per_composer = math.ceil(
        policy.max_cases_per_composer / policy.max_cases_per_source_item
    )
    min_composers_required = min(requested_source_items, policy.min_distinct_composers)

    buckets: dict[str, list[OpenScoreSourceDescriptor]] = {}
    for item in eligible:
        buckets.setdefault(item.composer_component, []).append(item)
    for composer, items in buckets.items():
        items.sort(
            key=lambda item: (
                _rank(source_id, "score", item.score_relative_path),
                item.score_relative_path,
            )
        )

    composer_order = sorted(
        buckets,
        key=lambda composer: (_rank(source_id, "composer", composer), composer),
    )

    selected: list[OpenScoreSourceDescriptor] = []
    used_groups: set[str] = set()
    composer_counts: dict[str, int] = {composer: 0 for composer in buckets}

    while len(selected) < requested_source_items:
        progress = False
        for composer in composer_order:
            if len(selected) >= requested_source_items:
                break
            if composer_counts[composer] >= max_items_per_composer:
                continue
            bucket = buckets[composer]
            candidate = next(
                (item for item in bucket if item.source_group_id not in used_groups),
                None,
            )
            if candidate is None:
                continue
            selected.append(candidate)
            used_groups.add(candidate.source_group_id)
            composer_counts[composer] += 1
            bucket.remove(candidate)
            progress = True
        if not progress:
            break

    if len(selected) != requested_source_items:
        raise OpenScoreSourceSelectionError(
            "requested selection cannot satisfy source-group uniqueness and composer caps"
        )
    distinct_composers = len({item.composer_component for item in selected})
    if distinct_composers < min_composers_required:
        raise OpenScoreSourceSelectionError(
            "requested selection cannot satisfy the frozen composer diversity floor"
        )

    result = tuple(selected)
    return OpenScoreSourceSelection(
        source_id=source_id,
        requested_source_items=requested_source_items,
        selected=result,
        distinct_composer_count=distinct_composers,
        distinct_source_group_count=len(used_groups),
        selection_sha256=_selection_digest(source_id, result),
    )
