"""Private-input runner for the Stage 8-0 deterministic baseline seal.

The runner accepts two local frozen CSV files, validates/adapts them through the
existing Teacher-Gold contracts, evaluates the existing deterministic public v1.0
runtime, and writes only a compact self-hashing seal JSON. Raw Teacher-Gold rows
are never written to the repository or copied into the seal.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Mapping

from .calibration import BenchmarkSplit
from .stage8_baseline_seal import (
    Stage8BaselineSeal,
    build_stage8_baseline_seal,
    serialize_stage8_baseline_seal,
)
from .teacher_gold_adapter import TEACHER_GOLD_SHEET_COLUMNS
from .teacher_gold_evaluation import evaluate_teacher_gold_assembly
from .teacher_gold_reference import TeacherGoldReferenceCase
from .teacher_gold_vocabulary_v0_3 import (
    adapt_teacher_gold_reference_row_v0_3,
    assemble_frozen_teacher_gold_benchmark_v0_3,
)


MAX_PRIVATE_CSV_BYTES = 256 * 1024
EXPECTED_PARTITION_ROWS = 100


class Stage8BaselineRunnerError(ValueError):
    pass


def _read_frozen_csv(
    path: Path,
    *,
    split: BenchmarkSplit,
) -> tuple[bytes, tuple[TeacherGoldReferenceCase, ...]]:
    if not isinstance(path, Path):
        raise TypeError("path must be pathlib.Path")
    if not isinstance(split, BenchmarkSplit):
        raise TypeError("split must be BenchmarkSplit")
    if not path.is_file():
        raise Stage8BaselineRunnerError(f"{split.value} CSV is not a regular file")

    raw = path.read_bytes()
    if not raw:
        raise Stage8BaselineRunnerError(f"{split.value} CSV must not be empty")
    if len(raw) > MAX_PRIVATE_CSV_BYTES:
        raise Stage8BaselineRunnerError(f"{split.value} CSV exceeds private input size limit")
    if b"\x00" in raw:
        raise Stage8BaselineRunnerError(f"{split.value} CSV contains NUL bytes")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise Stage8BaselineRunnerError(f"{split.value} CSV must be UTF-8") from exc

    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames is None:
        raise Stage8BaselineRunnerError(f"{split.value} CSV is missing a header")
    if tuple(reader.fieldnames) != TEACHER_GOLD_SHEET_COLUMNS:
        raise Stage8BaselineRunnerError(
            f"{split.value} CSV columns must exactly match Teacher-Gold v0.1 schema"
        )

    rows: list[Mapping[str, object]] = []
    for row in reader:
        if None in row:
            raise Stage8BaselineRunnerError(f"{split.value} CSV contains extra columns")
        rows.append(dict(row))
        if len(rows) > EXPECTED_PARTITION_ROWS:
            raise Stage8BaselineRunnerError(
                f"{split.value} CSV must contain exactly {EXPECTED_PARTITION_ROWS} rows"
            )
    if len(rows) != EXPECTED_PARTITION_ROWS:
        raise Stage8BaselineRunnerError(
            f"{split.value} CSV must contain exactly {EXPECTED_PARTITION_ROWS} rows"
        )

    cases = tuple(
        adapt_teacher_gold_reference_row_v0_3(row, split=split)
        for row in rows
    )
    return raw, cases


def run_stage8_baseline_seal(
    *,
    calibration_csv: Path,
    holdout_csv: Path,
    output_json: Path,
    engine_commit_sha: str,
) -> Stage8BaselineSeal:
    """Run one private 200-case baseline evaluation and atomically emit its seal."""

    if not isinstance(output_json, Path):
        raise TypeError("output_json must be pathlib.Path")
    if output_json.exists():
        raise Stage8BaselineRunnerError("output_json already exists; refusing overwrite")
    if not output_json.parent.is_dir():
        raise Stage8BaselineRunnerError("output_json parent directory does not exist")

    calibration_raw, calibration_cases = _read_frozen_csv(
        calibration_csv,
        split=BenchmarkSplit.CALIBRATION,
    )
    holdout_raw, holdout_cases = _read_frozen_csv(
        holdout_csv,
        split=BenchmarkSplit.HOLDOUT,
    )

    calibration_digest = hashlib.sha256(calibration_raw).hexdigest()
    holdout_digest = hashlib.sha256(holdout_raw).hexdigest()
    if calibration_digest == holdout_digest:
        raise Stage8BaselineRunnerError("calibration and holdout source digests must differ")

    assembly = assemble_frozen_teacher_gold_benchmark_v0_3(
        calibration_cases,
        holdout_cases,
    )
    report = evaluate_teacher_gold_assembly(assembly)
    seal = build_stage8_baseline_seal(
        report,
        engine_commit_sha=engine_commit_sha,
        calibration_source_sha256=calibration_digest,
        holdout_source_sha256=holdout_digest,
    )
    payload = serialize_stage8_baseline_seal(seal)

    encoded = (
        json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    temporary = output_json.with_name(f".{output_json.name}.tmp")
    if temporary.exists():
        raise Stage8BaselineRunnerError("temporary output path already exists")
    try:
        temporary.write_bytes(encoded)
        temporary.replace(output_json)
    finally:
        if temporary.exists():
            temporary.unlink()
    return seal


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run private frozen Teacher-Gold Stage 8-0 baseline seal"
    )
    parser.add_argument("--calibration-csv", required=True, type=Path)
    parser.add_argument("--holdout-csv", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--engine-commit-sha", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    seal = run_stage8_baseline_seal(
        calibration_csv=args.calibration_csv,
        holdout_csv=args.holdout_csv,
        output_json=args.output_json,
        engine_commit_sha=args.engine_commit_sha,
    )
    print(seal.status.value)
    print(seal.seal_sha256)
    return 0 if seal.status.value == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
