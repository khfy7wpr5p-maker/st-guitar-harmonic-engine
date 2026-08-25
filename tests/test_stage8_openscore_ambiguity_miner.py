import unittest

from st_guitar_harmonic_engine.models import Measure, NoteEvent, RationalBeat, TimeSignature
from st_guitar_harmonic_engine.spelling import PitchStep, WrittenPitch
from st_guitar_harmonic_engine.stage8_openscore_ambiguity_miner import mine_openscore_ambiguities
from st_guitar_harmonic_engine.stage8_openscore_musicxml import ParsedOpenScoreScore


ENGINE_SHA = "9" * 40
SOURCE_SHA = "a" * 64
MXL_SHA = "b" * 64
SNAPSHOT_SHA = "91c780acf1502e7b4f745dc100836c501f41d8e3"
_PC_TO_WRITTEN = {
    0: (PitchStep.C, 0),
    1: (PitchStep.C, 1),
    2: (PitchStep.D, 0),
    3: (PitchStep.E, -1),
    4: (PitchStep.E, 0),
    5: (PitchStep.F, 0),
    6: (PitchStep.F, 1),
    7: (PitchStep.G, 0),
    8: (PitchStep.A, -1),
    9: (PitchStep.A, 0),
    10: (PitchStep.B, -1),
    11: (PitchStep.B, 0),
}


def _event(measure: int, midi: int, *, duration: int = 4, voice: int = 1) -> NoteEvent:
    pc = midi % 12
    step, alter = _PC_TO_WRITTEN[pc]
    octave = midi // 12 - 1
    return NoteEvent(
        measure_number=measure,
        staff=1,
        voice=voice,
        midi_pitch=midi,
        onset=RationalBeat(0),
        duration=RationalBeat(duration),
        written_pitch=WrittenPitch(step, alter, octave),
    )


def _measure(number: int, pitches: tuple[int, ...]) -> Measure:
    return Measure(
        number=number,
        time_signature=TimeSignature(4, 4),
        events=tuple(_event(number, midi, voice=index + 1) for index, midi in enumerate(pitches)),
        actual_duration=RationalBeat(4),
    )


def _score(measures: tuple[Measure, ...], *, source_id: str = "openscore-string-quartets", path: str = "scores/Composer/Work/sq1.mscx") -> ParsedOpenScoreScore:
    return ParsedOpenScoreScore(
        source_id=source_id,
        snapshot_commit_sha=SNAPSHOT_SHA if source_id == "openscore-string-quartets" else "6b2dc542ce2e8aa4b78c8ee62103b210efc07015",
        score_relative_path=path,
        source_sha256=SOURCE_SHA,
        mxl_sha256=MXL_SHA,
        source_measure_labels=tuple(str(item.number) for item in measures),
        measures=measures,
        part_count=1,
    )


class Stage8OpenScoreAmbiguityMinerTests(unittest.TestCase):
    def test_c6_am7_collision_is_mined_without_preferred_label(self):
        score = _score((_measure(1, (60, 64, 67, 69)),))
        result = mine_openscore_ambiguities(score, deterministic_engine_sha=ENGINE_SHA)
        self.assertEqual(result.harmonic_frame_count, 1)
        self.assertEqual(result.ambiguous_candidate_count, 1)
        candidate = result.candidates[0]
        self.assertEqual(
            candidate.candidate_ids,
            ("pc:0:basic:major_sixth", "pc:9:basic:minor_seventh"),
        )
        self.assertIsNone(candidate.preferred_candidate_id)
        self.assertEqual(candidate.annotation_status, "draft")
        self.assertEqual(candidate.previous_frame_sha256, ())
        self.assertFalse(candidate.model_training_authorized)
        self.assertFalse(candidate.production_authority_granted)

    def test_resolved_major_triad_is_not_mined(self):
        score = _score((_measure(1, (60, 64, 67)),))
        result = mine_openscore_ambiguities(score, deterministic_engine_sha=ENGINE_SHA)
        self.assertEqual(result.harmonic_frame_count, 1)
        self.assertEqual(result.ambiguous_candidate_count, 0)
        self.assertEqual(result.candidates, ())

    def test_weak_incomplete_ambiguity_becomes_abstain_and_is_not_mined(self):
        score = _score((_measure(1, (60, 64)),))
        result = mine_openscore_ambiguities(score, deterministic_engine_sha=ENGINE_SHA)
        self.assertEqual(result.ambiguous_candidate_count, 0)

    def test_previous_context_is_strictly_causal_and_capped_at_four_frames(self):
        resolved = tuple(_measure(index, (60, 64, 67)) for index in range(1, 6))
        ambiguous = _measure(6, (60, 64, 67, 69))
        score = _score(resolved + (ambiguous,))
        result = mine_openscore_ambiguities(score, deterministic_engine_sha=ENGINE_SHA)
        candidate = result.candidates[0]
        self.assertEqual(result.harmonic_frame_count, 6)
        self.assertEqual(len(candidate.previous_frame_sha256), 4)
        self.assertNotIn(candidate.current_frame_sha256, candidate.previous_frame_sha256)

    def test_mining_is_deterministic(self):
        score = _score(
            (
                _measure(1, (60, 64, 67)),
                _measure(2, (60, 64, 67, 69)),
                _measure(3, (62, 66, 69, 71)),
            )
        )
        first = mine_openscore_ambiguities(score, deterministic_engine_sha=ENGINE_SHA)
        second = mine_openscore_ambiguities(score, deterministic_engine_sha=ENGINE_SHA)
        self.assertEqual(first, second)

    def test_engine_sha_is_required_and_validated(self):
        score = _score((_measure(1, (60, 64, 67, 69)),))
        with self.assertRaises(ValueError):
            mine_openscore_ambiguities(score, deterministic_engine_sha="not-a-sha")

    def test_string_quartet_work_path_has_stable_group_identity(self):
        first = _score((_measure(1, (60, 64, 67, 69)),), path="scores/Composer/Quartet/sq1.mscx")
        second = _score((_measure(1, (60, 64, 67, 69)),), path="scores/Composer/Quartet/sq2.mscx")
        first_id = mine_openscore_ambiguities(first, deterministic_engine_sha=ENGINE_SHA).candidates[0].source_group_id
        second_id = mine_openscore_ambiguities(second, deterministic_engine_sha=ENGINE_SHA).candidates[0].source_group_id
        self.assertEqual(first_id, second_id)

    def test_lieder_cycle_groups_different_songs_together(self):
        first = _score(
            (_measure(1, (60, 64, 67, 69)),),
            source_id="openscore-lieder",
            path="scores/Composer/Cycle/01_Song/lc1.mscx",
        )
        second = _score(
            (_measure(1, (60, 64, 67, 69)),),
            source_id="openscore-lieder",
            path="scores/Composer/Cycle/02_Song/lc2.mscx",
        )
        first_id = mine_openscore_ambiguities(first, deterministic_engine_sha=ENGINE_SHA).candidates[0].source_group_id
        second_id = mine_openscore_ambiguities(second, deterministic_engine_sha=ENGINE_SHA).candidates[0].source_group_id
        self.assertEqual(first_id, second_id)

    def test_unapproved_source_id_fails_closed(self):
        score = ParsedOpenScoreScore(
            source_id="other-source",
            snapshot_commit_sha="c" * 40,
            score_relative_path="scores/Composer/Work/x.mscx",
            source_sha256=SOURCE_SHA,
            mxl_sha256=MXL_SHA,
            source_measure_labels=("1",),
            measures=(_measure(1, (60, 64, 67, 69)),),
            part_count=1,
        )
        with self.assertRaises(ValueError):
            mine_openscore_ambiguities(score, deterministic_engine_sha=ENGINE_SHA)


if __name__ == "__main__":
    unittest.main()
