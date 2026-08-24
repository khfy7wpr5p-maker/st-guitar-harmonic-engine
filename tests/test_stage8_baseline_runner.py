import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from st_guitar_harmonic_engine.stage8_baseline_runner import (
    Stage8BaselineRunnerError,
    run_stage8_baseline_seal,
)
from st_guitar_harmonic_engine.stage8_baseline_seal import Stage8BaselineStatus
from st_guitar_harmonic_engine.teacher_gold_adapter import TEACHER_GOLD_SHEET_COLUMNS


ENGINE_SHA = "1" * 40


def _row(case_id: str, *, status: str = "VERIFIED") -> dict[str, str]:
    return {
        "example_id": case_id,
        "input_notes": "C4,E4,G4",
        "expected_state": "RESOLVED",
        "primary_candidate": "C major",
        "acceptable_alternatives": "",
        "inversion": "root_position",
        "teacher_reason": "Synthetic exact C major test case.",
        "annotation_status": status,
    }


def _write_partition(path: Path, start: int, *, status: str = "VERIFIED") -> bytes:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TEACHER_GOLD_SHEET_COLUMNS)
        writer.writeheader()
        for index in range(start, start + 100):
            writer.writerow(_row(f"TG-{index:04d}", status=status))
    return path.read_bytes()


class Stage8BaselineRunnerTests(unittest.TestCase):
    def test_private_runner_builds_ready_200_case_seal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calibration = root / "calibration.csv"
            holdout = root / "holdout.csv"
            output = root / "seal.json"
            calibration_raw = _write_partition(calibration, 1)
            holdout_raw = _write_partition(holdout, 101)

            seal = run_stage8_baseline_seal(
                calibration_csv=calibration,
                holdout_csv=holdout,
                output_json=output,
                engine_commit_sha=ENGINE_SHA,
            )

            self.assertIs(seal.status, Stage8BaselineStatus.READY)
            self.assertEqual(seal.reference_case_count, 200)
            self.assertEqual(seal.executable_case_count, 200)
            self.assertEqual(seal.correct_case_count, 200)
            self.assertEqual(seal.calibration.reference_case_count, 100)
            self.assertEqual(seal.holdout.reference_case_count, 100)
            self.assertEqual(
                seal.calibration_source_sha256,
                hashlib.sha256(calibration_raw).hexdigest(),
            )
            self.assertEqual(
                seal.holdout_source_sha256,
                hashlib.sha256(holdout_raw).hexdigest(),
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["seal_sha256"], seal.seal_sha256)
            self.assertNotIn("input_notes", output.read_text(encoding="utf-8"))
            self.assertNotIn("teacher_reason", output.read_text(encoding="utf-8"))

    def test_repeated_equivalent_runs_are_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calibration = root / "calibration.csv"
            holdout = root / "holdout.csv"
            first_output = root / "first.json"
            second_output = root / "second.json"
            _write_partition(calibration, 1)
            _write_partition(holdout, 101)

            first = run_stage8_baseline_seal(
                calibration_csv=calibration,
                holdout_csv=holdout,
                output_json=first_output,
                engine_commit_sha=ENGINE_SHA,
            )
            second = run_stage8_baseline_seal(
                calibration_csv=calibration,
                holdout_csv=holdout,
                output_json=second_output,
                engine_commit_sha=ENGINE_SHA,
            )
            self.assertEqual(first, second)
            self.assertEqual(first_output.read_bytes(), second_output.read_bytes())

    def test_draft_row_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calibration = root / "calibration.csv"
            holdout = root / "holdout.csv"
            output = root / "seal.json"
            _write_partition(calibration, 1, status="DRAFT")
            _write_partition(holdout, 101)
            with self.assertRaises(ValueError):
                run_stage8_baseline_seal(
                    calibration_csv=calibration,
                    holdout_csv=holdout,
                    output_json=output,
                    engine_commit_sha=ENGINE_SHA,
                )
            self.assertFalse(output.exists())

    def test_wrong_header_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calibration = root / "calibration.csv"
            holdout = root / "holdout.csv"
            output = root / "seal.json"
            calibration.write_text("example_id,input_notes\nTG-0001,C4\n", encoding="utf-8")
            _write_partition(holdout, 101)
            with self.assertRaises(Stage8BaselineRunnerError):
                run_stage8_baseline_seal(
                    calibration_csv=calibration,
                    holdout_csv=holdout,
                    output_json=output,
                    engine_commit_sha=ENGINE_SHA,
                )

    def test_wrong_frozen_namespace_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calibration = root / "calibration.csv"
            holdout = root / "holdout.csv"
            output = root / "seal.json"
            _write_partition(calibration, 2)
            _write_partition(holdout, 101)
            with self.assertRaises(ValueError):
                run_stage8_baseline_seal(
                    calibration_csv=calibration,
                    holdout_csv=holdout,
                    output_json=output,
                    engine_commit_sha=ENGINE_SHA,
                )

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calibration = root / "calibration.csv"
            holdout = root / "holdout.csv"
            output = root / "seal.json"
            _write_partition(calibration, 1)
            _write_partition(holdout, 101)
            output.write_text("keep-me", encoding="utf-8")
            with self.assertRaises(Stage8BaselineRunnerError):
                run_stage8_baseline_seal(
                    calibration_csv=calibration,
                    holdout_csv=holdout,
                    output_json=output,
                    engine_commit_sha=ENGINE_SHA,
                )
            self.assertEqual(output.read_text(encoding="utf-8"), "keep-me")


if __name__ == "__main__":
    unittest.main()
