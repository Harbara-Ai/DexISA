import unittest
from dex_hand.adapters import create_adapter
from dex_hand.core.types import PINCH_GROUPS
from dex_hand.skills.shape_hand import ShapeHand
from dex_hand.skills.make_contact import MakeContact
from dex_hand.skills.establish_grasp import EstablishGrasp
from dex_hand.sim.perturbation import MujocoPerturbation


def grasp_setup():
    a=create_adapter("wuji")
    for skill in (ShapeHand(a),MakeContact(a),EstablishGrasp(a,MujocoPerturbation(a))):
        out=skill.run("target",PINCH_GROUPS)
        if not out.success: raise AssertionError(out.to_dict())
    return a


class GraspTests(unittest.TestCase):
    def test_baseline_stability(self):
        a=grasp_setup()
        self.assertTrue(a.grasp_verified)
        self.assertIsNone(a.build_canonical_observation().grasp.task_wrench_margin.value)
