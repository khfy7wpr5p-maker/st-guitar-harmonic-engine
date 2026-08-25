import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from st_guitar_harmonic_engine.stage8_openscore_conversion import (
    MuseScoreBinaryIdentity,
    OpenScoreConversionError,
    OpenScoreConversionRequest,
    execute_musescore_conversion,
)


STRING_QUARTETS_SHA = "91c780acf1502e7b4f745dc100836c501f41d8e3"
SCORE_RELATIVE = "scores/Composer/Work/sq123.mscx"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_valid_mxl(path: Path) -> None:
    container = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">'
        '<rootfiles><rootfile full-path="score.musicxml" media-type="application/vnd.recordare.musicxml+xml"/>'
        '</rootfiles></container>'
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("score.musicxml", "<score-partwise version=\"4.0\"></score-partwise>")


class _Workspace:
    def __init__(self, root: str):
        self.root = Path(root)
        self.input_root = self.root / "input"
        self.output_root = self.root / "output"
        self.input_root.mkdir()
        self.output_root.mkdir()
        self.source = self.input_root / SCORE_RELATIVE
        self.source.parent.mkdir(parents=True)
        self.source.write_text("<museScore version=\"4.0\"/>", encoding="utf-8")
        self.binary_path = Path(sys.executable).resolve()
        self.binary = MuseScoreBinaryIdentity(
            executable_path=str(self.binary_path),
            executable_sha256=_sha256(self.binary_path),
            version_text="MuseScore-4-test",
        )

    def request(self, **overrides):
        values = {
            "source_id": "openscore-string-quartets",
            "snapshot_commit_sha": STRING_QUARTETS_SHA,
            "input_root": str(self.input_root.resolve()),
            "output_root": str(self.output_root.resolve()),
            "score_relative_path": SCORE_RELATIVE,
            "source_sha256": _sha256(self.source),
            "binary": self.binary,
        }
        values.update(overrides)
        return OpenScoreConversionRequest(**values)


class Stage8OpenScoreConversionTests(unittest.TestCase):
    def test_valid_conversion_returns_integrity_receipt_without_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _Workspace(tmp)
            observed = {}

            def runner(args, **kwargs):
                observed["args"] = args
                observed["kwargs"] = kwargs
                _write_valid_mxl(Path(args[2]))
                return subprocess.CompletedProcess(args, 0, b"", b"")

            receipt = execute_musescore_conversion(workspace.request(), runner=runner)
            self.assertEqual(receipt.source_id, "openscore-string-quartets")
            self.assertEqual(receipt.score_relative_path, SCORE_RELATIVE)
            self.assertEqual(receipt.output_relative_path, "scores/Composer/Work/sq123.mxl")
            self.assertEqual(receipt.rootfile_path, "score.musicxml")
            self.assertEqual(receipt.source_sha256, _sha256(workspace.source))
            self.assertGreater(receipt.output_bytes, 0)
            self.assertFalse(receipt.model_training_authorized)
            self.assertFalse(receipt.production_authority_granted)
            self.assertIs(observed["kwargs"]["shell"], False)
            self.assertEqual(observed["args"][1], "-o")

    def test_source_hash_mismatch_fails_before_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _Workspace(tmp)
            called = False

            def runner(args, **kwargs):
                nonlocal called
                called = True
                return subprocess.CompletedProcess(args, 0, b"", b"")

            with self.assertRaisesRegex(OpenScoreConversionError, "source score SHA-256 mismatch"):
                execute_musescore_conversion(
                    workspace.request(source_sha256="0" * 64),
                    runner=runner,
                )
            self.assertFalse(called)

    def test_wrong_snapshot_commit_is_rejected_at_request_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _Workspace(tmp)
            with self.assertRaisesRegex(ValueError, "snapshot_commit_sha"):
                workspace.request(snapshot_commit_sha="a" * 40)

    def test_path_traversal_is_rejected_at_request_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _Workspace(tmp)
            with self.assertRaises(ValueError):
                workspace.request(score_relative_path="scores/../secret.mscx")

    def test_binary_hash_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _Workspace(tmp)
            bad_binary = MuseScoreBinaryIdentity(
                executable_path=str(workspace.binary_path),
                executable_sha256="0" * 64,
                version_text="MuseScore-4-test",
            )
            with self.assertRaisesRegex(OpenScoreConversionError, "executable SHA-256 mismatch"):
                execute_musescore_conversion(workspace.request(binary=bad_binary))

    def test_nonzero_exit_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _Workspace(tmp)

            def runner(args, **kwargs):
                return subprocess.CompletedProcess(args, 2, b"", b"failure")

            with self.assertRaisesRegex(OpenScoreConversionError, "exited non-zero"):
                execute_musescore_conversion(workspace.request(), runner=runner)

    def test_success_without_output_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _Workspace(tmp)

            def runner(args, **kwargs):
                return subprocess.CompletedProcess(args, 0, b"", b"")

            with self.assertRaisesRegex(OpenScoreConversionError, "without output"):
                execute_musescore_conversion(workspace.request(), runner=runner)

    def test_invalid_mxl_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _Workspace(tmp)

            def runner(args, **kwargs):
                Path(args[2]).write_bytes(b"not-a-zip")
                return subprocess.CompletedProcess(args, 0, b"", b"")

            with self.assertRaisesRegex(OpenScoreConversionError, "not a valid MXL"):
                execute_musescore_conversion(workspace.request(), runner=runner)

    def test_archive_path_traversal_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _Workspace(tmp)

            def runner(args, **kwargs):
                output = Path(args[2])
                with zipfile.ZipFile(output, "w") as archive:
                    archive.writestr("../escape", b"x")
                    archive.writestr(
                        "META-INF/container.xml",
                        '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                        '<rootfile full-path="score.musicxml"/></rootfiles></container>',
                    )
                    archive.writestr("score.musicxml", "<score-partwise/>")
                return subprocess.CompletedProcess(args, 0, b"", b"")

            with self.assertRaisesRegex(OpenScoreConversionError, "archive member path is unsafe"):
                execute_musescore_conversion(workspace.request(), runner=runner)

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _Workspace(tmp)
            output = workspace.output_root / "scores/Composer/Work/sq123.mxl"
            output.parent.mkdir(parents=True)
            output.write_bytes(b"existing")
            with self.assertRaisesRegex(OpenScoreConversionError, "refuses to overwrite"):
                execute_musescore_conversion(workspace.request())


if __name__ == "__main__":
    unittest.main()
