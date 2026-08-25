"""Fail-closed local MuseScore conversion boundary for frozen OpenScore snapshots.

This adapter converts one already-materialized, content-hashed ``.mscx`` source to
one ``.mxl`` file. It never downloads data, invokes a shell, extracts MXL payloads,
mines harmonic labels, starts model training, or grants production authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Callable, Protocol
import xml.etree.ElementTree as ET
import zipfile

from .stage8_openscore_snapshot import canonical_openscore_snapshots


STAGE8_OPENSCORE_CONVERSION_VERSION = "0.1"
_MAX_SOURCE_BYTES = 64 * 1024 * 1024
_DEFAULT_MAX_OUTPUT_BYTES = 128 * 1024 * 1024
_DEFAULT_MAX_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
_MAX_ZIP_ENTRIES = 256
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._+()/-]{0,127}$")
_CONTAINER_PATH = "META-INF/container.xml"
_CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"


class OpenScoreConversionError(RuntimeError):
    """Raised when any conversion/integrity gate fails closed."""


class _Runner(Protocol):
    def __call__(self, args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]: ...


@dataclass(frozen=True, slots=True)
class MuseScoreBinaryIdentity:
    executable_path: str
    executable_sha256: str
    version_text: str

    def __post_init__(self) -> None:
        if not isinstance(self.executable_path, str) or not self.executable_path:
            raise TypeError("executable_path must be a non-empty string")
        if not os.path.isabs(self.executable_path):
            raise ValueError("executable_path must be absolute")
        if not isinstance(self.executable_sha256, str) or _SHA256_RE.fullmatch(self.executable_sha256) is None:
            raise ValueError("executable_sha256 must be lowercase SHA-256")
        if not isinstance(self.version_text, str) or _VERSION_RE.fullmatch(self.version_text) is None:
            raise ValueError("version_text must be a bounded canonical version string")


@dataclass(frozen=True, slots=True)
class OpenScoreConversionRequest:
    source_id: str
    snapshot_commit_sha: str
    input_root: str
    output_root: str
    score_relative_path: str
    source_sha256: str
    binary: MuseScoreBinaryIdentity
    timeout_seconds: int = 180
    max_output_bytes: int = _DEFAULT_MAX_OUTPUT_BYTES
    max_uncompressed_bytes: int = _DEFAULT_MAX_UNCOMPRESSED_BYTES

    def __post_init__(self) -> None:
        snapshots = {item.source_id: item for item in canonical_openscore_snapshots()}
        if self.source_id not in snapshots:
            raise ValueError("source_id must be one approved frozen OpenScore source")
        if self.snapshot_commit_sha != snapshots[self.source_id].commit_sha:
            raise ValueError("snapshot_commit_sha must match the frozen source snapshot")
        for name in ("input_root", "output_root"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value or not os.path.isabs(value):
                raise ValueError(f"{name} must be a non-empty absolute path")
        _validated_score_relative_path(self.score_relative_path)
        if not isinstance(self.source_sha256, str) or _SHA256_RE.fullmatch(self.source_sha256) is None:
            raise ValueError("source_sha256 must be lowercase SHA-256")
        if not isinstance(self.binary, MuseScoreBinaryIdentity):
            raise TypeError("binary must be MuseScoreBinaryIdentity")
        if isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, int):
            raise TypeError("timeout_seconds must be int")
        if not 1 <= self.timeout_seconds <= 600:
            raise ValueError("timeout_seconds must be in 1..600")
        for name, maximum in (
            ("max_output_bytes", 512 * 1024 * 1024),
            ("max_uncompressed_bytes", 1024 * 1024 * 1024),
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0 or value > maximum:
                raise ValueError(f"{name} is outside the approved bound")
        if self.max_uncompressed_bytes < self.max_output_bytes:
            raise ValueError("max_uncompressed_bytes cannot be smaller than max_output_bytes")


@dataclass(frozen=True, slots=True)
class OpenScoreConversionReceipt:
    source_id: str
    snapshot_commit_sha: str
    score_relative_path: str
    source_sha256: str
    output_relative_path: str
    output_sha256: str
    output_bytes: int
    rootfile_path: str
    executable_sha256: str
    executable_version: str
    exit_code: int
    model_training_authorized: bool = False
    production_authority_granted: bool = False

    def __post_init__(self) -> None:
        for name in ("source_sha256", "output_sha256", "executable_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
                raise ValueError(f"{name} must be lowercase SHA-256")
        if isinstance(self.output_bytes, bool) or not isinstance(self.output_bytes, int) or self.output_bytes <= 0:
            raise ValueError("output_bytes must be a positive int")
        if self.exit_code != 0:
            raise ValueError("successful receipt requires exit_code 0")
        if self.model_training_authorized or self.production_authority_granted:
            raise ValueError("conversion receipt cannot authorize training or production")
        _validated_score_relative_path(self.score_relative_path)
        if not self.output_relative_path.endswith(".mxl"):
            raise ValueError("output_relative_path must end in .mxl")
        _validated_archive_member(self.rootfile_path)


def _validated_score_relative_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise TypeError("score_relative_path must be a non-empty string")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ValueError("score_relative_path must be normalized and relative")
    if len(path.parts) < 2 or path.parts[0] != "scores" or path.suffix.lower() != ".mscx":
        raise ValueError("score_relative_path must be scores/**/*.mscx")
    return path


def _validated_archive_member(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise OpenScoreConversionError("archive member path is empty")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise OpenScoreConversionError("archive member path is unsafe")
    return path


def _sha256_file(path: Path, *, maximum_bytes: int | None = None) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if maximum_bytes is not None and size > maximum_bytes:
                raise OpenScoreConversionError("file exceeds approved byte bound")
            digest.update(chunk)
    return digest.hexdigest(), size


def _resolve_root(value: str) -> Path:
    root = Path(value)
    if root.is_symlink():
        raise OpenScoreConversionError("workspace root cannot be a symlink")
    try:
        resolved = root.resolve(strict=True)
    except FileNotFoundError as exc:
        raise OpenScoreConversionError("workspace root does not exist") from exc
    if not resolved.is_dir():
        raise OpenScoreConversionError("workspace root must be a directory")
    return resolved


def _resolve_source(request: OpenScoreConversionRequest) -> tuple[Path, PurePosixPath]:
    relative = _validated_score_relative_path(request.score_relative_path)
    root = _resolve_root(request.input_root)
    source = root.joinpath(*relative.parts)
    if source.is_symlink():
        raise OpenScoreConversionError("source score cannot be a symlink")
    try:
        resolved = source.resolve(strict=True)
    except FileNotFoundError as exc:
        raise OpenScoreConversionError("source score does not exist") from exc
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise OpenScoreConversionError("source score escapes input_root or is not a file")
    return resolved, relative


def _resolve_output(request: OpenScoreConversionRequest, relative: PurePosixPath) -> tuple[Path, str]:
    input_root = _resolve_root(request.input_root)
    output_root = _resolve_root(request.output_root)
    if output_root == input_root or output_root.is_relative_to(input_root) or input_root.is_relative_to(output_root):
        raise OpenScoreConversionError("input_root and output_root must be disjoint")
    output_relative = relative.with_suffix(".mxl")
    parent = output_root.joinpath(*output_relative.parent.parts)
    parent.mkdir(parents=True, exist_ok=True)
    resolved_parent = parent.resolve(strict=True)
    if not resolved_parent.is_relative_to(output_root):
        raise OpenScoreConversionError("output parent escapes output_root")
    cursor = output_root
    for part in output_relative.parent.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise OpenScoreConversionError("output path cannot traverse symlinks")
    output = resolved_parent / output_relative.name
    if output.exists() or output.is_symlink():
        raise OpenScoreConversionError("conversion refuses to overwrite existing output")
    return output, output_relative.as_posix()


def _verify_binary(binary: MuseScoreBinaryIdentity) -> Path:
    executable = Path(binary.executable_path)
    try:
        resolved = executable.resolve(strict=True)
    except FileNotFoundError as exc:
        raise OpenScoreConversionError("MuseScore executable does not exist") from exc
    if not resolved.is_file():
        raise OpenScoreConversionError("MuseScore executable must be a file")
    digest, _ = _sha256_file(resolved, maximum_bytes=512 * 1024 * 1024)
    if digest != binary.executable_sha256:
        raise OpenScoreConversionError("MuseScore executable SHA-256 mismatch")
    return resolved


def planned_musescore_argv(request: OpenScoreConversionRequest) -> tuple[str, str, str, str]:
    """Return the shell-free single-score MuseScore CLI argv after path validation."""

    if not isinstance(request, OpenScoreConversionRequest):
        raise TypeError("request must be OpenScoreConversionRequest")
    source, relative = _resolve_source(request)
    output, _ = _resolve_output(request, relative)
    executable = _verify_binary(request.binary)
    return (str(executable), "-o", str(output), str(source))


def _validate_mxl(path: Path, request: OpenScoreConversionRequest) -> str:
    if path.is_symlink() or not path.is_file():
        raise OpenScoreConversionError("conversion output must be a regular file")
    if not zipfile.is_zipfile(path):
        raise OpenScoreConversionError("conversion output is not a valid MXL/ZIP archive")

    try:
        with zipfile.ZipFile(path, "r") as archive:
            infos = archive.infolist()
            if not infos or len(infos) > _MAX_ZIP_ENTRIES:
                raise OpenScoreConversionError("MXL entry count is outside approved bounds")
            total_uncompressed = 0
            names: set[str] = set()
            for info in infos:
                member = _validated_archive_member(info.filename)
                name = member.as_posix()
                if name in names:
                    raise OpenScoreConversionError("MXL contains duplicate member names")
                names.add(name)
                if info.flag_bits & 0x1:
                    raise OpenScoreConversionError("encrypted MXL members are forbidden")
                total_uncompressed += info.file_size
                if total_uncompressed > request.max_uncompressed_bytes:
                    raise OpenScoreConversionError("MXL uncompressed size exceeds approved bound")
            if _CONTAINER_PATH not in names:
                raise OpenScoreConversionError("MXL is missing META-INF/container.xml")
            container_info = archive.getinfo(_CONTAINER_PATH)
            if container_info.file_size > 1024 * 1024:
                raise OpenScoreConversionError("MXL container.xml exceeds approved bound")
            container = archive.read(container_info)
            try:
                root = ET.fromstring(container)
            except ET.ParseError as exc:
                raise OpenScoreConversionError("MXL container.xml is malformed") from exc
            rootfiles = root.findall(f".//{{{_CONTAINER_NS}}}rootfile")
            if len(rootfiles) != 1:
                raise OpenScoreConversionError("MXL must declare exactly one rootfile")
            rootfile_path = rootfiles[0].attrib.get("full-path", "")
            rootfile = _validated_archive_member(rootfile_path).as_posix()
            if rootfile not in names:
                raise OpenScoreConversionError("MXL declared rootfile is missing")
            if PurePosixPath(rootfile).suffix.lower() not in {".xml", ".musicxml"}:
                raise OpenScoreConversionError("MXL rootfile must be MusicXML")
            return rootfile
    except zipfile.BadZipFile as exc:
        raise OpenScoreConversionError("conversion output is a malformed ZIP archive") from exc


def execute_musescore_conversion(
    request: OpenScoreConversionRequest,
    *,
    runner: _Runner = subprocess.run,
) -> OpenScoreConversionReceipt:
    """Execute one bounded shell-free conversion and return an integrity receipt."""

    if not isinstance(request, OpenScoreConversionRequest):
        raise TypeError("request must be OpenScoreConversionRequest")
    source, relative = _resolve_source(request)
    source_digest, source_bytes = _sha256_file(source, maximum_bytes=_MAX_SOURCE_BYTES)
    if source_bytes == 0 or source_digest != request.source_sha256:
        raise OpenScoreConversionError("source score SHA-256 mismatch or empty source")
    output, output_relative = _resolve_output(request, relative)
    executable = _verify_binary(request.binary)
    argv = [str(executable), "-o", str(output), str(source)]

    try:
        completed = runner(
            argv,
            shell=False,
            check=False,
            timeout=request.timeout_seconds,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.TimeoutExpired as exc:
        raise OpenScoreConversionError("MuseScore conversion timed out") from exc
    except OSError as exc:
        raise OpenScoreConversionError("MuseScore conversion could not start") from exc

    if not isinstance(completed, subprocess.CompletedProcess):
        raise OpenScoreConversionError("conversion runner returned an invalid result")
    if completed.returncode != 0:
        raise OpenScoreConversionError("MuseScore conversion exited non-zero")
    if not output.exists():
        raise OpenScoreConversionError("MuseScore reported success without output")

    output_digest, output_bytes = _sha256_file(output, maximum_bytes=request.max_output_bytes)
    if output_bytes == 0:
        raise OpenScoreConversionError("MuseScore produced an empty output")
    rootfile = _validate_mxl(output, request)

    return OpenScoreConversionReceipt(
        source_id=request.source_id,
        snapshot_commit_sha=request.snapshot_commit_sha,
        score_relative_path=relative.as_posix(),
        source_sha256=source_digest,
        output_relative_path=output_relative,
        output_sha256=output_digest,
        output_bytes=output_bytes,
        rootfile_path=rootfile,
        executable_sha256=request.binary.executable_sha256,
        executable_version=request.binary.version_text,
        exit_code=completed.returncode,
    )
