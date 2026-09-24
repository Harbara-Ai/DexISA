"""Offline package checks that do not require vendor models or hardware."""
import os
import unittest
from unittest.mock import patch

from dex_hand.adapters import create_adapter
from dex_hand.core.outcome import AdapterError, SkillOutcome
from dex_hand.core.schema import validate_outcome


class DistributionTests(unittest.TestCase):
    def test_missing_external_models_are_explicit(self):
        for hand, variable in (
            ("wuji", "WUJI_MJCF"),
            ("sharpa", "SHARPA_MJCF"),
            ("allegro_v5", "ALLEGRO_V5_MJCF"),
            ("robotiq_2f85", "ROBOTIQ_2F85_MJCF"),
        ):
            with self.subTest(hand=hand), patch.dict(os.environ, {variable: ""}):
                with self.assertRaises((AdapterError, FileNotFoundError)) as raised:
                    create_adapter(hand, backend="mujoco")
                self.assertIn(variable, str(raised.exception))

    def test_packaged_schema_validates_skill_outcome(self):
        validate_outcome(SkillOutcome("SUCCESS", "SHAPE_HAND",
                                      achieved_state={"profile": "PRESHAPE"}))


if __name__ == "__main__":
    unittest.main()
