import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile

from st_guitar_harmonic_engine.stage8_openscore_conversion import OpenScoreConversionReceipt
from st_guitar_harmonic_engine.stage8_openscore_musicxml import OpenScoreMusicXMLError, parse_openscore_mxl


SNAPSHOT_SHA = "91c780acf1502e7b4f745dc100836c501f41d8e3"
APPROVED_DOCTYPE = (
    '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" '
    '"http://www.musicxml.org/dtds/partwise.dtd">'
)
BODY = (
    '<score-partwise version="3.1"><part-list/>'
    '<part id="P1"><measure number="1">'
    '<attributes><divisions>1</divisions><time><beats>4</beats><beat-type>4</beat-type></time></attributes>'
    '<note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration><voice>1</voice><staff>1</staff></note>'
    '</measure></part></score-partwise>'
)


def _write_mxl(path: Path, xml: str) -> OpenScoreConversionReceipt:
    container = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<container><rootfiles><rootfile full-path="score.xml"/></rootfiles></container>'
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("score.xml", xml)
    payload = path.read_bytes()
    return OpenScoreConversionReceipt(
        source_id="openscore-string-quartets",
        snapshot_commit_sha=SNAPSHOT_SHA,
        score_relative_path="scores/Composer/Work/sq1.mscx",
        source_sha256="a" * 64,
        output_relative_path="scores/Composer/Work/sq1.mxl",
        output_sha256=hashlib.sha256(payload).hexdigest(),
        output_bytes=len(payload),
        rootfile_path="score.xml",
        executable_sha256="b" * 64,
        executable_version="MuseScore3 3.6.2",
        exit_code=0,
    )


def _parse(xml: str):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "score.mxl"
        receipt = _write_mxl(path, xml)
        return parse_openscore_mxl(str(path.resolve()), receipt)


class Stage8OpenScoreMusicXMLDoctypeCompatTests(unittest.TestCase):
    def test_exact_musescore_musicxml31_doctype_is_accepted(self):
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + APPROVED_DOCTYPE + "\n" + BODY
        parsed = _parse(xml)
        self.assertEqual(parsed.part_count, 1)
        self.assertEqual(len(parsed.measures), 1)
        self.assertEqual(parsed.measures[0].events[0].midi_pitch, 60)
        self.assertFalse(parsed.model_training_authorized)
        self.assertFalse(parsed.production_authority_granted)

    def test_generic_doctype_remains_rejected(self):
        xml = '<!DOCTYPE score-partwise>' + BODY
        with self.assertRaisesRegex(OpenScoreMusicXMLError, "DOCTYPE is not approved"):
            _parse(xml)

    def test_wrong_public_identifier_is_rejected(self):
        xml = (
            '<!DOCTYPE score-partwise PUBLIC "-//Example//DTD MusicXML 3.1 Partwise//EN" '
            '"http://www.musicxml.org/dtds/partwise.dtd">' + BODY
        )
        with self.assertRaisesRegex(OpenScoreMusicXMLError, "DOCTYPE is not approved"):
            _parse(xml)

    def test_wrong_system_url_is_rejected(self):
        xml = (
            '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" '
            '"https://example.invalid/partwise.dtd">' + BODY
        )
        with self.assertRaisesRegex(OpenScoreMusicXMLError, "DOCTYPE is not approved"):
            _parse(xml)

    def test_internal_subset_and_entity_are_rejected(self):
        xml = '<!DOCTYPE score-partwise [<!ENTITY x "boom">]>' + BODY
        with self.assertRaisesRegex(OpenScoreMusicXMLError, "entity declarations are forbidden"):
            _parse(xml)

    def test_duplicate_doctype_is_rejected(self):
        xml = APPROVED_DOCTYPE + APPROVED_DOCTYPE + BODY
        with self.assertRaisesRegex(OpenScoreMusicXMLError, "at most one approved DOCTYPE"):
            _parse(xml)

    def test_doctype_after_unexpected_markup_is_rejected(self):
        xml = '<!--prefix-->' + APPROVED_DOCTYPE + BODY
        with self.assertRaisesRegex(OpenScoreMusicXMLError, "unsafe position"):
            _parse(xml)


if __name__ == "__main__":
    unittest.main()
