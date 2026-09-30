import unittest
from dex_hand.adapters import create_adapter
from dex_hand.sim.worlds import WorldConfig
from dex_hand.core.types import PRESS_GROUPS as G
from dex_hand.skills.shape_hand import ShapeHand
from dex_hand.skills.make_contact import MakeContact
from dex_hand.skills.apply_wrench import ApplyWrench
from dex_hand.skills.break_contact import BreakContact


class ButtonTests(unittest.TestCase):
    def test_press_sequence(self):
        a=create_adapter("wuji",config=WorldConfig(kind="button",center=(.025,.065,.24)))
        outcomes=[ShapeHand(a).run("target",G,profile="POINT")]
        self.assertTrue(outcomes[-1].success,outcomes[-1].to_dict())
        outcomes.append(MakeContact(a).run("target",G))
        self.assertTrue(outcomes[-1].success,outcomes[-1].to_dict())
        outcomes.append(ApplyWrench(a).run("target",G))
        self.assertTrue(outcomes[-1].success,outcomes[-1].to_dict())
        self.assertTrue(a.build_canonical_observation().objects["target"].activated.value)
        out=BreakContact(a).run("target",G,support_state="FIXTURE",retreat=.02)
        self.assertTrue(out.success,out.to_dict())

    def test_requires_contact(self):
        a=create_adapter("wuji",config=WorldConfig(kind="button"))
        out=ApplyWrench(a).run("target",G)
        self.assertEqual(out.failure_class,"PRECONDITION_FAILED")
        self.assertEqual(a.data.time,0.)
