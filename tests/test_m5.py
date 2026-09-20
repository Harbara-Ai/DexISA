import unittest
from test_m4 import grasp_setup
from dex_hand.core.types import PINCH_GROUPS
from dex_hand.modes.maintain_grasp import MaintainGrasp
from dex_hand.sim.perturbation import MujocoPerturbation


class ModeTests(unittest.TestCase):
    def test_runs_without_polling(self):
        a=grasp_setup()
        mode=MaintainGrasp(a)
        self.assertTrue(mode.enter("target",PINCH_GROUPS).success)
        a.step(500)
        self.assertAlmostEqual(mode.elapsed,1.,places=5)
        self.assertTrue(mode.active,mode.query())
        probe=MujocoPerturbation(a)
        probe.set_wrench(force=(4,0,0))
        a.step(500)
        probe.clear()
        self.assertEqual(mode.health,"CRITICAL",mode.query())
        self.assertFalse(mode.active)
        self.assertIsNotNone(mode.event["failure_class"])
