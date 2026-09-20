import unittest
import numpy as np
from test_m4 import grasp_setup
from dex_hand.core.types import PINCH_GROUPS
from dex_hand.skills.break_contact import BreakContact
from dex_hand.modes.maintain_grasp import MaintainGrasp


class ReleaseTests(unittest.TestCase):
    def test_unsafe_release_rejected_before_motion(self):
        a=grasp_setup()
        time=a.data.time
        command=a.data.ctrl.copy()
        out=BreakContact(a).run("target",PINCH_GROUPS,support_state="NONE")
        self.assertEqual(out.failure_class,"PRECONDITION_FAILED")
        self.assertEqual(a.data.time,time)
        np.testing.assert_array_equal(a.data.ctrl,command)

    def test_controlled_release(self):
        a=grasp_setup()
        mode=MaintainGrasp(a)
        mode.enter("target",PINCH_GROUPS)
        a.step(100)
        out=BreakContact(a).run("target",PINCH_GROUPS)
        self.assertTrue(out.success,out.to_dict())
        self.assertFalse(mode.active)
        self.assertFalse(a.build_canonical_observation().contacts)
