import unittest
from dex_hand.adapters import create_adapter
from dex_hand.core.types import PINCH_GROUPS
from dex_hand.skills.shape_hand import ShapeHand


class ShapeTests(unittest.TestCase):
    def test_preshape(self):
        a=create_adapter("wuji")
        out=ShapeHand(a).run("target",PINCH_GROUPS)
        self.assertTrue(out.success,out.to_dict())
