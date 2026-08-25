import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from st_guitar_harmonic_engine.stage8_openscore_mining_runner import (
    STAGE8_OPENSCORE_MINING_MANIFEST_SCHEMA,
    OpenScoreMiningRunnerError,
    run_openscore_mining_manifest,
)


ENGINE_SHA = "9" * 40
SNAPSHOT_SHA = "91c780acf1502e7b4f745dc100836c501f41d8e3"


def _score_xml(pitches: tuple[tuple[str, int], ...]) -> str:
    notes = []
    for index, (step, octave) in enumerate(pitches):
        chord = "<chord/>" if index else ""
        notes.append(
            f"<note>{chord}<pitch><step>{step}</step><octave>{octave}</octave></pitch>"
            "<duration>4</duration><voice>1</voice><staff>1</staff></note>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<score-partwise version="4.0"><part-list/>'
        '<part id="P1"><measure number="1">'
        '<attributes><divisions>1</divisions><time><beats>4</beats><beat-type>4</beat-type></time></attributes>'
        + "".join(notes)
        + "</measure></part></score-partwise>"
    )


def _write_mxl(mxl_root: Path, *, score_name: str, pitches: tuple[tuple[str, int], ...]) -> dict[str, object]:
    relative = f"scores/Composer/Work/{score_name}.mxl"
    path = mxl_root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    container = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">'
        '<rootfiles><rootfile full-path="score.musicxml" media-type="application/vnd.recordare.musicxml+xml"/>'
        '</rootfiles></container>'
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("score.musicxml", _score_xml(pitches))
    payload = path.read_bytes()
    return {
        "source_id": "openscore-string-quartets",
        "snapshot_commit_sha": SNAPSHOT_SHA,
        "score_relative_path": f"scores/Composer/Work/{score_name}.mscx",
        "source_sha256": hashlib.sha256(f"source:{score_name}".encode("utf-8")).hexdigest(),
        "output_relative_path": relative,
        "output_sha256": hashlib.sha256(payload).hexdigest(),
        "output_bytes": len(payload),
        "rootfile_path": "score.musicxml",
        "executable_sha256": "b" * 64,
        "executable_version": "MuseScore-4-test",
        "exit_code": 0,
    }


def _write_manifest(path: Path, items: list[dict[str, object]]) -> str:
    document = {
        "schema": STAGE8_OPENSCORE_MINING_MANIFEST_SCHEMA,
        "version": "0.1",
        "item_count": len(items),
        "items": items,
    }
    payload = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


class Stage8OpenScoreMiningRunnerTests(unittest.TestCase):
    def test_ambiguous_score_emits_metadata_only_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mxl_root = root / "mxl"
            mxl_root.mkdir()
            receipt = _write_mxl(
                mxl_root,
                score_name="sq1",
                pitches=(("C", 4), ("E", 4), ("G", 4), ("A", 4)),
            )
            manifest = root / "manifest.json"
            digest = _write_manifest(manifest, [receipt])
            output = root / "candidates.jsonl"

            summary = run_openscore_mining_manifest(
                manifest_path=str(manifest.resolve()),
                expected_manifest_sha256=digest,
                mxl_root=str(mxl_root.resolve()),
                deterministic_engine_sha=ENGINE_SHA,
                output_jsonl=str(output.resolve()),
            )

            lines = output.read_text(encoding="utf-8").splitlines()
            self.assertEqual(summary.source_item_count, 1)
            self.assertEqual(summary.harmonic_frame_count, 1)
            self.assertEqual(summary.ambiguous_candidate_count, 1)
            self.assertEqual(len(lines), 2)
            header = json.loads(lines[0])
            candidate = json.loads(lines[1])
            self.assertEqual(header["record_type"], "run")
            self.assertEqual(header["ambiguous_candidate_count"], 1)
            self.assertFalse(header["model_training_authorized"])
            self.assertFalse(header["production_authority_granted"])
            self.assertEqual(candidate["record_type"], "candidate")
            self.assertEqual(
                candidate["candidate_ids"],
                ["pc:0:basic:major_sixth", "pc:9:basic:minor_seventh"],
            )
            self.assertIsNone(candidate["preferred_candidate_id"])
            self.assertEqual(candidate["annotation_status"], "draft")
            self.assertFalse(candidate["model_training_authorized"])
            self.assertFalse(candidate["production_authority_granted"])
            raw = output.read_bytes()
            self.assertNotIn(b"midi_pitch", raw)
            self.assertNotIn(b"written_pitch", raw)
            self.assertNotIn(b"score-partwise", raw)

    def test_resolved_score_produces_header_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mxl_root = root / "mxl"
            mxl_root.mkdir()
            receipt = _write_mxl(
                mxl_root,
                score_name="sq1",
                pitches=(("C", 4), ("E", 4), ("G", 4)),
            )
            manifest = root / "manifest.json"
            digest = _write_manifest(manifest, [receipt])
            output = root / "candidates.jsonl"
            summary = run_openscore_mining_manifest(
                manifest_path=str(manifest.resolve()),
                expected_manifest_sha256=digest,
                mxl_root=str(mxl_root.resolve()),
                deterministic_engine_sha=ENGINE_SHA,
                output_jsonl=str(output.resolve()),
            )
            self.assertEqual(summary.ambiguous_candidate_count, 0)
            self.assertEqual(len(output.read_text(encoding="utf-8").splitlines()), 1)

    def test_repeat_runs_to_distinct_outputs_are_byte_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mxl_root = root / "mxl"
            mxl_root.mkdir()
            receipt = _write_mxl(
                mxl_root,
                score_name="sq1",
                pitches=(("C", 4), ("E", 4), ("G", 4), ("A", 4)),
            )
            manifest = root / "manifest.json"
            digest = _write_manifest(manifest, [receipt])
            outputs = [root / "first.jsonl", root / "second.jsonl"]
            summaries = []
            for output in outputs:
                summaries.append(
                    run_openscore_mining_manifest(
                        manifest_path=str(manifest.resolve()),
                        expected_manifest_sha256=digest,
                        mxl_root=str(mxl_root.resolve()),
                        deterministic_engine_sha=ENGINE_SHA,
                        output_jsonl=str(output.resolve()),
                    )
                )
            self.assertEqual(outputs[0].read_bytes(), outputs[1].read_bytes())
            self.assertEqual(summaries[0].output_sha256, summaries[1].output_sha256)
            self.assertEqual(summaries[0].candidate_pool_sha256, summaries[1].candidate_pool_sha256)

    def test_wrong_manifest_digest_fails_closed_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mxl_root = root / "mxl"
            mxl_root.mkdir()
            receipt = _write_mxl(mxl_root, score_name="sq1", pitches=(("C", 4), ("E", 4), ("G", 4)))
            manifest = root / "manifest.json"
            _write_manifest(manifest, [receipt])
            output = root / "result.jsonl"
            with self.assertRaises(OpenScoreMiningRunnerError):
                run_openscore_mining_manifest(
                    manifest_path=str(manifest.resolve()),
                    expected_manifest_sha256="0" * 64,
                    mxl_root=str(mxl_root.resolve()),
                    deterministic_engine_sha=ENGINE_SHA,
                    output_jsonl=str(output.resolve()),
                )
            self.assertFalse(output.exists())

    def test_snapshot_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mxl_root = root / "mxl"
            mxl_root.mkdir()
            receipt = _write_mxl(mxl_root, score_name="sq1", pitches=(("C", 4), ("E", 4), ("G", 4)))
            receipt["snapshot_commit_sha"] = "0" * 40
            manifest = root / "manifest.json"
            digest = _write_manifest(manifest, [receipt])
            with self.assertRaises(OpenScoreMiningRunnerError):
                run_openscore_mining_manifest(
                    manifest_path=str(manifest.resolve()),
                    expected_manifest_sha256=digest,
                    mxl_root=str(mxl_root.resolve()),
                    deterministic_engine_sha=ENGINE_SHA,
                    output_jsonl=str((root / "result.jsonl").resolve()),
                )

    def test_output_path_mismatch_and_traversal_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mxl_root = root / "mxl"
            mxl_root.mkdir()
            receipt = _write_mxl(mxl_root, score_name="sq1", pitches=(("C", 4), ("E", 4), ("G", 4)))
            receipt["output_relative_path"] = "scores/Composer/Other/sq1.mxl"
            manifest = root / "manifest.json"
            digest = _write_manifest(manifest, [receipt])
            with self.assertRaises(OpenScoreMiningRunnerError):
                run_openscore_mining_manifest(
                    manifest_path=str(manifest.resolve()),
                    expected_manifest_sha256=digest,
                    mxl_root=str(mxl_root.resolve()),
                    deterministic_engine_sha=ENGINE_SHA,
                    output_jsonl=str((root / "result.jsonl").resolve()),
                )

    def test_container_rootfile_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mxl_root = root / "mxl"
            mxl_root.mkdir()
            receipt = _write_mxl(mxl_root, score_name="sq1", pitches=(("C", 4), ("E", 4), ("G", 4)))
            receipt["rootfile_path"] = "other.musicxml"
            manifest = root / "manifest.json"
            digest = _write_manifest(manifest, [receipt])
            with self.assertRaises(OpenScoreMiningRunnerError):
                run_openscore_mining_manifest(
                    manifest_path=str(manifest.resolve()),
                    expected_manifest_sha256=digest,
                    mxl_root=str(mxl_root.resolve()),
                    deterministic_engine_sha=ENGINE_SHA,
                    output_jsonl=str((root / "result.jsonl").resolve()),
                )

    def test_runner_refuses_to_overwrite_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mxl_root = root / "mxl"
            mxl_root.mkdir()
            receipt = _write_mxl(mxl_root, score_name="sq1", pitches=(("C", 4), ("E", 4), ("G", 4)))
            manifest = root / "manifest.json"
            digest = _write_manifest(manifest, [receipt])
            output = root / "result.jsonl"
            output.write_text("existing", encoding="utf-8")
            with self.assertRaises(OpenScoreMiningRunnerError):
                run_openscore_mining_manifest(
                    manifest_path=str(manifest.resolve()),
                    expected_manifest_sha256=digest,
                    mxl_root=str(mxl_root.resolve()),
                    deterministic_engine_sha=ENGINE_SHA,
                    output_jsonl=str(output.resolve()),
                )
            self.assertEqual(output.read_text(encoding="utf-8"), "existing")

    def test_duplicate_source_score_entries_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mxl_root = root / "mxl"
            mxl_root.mkdir()
            receipt = _write_mxl(mxl_root, score_name="sq1", pitches=(("C", 4), ("E", 4), ("G", 4)))
            manifest = root / "manifest.json"
            digest = _write_manifest(manifest, [receipt, dict(receipt)])
            with self.assertRaises(OpenScoreMiningRunnerError):
                run_openscore_mining_manifest(
                    manifest_path=str(manifest.resolve()),
                    expected_manifest_sha256=digest,
                    mxl_root=str(mxl_root.resolve()),
                    deterministic_engine_sha=ENGINE_SHA,
                    output_jsonl=str((root / "result.jsonl").resolve()),
                )


if __name__ == "__main__":
    unittest.main()
