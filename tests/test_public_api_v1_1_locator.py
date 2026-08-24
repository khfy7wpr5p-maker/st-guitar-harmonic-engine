import unittest

from st_guitar_harmonic_engine.public_api import PUBLIC_API_SCHEMA_NAME
from st_guitar_harmonic_engine.public_api_v1_1 import (
    PUBLIC_API_SCHEMA_VERSION_V1_1,
    validate_public_request_v1_1,
)


def beat(value):
    return {"numerator": value, "denominator": 1}


def event(pitch, voice, step):
    return {
        "staff": 1,
        "voice": voice,
        "midi_pitch": pitch,
        "onset": beat(0),
        "duration": beat(1),
        "tie": "none",
        "written_pitch": {"step": step, "alter": 0, "octave": 4},
    }


def frame(events):
    return {
        "measure_number": 1,
        "start": beat(0),
        "end": beat(1),
        "events": events,
    }


class PublicApiV11LocatorTests(unittest.TestCase):
    def test_distinct_same_boundary_frames_may_share_an_event_without_locator_collision(self):
        shared_left = event(60, 1, "C")
        shared_right = event(60, 1, "C")
        payload = {
            "schema_name": PUBLIC_API_SCHEMA_NAME,
            "schema_version": PUBLIC_API_SCHEMA_VERSION_V1_1,
            "mode": "batch",
            "frames": [
                frame([shared_left, event(64, 2, "E")]),
                frame([shared_right, event(67, 3, "G")]),
            ],
            "phrase_spans": None,
        }
        validated = validate_public_request_v1_1(payload)
        self.assertEqual(len(validated.frames), 2)
        self.assertEqual(
            tuple(
                tuple(item.written_pitch.name for item in current.events)
                for current in validated.frames
            ),
            (("C4", "E4"), ("C4", "G4")),
        )


if __name__ == "__main__":
    unittest.main()
