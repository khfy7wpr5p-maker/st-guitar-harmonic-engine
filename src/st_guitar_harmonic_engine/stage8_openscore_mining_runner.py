"""Metadata-only local runner for Stage 8 OpenScore ambiguity mining.

The runner consumes a frozen, hash-pinned conversion-receipt manifest and local
MXL artifacts that were already produced by the separate MuseScore conversion
boundary. It performs no network access, no conversion, no human adjudication,
no model training, and no production promotion.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
import zipfile

from .stage8_openscore_ambiguity_miner import (
    STAGE8_OPENSCORE_AMBIGUITY_MINER_VERSION,
    OpenScoreAmbiguityCandidate,
    mine_openscore_ambiguities,
)
from .stage8_openscore_conversion import (
    OpenScoreConversionError,
    OpenScoreConversionReceipt,
    _parse_mxl_container_rootfile,
)
from .stage8_openscore_musicxml import OpenScoreMusicXMLError, parse_openscore_mxl
from .stage8_openscore_snapshot import canonical_openscore_snapshots


STAGE8_OPENSCORE_MINING_RUNNER_VERSION = "0.1"
STAGE8_OPENSCORE_MINING_MANIFEST_SCHEMA = (
    "st_guitar_harmonic_engine.stage8_openscore_mining_manifest"
)
STAGE8_OPENSCORE_MINING_OUTPUT_SCHEMA = (
    "st_guitar_harmonic_engine.stage8_openscore_mining_output"
)
_MAX_MANIFEST_BYTES = 8 * 1024 * 1024
_MAX_MANIFEST_ITEMS = 10_000
_MAX_CANDIDATES = 50_000
_MAX_OUTPUT_BYTES = 128 * 1024 * 1024
_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._+()/-]{0,127}$")
_CONTAINER_PATH = "META-INF/container.xml"

_MANIFEST_KEYS = frozenset({"schema", "version", "item_count", "items"})
_RECEIPT_KEYS = frozenset(
    {
        "source_id",
        "snapshot_commit_sha",
        "score_relative_path",
        "source_sha256",
        "output_relative_path",
        "output_sha256",
        "output_bytes",
        "rootfile_path",
        "executable_sha256",
        "executable_version",
        "exit_code",
    }
)


class OpenScoreMiningRunnerError(RuntimeError):
    """Raised when the local mining runner cannot prove a safe deterministic run."""


@dataclass(frozen=True, slots=True)
class OpenScoreMiningRunSummary:
    manifest_sha256: str
    deterministic_engine_sha: str
    source_item_count: int
    harmonic_frame_count: int
    ambiguous_candidate_count: int
    candidate_pool_sha256: str
    output_sha256: str
    output_bytes: int
    model_training_authorized: bool = False
    production_authority_granted: bool = False

    def __post_init__(self) -> None:
        for name in ("manifest_sha256", "candidate_pool_sha256", "output_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
                raise ValueError(f"{name} must be lowercase SHA-256")
        if not isinstance(self.deterministic_engine_sha, str) or _SHA40_RE.fullmatch(self.deterministic_engine_sha) is None:
            raise ValueError("deterministic_engine_sha must be lowercase 40-character SHA")
        for name in ("source_item_count", "harmonic_frame_count", "ambiguous_candidate_count", "output_bytes"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative int")
        if self.source_item_count <= 0:
            raise ValueError("source_item_count must be positive")
        if self.output_bytes <= 0:
            raise ValueError("output_bytes must be positive")
        if self.model_training_authorized or self.production_authority_granted:
            raise ValueError("mining runner cannot authorize training or production")


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read_bounded_regular_file(path_text: str, *, maximum_bytes: int, label: str) -> bytes:
    if not isinstance(path_text, str) or not path_text or not os.path.isabs(path_text):
        raise OpenScoreMiningRunnerError(f"{label} path must be a non-empty absolute path")
    path = Path(path_text)
    if path.is_symlink():
        raise OpenScoreMiningRunnerError(f"{label} cannot be a symlink")
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise OpenScoreMiningRunnerError(f"{label} does not exist") from exc
    if not resolved.is_file():
        raise OpenScoreMiningRunnerError(f"{label} must be a regular file")
    size = resolved.stat().st_size
    if size <= 0 or size > maximum_bytes:
        raise OpenScoreMiningRunnerError(f"{label} size is outside approved bounds")
    payload = resolved.read_bytes()
    if len(payload) != size:
        raise OpenScoreMiningRunnerError(f"{label} changed while being read")
    return payload


def _validated_posix_relative(value: str, *, suffix: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise OpenScoreMiningRunnerError("manifest contains an empty relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise OpenScoreMiningRunnerError("manifest contains an unsafe relative path")
    if len(path.parts) < 2 or path.parts[0] != "scores" or path.suffix.lower() != suffix:
        raise OpenScoreMiningRunnerError(f"manifest path must be scores/**/*{suffix}")
    if path.as_posix() != value:
        raise OpenScoreMiningRunnerError("manifest path must use canonical POSIX form")
    return path


def _receipt_from_manifest(value: object) -> OpenScoreConversionReceipt:
    if not isinstance(value, dict) or frozenset(value) != _RECEIPT_KEYS:
        raise OpenScoreMiningRunnerError("manifest receipt fields do not match the frozen schema")

    source_id = value["source_id"]
    snapshot_sha = value["snapshot_commit_sha"]
    snapshots = {item.source_id: item for item in canonical_openscore_snapshots()}
    if source_id not in snapshots:
        raise OpenScoreMiningRunnerError("manifest references an unapproved OpenScore source")
    if snapshot_sha != snapshots[source_id].commit_sha:
        raise OpenScoreMiningRunnerError("manifest snapshot SHA does not match the frozen source")

    score_path = _validated_posix_relative(value["score_relative_path"], suffix=".mscx")
    output_path = _validated_posix_relative(value["output_relative_path"], suffix=".mxl")
    if output_path != score_path.with_suffix(".mxl"):
        raise OpenScoreMiningRunnerError("receipt output path does not correspond to source score path")

    if not isinstance(value["executable_version"], str) or _VERSION_RE.fullmatch(value["executable_version"]) is None:
        raise OpenScoreMiningRunnerError("receipt executable version is not canonical")

    try:
        return OpenScoreConversionReceipt(
            source_id=source_id,
            snapshot_commit_sha=snapshot_sha,
            score_relative_path=score_path.as_posix(),
            source_sha256=value["source_sha256"],
            output_relative_path=output_path.as_posix(),
            output_sha256=value["output_sha256"],
            output_bytes=value["output_bytes"],
            rootfile_path=value["rootfile_path"],
            executable_sha256=value["executable_sha256"],
            executable_version=value["executable_version"],
            exit_code=value["exit_code"],
        )
    except (TypeError, ValueError, RuntimeError) as exc:
        raise OpenScoreMiningRunnerError("manifest contains an invalid conversion receipt") from exc


def _load_manifest(path_text: str, *, expected_sha256: str) -> tuple[str, tuple[OpenScoreConversionReceipt, ...]]:
    if not isinstance(expected_sha256, str) or _SHA256_RE.fullmatch(expected_sha256) is None:
        raise ValueError("expected_manifest_sha256 must be lowercase SHA-256")
    payload = _read_bounded_regular_file(path_text, maximum_bytes=_MAX_MANIFEST_BYTES, label="manifest")
    digest = _sha256_bytes(payload)
    if digest != expected_sha256:
        raise OpenScoreMiningRunnerError("manifest SHA-256 does not match the expected frozen digest")
    if b"\x00" in payload:
        raise OpenScoreMiningRunnerError("manifest contains NUL bytes")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise OpenScoreMiningRunnerError("manifest must be UTF-8") from exc
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OpenScoreMiningRunnerError("manifest JSON is malformed") from exc
    if not isinstance(document, dict) or frozenset(document) != _MANIFEST_KEYS:
        raise OpenScoreMiningRunnerError("manifest top-level fields do not match the frozen schema")
    if document["schema"] != STAGE8_OPENSCORE_MINING_MANIFEST_SCHEMA:
        raise OpenScoreMiningRunnerError("manifest schema is not approved")
    if document["version"] != STAGE8_OPENSCORE_MINING_RUNNER_VERSION:
        raise OpenScoreMiningRunnerError("manifest version is not approved")
    items = document["items"]
    if not isinstance(items, list) or not 1 <= len(items) <= _MAX_MANIFEST_ITEMS:
        raise OpenScoreMiningRunnerError("manifest item count is outside approved bounds")
    if isinstance(document["item_count"], bool) or not isinstance(document["item_count"], int):
        raise OpenScoreMiningRunnerError("manifest item_count must be an int")
    if document["item_count"] != len(items):
        raise OpenScoreMiningRunnerError("manifest item_count does not match items")

    receipts = tuple(_receipt_from_manifest(item) for item in items)
    keys = tuple((item.source_id, item.score_relative_path) for item in receipts)
    if len(set(keys)) != len(keys):
        raise OpenScoreMiningRunnerError("manifest contains duplicate source score entries")
    output_paths = tuple((item.source_id, item.output_relative_path) for item in receipts)
    if len(set(output_paths)) != len(output_paths):
        raise OpenScoreMiningRunnerError("manifest contains duplicate output entries")
    return digest, tuple(sorted(receipts, key=lambda item: (item.source_id, item.score_relative_path)))


def _resolve_mxl_root(value: str) -> Path:
    if not isinstance(value, str) or not value or not os.path.isabs(value):
        raise ValueError("mxl_root must be a non-empty absolute path")
    root = Path(value)
    if root.is_symlink():
        raise OpenScoreMiningRunnerError("mxl_root cannot be a symlink")
    try:
        resolved = root.resolve(strict=True)
    except FileNotFoundError as exc:
        raise OpenScoreMiningRunnerError("mxl_root does not exist") from exc
    if not resolved.is_dir():
        raise OpenScoreMiningRunnerError("mxl_root must be a directory")
    return resolved


def _resolve_mxl_path(root: Path, receipt: OpenScoreConversionReceipt) -> Path:
    relative = _validated_posix_relative(receipt.output_relative_path, suffix=".mxl")
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise OpenScoreMiningRunnerError("MXL path cannot traverse symlinks")
    try:
        resolved = cursor.resolve(strict=True)
    except FileNotFoundError as exc:
        raise OpenScoreMiningRunnerError("manifest MXL artifact does not exist") from exc
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise OpenScoreMiningRunnerError("MXL artifact escapes mxl_root or is not a regular file")
    return resolved


def _container_rootfile(path: Path) -> str:
    """Re-derive the MXL container rootfile so reconstructed receipts cannot drift."""

    try:
        with zipfile.ZipFile(path, "r") as archive:
            try:
                payload = archive.read(_CONTAINER_PATH)
            except KeyError as exc:
                raise OpenScoreMiningRunnerError("MXL is missing META-INF/container.xml") from exc
    except zipfile.BadZipFile as exc:
        raise OpenScoreMiningRunnerError("MXL is not a valid ZIP archive") from exc
    try:
        return _parse_mxl_container_rootfile(payload)
    except OpenScoreConversionError as exc:
        raise OpenScoreMiningRunnerError("MXL container.xml is invalid") from exc


def _receipt_hash(receipt: OpenScoreConversionReceipt) -> str:
    payload = {
        "source_id": receipt.source_id,
        "snapshot_commit_sha": receipt.snapshot_commit_sha,
        "score_relative_path": receipt.score_relative_path,
        "source_sha256": receipt.source_sha256,
        "output_relative_path": receipt.output_relative_path,
        "output_sha256": receipt.output_sha256,
        "output_bytes": receipt.output_bytes,
        "rootfile_path": receipt.rootfile_path,
        "executable_sha256": receipt.executable_sha256,
        "executable_version": receipt.executable_version,
        "exit_code": receipt.exit_code,
    }
    return _sha256_bytes(_canonical_json(payload).encode("utf-8"))


def _candidate_payload(candidate: OpenScoreAmbiguityCandidate, *, receipt_sha256: str) -> dict[str, object]:
    identity_payload = {
        "source_id": candidate.source_id,
        "snapshot_commit_sha": candidate.snapshot_commit_sha,
        "score_relative_path": candidate.score_relative_path,
        "measure_ordinal": candidate.measure_ordinal,
        "frame_ordinal_in_measure": candidate.frame_ordinal_in_measure,
        "current_frame_sha256": candidate.current_frame_sha256,
        "candidate_set_sha256": candidate.candidate_set_sha256,
    }
    candidate_uid = _sha256_bytes(_canonical_json(identity_payload).encode("utf-8"))
    return {
        "record_type": "candidate",
        "candidate_uid": candidate_uid,
        "receipt_sha256": receipt_sha256,
        "source_id": candidate.source_id,
        "snapshot_commit_sha": candidate.snapshot_commit_sha,
        "score_relative_path": candidate.score_relative_path,
        "source_group_id": candidate.source_group_id,
        "source_sha256": candidate.source_sha256,
        "mxl_sha256": candidate.mxl_sha256,
        "deterministic_engine_sha": candidate.deterministic_engine_sha,
        "measure_ordinal": candidate.measure_ordinal,
        "source_measure_label": candidate.source_measure_label,
        "frame_ordinal_in_measure": candidate.frame_ordinal_in_measure,
        "frame_start": [candidate.frame_start_numerator, candidate.frame_start_denominator],
        "frame_end": [candidate.frame_end_numerator, candidate.frame_end_denominator],
        "current_frame_sha256": candidate.current_frame_sha256,
        "candidate_ids": list(candidate.candidate_ids),
        "candidate_set_sha256": candidate.candidate_set_sha256,
        "previous_frame_sha256": list(candidate.previous_frame_sha256),
        "preferred_candidate_id": None,
        "annotation_status": "draft",
        "model_training_authorized": False,
        "production_authority_granted": False,
    }


def _prepare_output_path(output_text: str, *, mxl_root: Path) -> Path:
    if not isinstance(output_text, str) or not output_text or not os.path.isabs(output_text):
        raise ValueError("output_jsonl must be a non-empty absolute path")
    output = Path(output_text)
    if output.exists() or output.is_symlink():
        raise OpenScoreMiningRunnerError("runner refuses to overwrite existing output")
    parent = output.parent
    if parent.is_symlink():
        raise OpenScoreMiningRunnerError("output parent cannot be a symlink")
    try:
        resolved_parent = parent.resolve(strict=True)
    except FileNotFoundError as exc:
        raise OpenScoreMiningRunnerError("output parent does not exist") from exc
    if not resolved_parent.is_dir():
        raise OpenScoreMiningRunnerError("output parent must be a directory")
    if resolved_parent == mxl_root or resolved_parent.is_relative_to(mxl_root):
        raise OpenScoreMiningRunnerError("mining output must be outside mxl_root")
    return resolved_parent / output.name


def _publish_atomic_no_overwrite(output: Path, payload: bytes) -> None:
    if len(payload) <= 0 or len(payload) > _MAX_OUTPUT_BYTES:
        raise OpenScoreMiningRunnerError("metadata output size is outside approved bounds")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix=f".{output.name}.", suffix=".tmp", dir=output.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, output)
        except FileExistsError as exc:
            raise OpenScoreMiningRunnerError("runner refuses to overwrite existing output") from exc
        except OSError as exc:
            raise OpenScoreMiningRunnerError("atomic output publication failed") from exc
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def run_openscore_mining_manifest(
    *,
    manifest_path: str,
    expected_manifest_sha256: str,
    mxl_root: str,
    deterministic_engine_sha: str,
    output_jsonl: str,
) -> OpenScoreMiningRunSummary:
    """Parse and mine one frozen local manifest, writing metadata-only JSONL."""

    if not isinstance(deterministic_engine_sha, str) or _SHA40_RE.fullmatch(deterministic_engine_sha) is None:
        raise ValueError("deterministic_engine_sha must be lowercase 40-character SHA")
    root = _resolve_mxl_root(mxl_root)
    output = _prepare_output_path(output_jsonl, mxl_root=root)
    manifest_sha, receipts = _load_manifest(manifest_path, expected_sha256=expected_manifest_sha256)

    candidate_records: list[dict[str, object]] = []
    frame_count = 0
    seen_candidate_uids: set[str] = set()

    for receipt in receipts:
        mxl_path = _resolve_mxl_path(root, receipt)
        if _container_rootfile(mxl_path) != receipt.rootfile_path:
            raise OpenScoreMiningRunnerError("receipt rootfile does not match MXL container metadata")
        try:
            parsed = parse_openscore_mxl(str(mxl_path), receipt)
            result = mine_openscore_ambiguities(
                parsed,
                deterministic_engine_sha=deterministic_engine_sha,
            )
        except (OpenScoreMusicXMLError, TypeError, ValueError, RuntimeError) as exc:
            raise OpenScoreMiningRunnerError(
                f"mining failed for {receipt.source_id}:{receipt.score_relative_path}"
            ) from exc
        frame_count += result.harmonic_frame_count
        receipt_sha = _receipt_hash(receipt)
        for candidate in result.candidates:
            record = _candidate_payload(candidate, receipt_sha256=receipt_sha)
            uid = record["candidate_uid"]
            if not isinstance(uid, str) or uid in seen_candidate_uids:
                raise OpenScoreMiningRunnerError("mining produced duplicate candidate identity")
            seen_candidate_uids.add(uid)
            candidate_records.append(record)
            if len(candidate_records) > _MAX_CANDIDATES:
                raise OpenScoreMiningRunnerError("candidate count exceeds approved runner bound")

    candidate_records.sort(
        key=lambda item: (
            item["source_id"],
            item["score_relative_path"],
            item["measure_ordinal"],
            item["frame_start"][0] / item["frame_start"][1],
            item["frame_ordinal_in_measure"],
            item["candidate_uid"],
        )
    )
    candidate_lines = tuple((_canonical_json(item) + "\n").encode("utf-8") for item in candidate_records)
    candidate_blob = b"".join(candidate_lines)
    candidate_pool_sha = _sha256_bytes(candidate_blob)
    header = {
        "record_type": "run",
        "schema": STAGE8_OPENSCORE_MINING_OUTPUT_SCHEMA,
        "version": STAGE8_OPENSCORE_MINING_RUNNER_VERSION,
        "miner_version": STAGE8_OPENSCORE_AMBIGUITY_MINER_VERSION,
        "manifest_sha256": manifest_sha,
        "deterministic_engine_sha": deterministic_engine_sha,
        "source_item_count": len(receipts),
        "harmonic_frame_count": frame_count,
        "ambiguous_candidate_count": len(candidate_records),
        "candidate_pool_sha256": candidate_pool_sha,
        "model_training_authorized": False,
        "production_authority_granted": False,
    }
    output_payload = (_canonical_json(header) + "\n").encode("utf-8") + candidate_blob
    output_sha = _sha256_bytes(output_payload)
    _publish_atomic_no_overwrite(output, output_payload)

    return OpenScoreMiningRunSummary(
        manifest_sha256=manifest_sha,
        deterministic_engine_sha=deterministic_engine_sha,
        source_item_count=len(receipts),
        harmonic_frame_count=frame_count,
        ambiguous_candidate_count=len(candidate_records),
        candidate_pool_sha256=candidate_pool_sha,
        output_sha256=output_sha,
        output_bytes=len(output_payload),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run metadata-only Stage 8 OpenScore ambiguity mining")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--mxl-root", required=True)
    parser.add_argument("--engine-commit-sha", required=True)
    parser.add_argument("--output-jsonl", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        summary = run_openscore_mining_manifest(
            manifest_path=args.manifest,
            expected_manifest_sha256=args.manifest_sha256,
            mxl_root=args.mxl_root,
            deterministic_engine_sha=args.engine_commit_sha,
            output_jsonl=args.output_jsonl,
        )
    except (OpenScoreMiningRunnerError, ValueError, TypeError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(
        _canonical_json(
            {
                "status": "READY_FOR_HUMAN_REVIEW",
                "manifest_sha256": summary.manifest_sha256,
                "deterministic_engine_sha": summary.deterministic_engine_sha,
                "source_item_count": summary.source_item_count,
                "harmonic_frame_count": summary.harmonic_frame_count,
                "ambiguous_candidate_count": summary.ambiguous_candidate_count,
                "candidate_pool_sha256": summary.candidate_pool_sha256,
                "output_sha256": summary.output_sha256,
                "output_bytes": summary.output_bytes,
                "model_training_authorized": False,
                "production_authority_granted": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
