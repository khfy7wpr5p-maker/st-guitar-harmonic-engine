import unittest

from st_guitar_harmonic_engine.explainability_schema import EXPLAINABILITY_SCHEMA_VERSION
from st_guitar_harmonic_engine.public_api import (
    PUBLIC_API_SCHEMA_VERSION,
    PUBLIC_RESULT_SCHEMA_VERSION,
)


class PublicApiCompatibilityTests(unittest.TestCase):
    def test_public_api_is_additive_and_does_not_replace_explainability_v1(self):
        self.assertTrue(EXPLAINABILITY_SCHEMA_VERSION.startswith("1."))
        self.assertEqual(PUBLIC_API_SCHEMA_VERSION, "1.0")
        self.assertEqual(PUBLIC_RESULT_SCHEMA_VERSION, "1.0")


if __name__ == "__main__":
    unittest.main()
