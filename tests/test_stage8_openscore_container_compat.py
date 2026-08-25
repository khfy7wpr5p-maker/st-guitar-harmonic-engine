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
    _parse_mxl_container_rootfile,
    execute_musescore_conversion,
)
from st_guitar_harmonic_engine.stage8_openscore_mining_runner import (
    OpenScoreMiningRunnerError,
    _container_rootfile,
)


STRING_QUARTETS_SHA = "91c780acf1502e7b4f745dc100836c501f41d8e3"
SCORE_RELATIVE = "scores/Composer/Work/sq123.mscx"
CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _container(*, namespaced: bool, rootfile: str = "score.musicxml") -> bytes:
    namespace = f' xmlns="{CONTAINER_NS}" version="1.0"' if namespaced else ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<container{namespace}><rootfiles><rootfile full-path="{rootfile}"/></rootfiles></container>'
    ).encode("utf-8")


def _write_mxl(path: Path, *, namespaced: bool) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("META-INF/container.xml", _container(namespaced=namespaced))
        archive.writestr("score.musicxml", '<score-partwise version="4.0"></score-partwise>')


class Stage8OpenScoreContainerCompatibilityTests(unittest.TestCase):
    def test_official_namespaced_container_is_accepted(self):
        self.assertEqual(
            _parse_mxl_container_rootfile(_container(namespaced=True)),
            "score.musicxml",
        )

    def test_musescore_362_namespace_free_container_is_accepted(self):
        payload = b'''<?xml version="1.0" encoding="UTF-8"?>
<container>
  <rootfiles>
    <rootfile full-path="pilot_first_score.xml">
      </rootfile>
    </rootfiles>
  </container>
'''
        self.assertEqual(
            _parse_mxl_container_rootfile(payload),
            "pilot_first_score.xml",
        )

    def test_unknown_container_namespace_fails_closed(self):
        payload = (
            b'<container xmlns="urn:unapproved"><rootfiles>'
            b'<rootfile full-path="score.musicxml"/></rootfiles></container>'
        )
        with self.assertRaisesRegex(OpenScoreConversionError, "namespace is not approved"):
            _parse_mxl_container_rootfile(payload)

    def test_mixed_container_namespace_fails_closed(self):
        payload = (
            f'<container xmlns="{CONTAINER_NS}"><rootfiles xmlns="">'
            '<rootfile full-path="score.musicxml"/></rootfiles></container>'
        ).encode("utf-8")
        with self.assertRaisesRegex(OpenScoreConversionError, "mixes namespaces"):
            _parse_mxl_container_rootfile(payload)

    def test_duplicate_rootfile_fails_closed(self):
        payload = (
            b'<container><rootfiles><rootfile full-path="a.xml"/>'
            b'<rootfile full-path="b.xml"/></rootfiles></container>'
        )
        with self.assertRaisesRegex(OpenScoreConversionError, "exactly one rootfile"):
            _parse_mxl_container_rootfile(payload)

    def test_dtd_or_entity_is_rejected(self):
        payload = (
            b'<!DOCTYPE container [<!ENTITY x "score.musicxml">]>'
            b'<container><rootfiles><rootfile full-path="&x;"/></rootfiles></container>'
        )
        with self.assertRaisesRegex(OpenScoreConversionError, "DTD/entity"):
            _parse_mxl_container_rootfile(payload)

    def test_conversion_receipt_accepts_namespace_free_musescore_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = root / "input"
            output_root = root / "output"
            input_root.mkdir()
            output_root.mkdir()
            source = input_root / SCORE_RELATIVE
            source.parent.mkdir(parents=True)
            source.write_text('<museScore version="3.02"/>', encoding="utf-8")
            binary_path = Path(sys.executable).resolve()
            binary = MuseScoreBinaryIdentity(
                executable_path=str(binary_path),
                executable_sha256=_sha256(binary_path),
                version_text="MuseScore3 3.6.2",
            )
            request = OpenScoreConversionRequest(
                source_id="openscore-string-quartets",
                snapshot_commit_sha=STRING_QUARTETS_SHA,
                input_root=str(input_root.resolve()),
                output_root=str(output_root.resolve()),
                score_relative_path=SCORE_RELATIVE,
                source_sha256=_sha256(source),
                binary=binary,
            )

            def runner(args, **kwargs):
                _write_mxl(Path(args[2]), namespaced=False)
                return subprocess.CompletedProcess(args, 0, b"", b"")

            receipt = execute_musescore_conversion(request, runner=runner)
            self.assertEqual(receipt.rootfile_path, "score.musicxml")
            self.assertFalse(receipt.model_training_authorized)
            self.assertFalse(receipt.production_authority_granted)

    def test_mining_runner_rederives_namespace_free_rootfile(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "score.mxl"
            _write_mxl(path, namespaced=False)
            self.assertEqual(_container_rootfile(path), "score.musicxml")

    def test_mining_runner_wraps_invalid_namespace_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "score.mxl"
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(
                    "META-INF/container.xml",
                    '<container xmlns="urn:unapproved"><rootfiles><rootfile full-path="score.musicxml"/></rootfiles></container>',
                )
                archive.writestr("score.musicxml", "<score-partwise/>")
            with self.assertRaisesRegex(OpenScoreMiningRunnerError, "container.xml is invalid"):
                _container_rootfile(path)


if __name__ == "__main__":
    unittest.main()
