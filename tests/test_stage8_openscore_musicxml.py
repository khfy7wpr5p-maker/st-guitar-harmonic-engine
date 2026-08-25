import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile

from st_guitar_harmonic_engine.models import TieState
from st_guitar_harmonic_engine.stage8_openscore_conversion import OpenScoreConversionReceipt
from st_guitar_harmonic_engine.stage8_openscore_musicxml import OpenScoreMusicXMLError, parse_openscore_mxl


SOURCE_SHA = "a" * 64
SNAPSHOT_SHA = "91c780acf1502e7b4f745dc100836c501f41d8e3"


def _write_mxl(path: Path, musicxml: str) -> OpenScoreConversionReceipt:
    container = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">'
        '<rootfiles><rootfile full-path="score.musicxml" media-type="application/vnd.recordare.musicxml+xml"/>'
        '</rootfiles></container>'
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("score.musicxml", musicxml)
    payload = path.read_bytes()
    return OpenScoreConversionReceipt(
        source_id="openscore-string-quartets",
        snapshot_commit_sha=SNAPSHOT_SHA,
        score_relative_path="scores/Composer/Work/sq1.mscx",
        source_sha256=SOURCE_SHA,
        output_relative_path="scores/Composer/Work/sq1.mxl",
        output_sha256=hashlib.sha256(payload).hexdigest(),
        output_bytes=len(payload),
        rootfile_path="score.musicxml",
        executable_sha256="b" * 64,
        executable_version="MuseScore-4-test",
        exit_code=0,
    )


def _score(body: str, *, part_id: str = "P1") -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?><score-partwise version="4.0"><part-list/>'
        f'<part id="{part_id}">{body}</part></score-partwise>'
    )


def _attributes(*, transpose: str = "") -> str:
    return (
        "<attributes><divisions>1</divisions>"
        "<time><beats>4</beats><beat-type>4</beat-type></time>"
        f"{transpose}</attributes>"
    )


def _note(step: str, octave: int, duration: int = 4, *, chord: bool = False, alter: str | None = None, extra: str = "") -> str:
    alter_xml = f"<alter>{alter}</alter>" if alter is not None else ""
    chord_xml = "<chord/>" if chord else ""
    return (
        f"<note>{chord_xml}<pitch><step>{step}</step>{alter_xml}<octave>{octave}</octave></pitch>"
        f"<duration>{duration}</duration><voice>1</voice><staff>1</staff>{extra}</note>"
    )


class Stage8OpenScoreMusicXMLTests(unittest.TestCase):
    def test_parses_simultaneous_chord_into_existing_symbolic_contracts(self):
        xml = _score(
            '<measure number="1">'
            + _attributes()
            + _note("C", 4)
            + _note("E", 4, chord=True)
            + _note("G", 4, chord=True)
            + _note("A", 4, chord=True)
            + "</measure>"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "score.mxl"
            receipt = _write_mxl(path, xml)
            parsed = parse_openscore_mxl(str(path.resolve()), receipt)
        self.assertEqual(parsed.part_count, 1)
        self.assertEqual(parsed.source_measure_labels, ("1",))
        measure = parsed.measures[0]
        self.assertEqual(measure.number, 1)
        self.assertEqual(measure.actual_duration.fraction, 4)
        self.assertEqual([event.midi_pitch for event in measure.events], [60, 64, 67, 69])
        self.assertEqual([event.written_pitch.name for event in measure.events], ["C4", "E4", "G4", "A4"])
        self.assertEqual({event.onset.fraction for event in measure.events}, {0})
        self.assertFalse(parsed.model_training_authorized)
        self.assertFalse(parsed.production_authority_granted)

    def test_transpose_octave_change_changes_sounding_midi_not_written_pitch(self):
        transpose = "<transpose><chromatic>0</chromatic><octave-change>-1</octave-change></transpose>"
        xml = _score('<measure number="1">' + _attributes(transpose=transpose) + _note("C", 4) + "</measure>")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "score.mxl"
            receipt = _write_mxl(path, xml)
            parsed = parse_openscore_mxl(str(path.resolve()), receipt)
        event = parsed.measures[0].events[0]
        self.assertEqual(event.midi_pitch, 48)
        self.assertEqual(event.written_pitch.name, "C4")

    def test_multiple_parts_and_staves_get_stable_global_staff_numbers(self):
        part1 = '<part id="P1"><measure number="1">' + _attributes() + _note("G", 3) + "</measure></part>"
        part2_notes = (
            '<note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration><voice>1</voice><staff>1</staff></note>'
            '<backup><duration>4</duration></backup>'
            '<note><pitch><step>C</step><octave>3</octave></pitch><duration>4</duration><voice>2</voice><staff>2</staff></note>'
        )
        part2 = '<part id="P2"><measure number="1">' + _attributes() + part2_notes + "</measure></part>"
        xml = '<?xml version="1.0"?><score-partwise version="4.0"><part-list/>' + part1 + part2 + "</score-partwise>"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "score.mxl"
            receipt = _write_mxl(path, xml)
            parsed = parse_openscore_mxl(str(path.resolve()), receipt)
        self.assertEqual(parsed.part_count, 2)
        self.assertEqual({event.staff for event in parsed.measures[0].events}, {1, 17, 18})

    def test_tie_start_and_stop_maps_to_continue(self):
        xml = _score(
            '<measure number="1">' + _attributes() + _note("C", 4, extra='<tie type="start"/><tie type="stop"/>') + "</measure>"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "score.mxl"
            receipt = _write_mxl(path, xml)
            parsed = parse_openscore_mxl(str(path.resolve()), receipt)
        self.assertIs(parsed.measures[0].events[0].tie, TieState.CONTINUE)

    def test_short_pickup_preserves_actual_duration(self):
        xml = _score('<measure number="0" implicit="yes">' + _attributes() + _note("C", 4, duration=1) + "</measure>")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "score.mxl"
            receipt = _write_mxl(path, xml)
            parsed = parse_openscore_mxl(str(path.resolve()), receipt)
        self.assertEqual(parsed.source_measure_labels, ("0",))
        self.assertEqual(parsed.measures[0].actual_duration.fraction, 1)

    def test_hash_tamper_fails_closed(self):
        xml = _score('<measure number="1">' + _attributes() + _note("C", 4) + "</measure>")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "score.mxl"
            receipt = _write_mxl(path, xml)
            with path.open("ab") as handle:
                handle.write(b"tamper")
            with self.assertRaisesRegex(OpenScoreMusicXMLError, "byte size"):
                parse_openscore_mxl(str(path.resolve()), receipt)

    def test_doctype_declaration_is_rejected(self):
        xml = '<!DOCTYPE score-partwise>' + _score('<measure number="1">' + _attributes() + _note("C", 4) + "</measure>")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "score.mxl"
            receipt = _write_mxl(path, xml)
            with self.assertRaisesRegex(OpenScoreMusicXMLError, "DOCTYPE is not approved"):
                parse_openscore_mxl(str(path.resolve()), receipt)

    def test_microtonal_alter_is_rejected_in_v0_1(self):
        xml = _score('<measure number="1">' + _attributes() + _note("C", 4, alter="0.5") + "</measure>")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "score.mxl"
            receipt = _write_mxl(path, xml)
            with self.assertRaisesRegex(OpenScoreMusicXMLError, "microtonal"):
                parse_openscore_mxl(str(path.resolve()), receipt)

    def test_backup_before_measure_start_is_rejected(self):
        xml = _score(
            '<measure number="1">' + _attributes() + '<backup><duration>1</duration></backup>' + _note("C", 4) + "</measure>"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "score.mxl"
            receipt = _write_mxl(path, xml)
            with self.assertRaisesRegex(OpenScoreMusicXMLError, "before measure start"):
                parse_openscore_mxl(str(path.resolve()), receipt)

    def test_part_measure_label_misalignment_is_rejected(self):
        part1 = '<part id="P1"><measure number="1">' + _attributes() + _note("C", 4) + "</measure></part>"
        part2 = '<part id="P2"><measure number="2">' + _attributes() + _note("E", 4) + "</measure></part>"
        xml = '<?xml version="1.0"?><score-partwise version="4.0"><part-list/>' + part1 + part2 + "</score-partwise>"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "score.mxl"
            receipt = _write_mxl(path, xml)
            with self.assertRaisesRegex(OpenScoreMusicXMLError, "labels are misaligned"):
                parse_openscore_mxl(str(path.resolve()), receipt)


if __name__ == "__main__":
    unittest.main()
