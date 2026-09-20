import unittest
from dex_hand.adapters import create_adapter
from dex_hand.core.types import PINCH_GROUPS
from dex_hand.skills.shape_hand import ShapeHand
from dex_hand.skills.make_contact import MakeContact


class ContactTests(unittest.TestCase):
    def test_guarded_contact(self):
        a=create_adapter("wuji")
        first=ShapeHand(a).run("target",PINCH_GROUPS)
        self.assertTrue(first.success,first.to_dict())
        out=MakeContact(a).run("target",PINCH_GROUPS)
        self.assertTrue(out.success,out.to_dict())
        self.assertGreater(len(a.build_canonical_observation().contacts),0)
