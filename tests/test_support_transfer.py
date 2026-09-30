import unittest
import numpy as np
import mujoco
from dex_hand.sim.support_transfer import FixedPalmSupportAdapter
from dex_hand.sim.worlds import WorldConfig


class SupportTransferTests(unittest.TestCase):
    def test_oracle_is_read_only_and_force_balance_closes(self):
        a=FixedPalmSupportAdapter('wuji',WorldConfig(friction=1.2))
        a.step(50)
        q=a.data.qpos.copy();v=a.data.qvel.copy();warm=a.data.qacc_warmstart.copy();ctrl=a.data.ctrl.copy()
        e=a.evaluation_oracle()
        np.testing.assert_array_equal(q,a.data.qpos);np.testing.assert_array_equal(v,a.data.qvel)
        np.testing.assert_array_equal(warm,a.data.qacc_warmstart);np.testing.assert_array_equal(ctrl,a.data.ctrl)
        self.assertTrue(e['support_contact_present'])
        self.assertAlmostEqual(e['F_hand_z'],0,places=5)
        self.assertAlmostEqual(e['F_support_z'],.5886,delta=.02)
        self.assertLess(abs(e['force_balance_residual_N']),.001)

    def test_support_mapped_as_environment_not_a_finger(self):
        a=FixedPalmSupportAdapter('sharpa',WorldConfig(friction=1.2));a.step(50)
        o=a.build_canonical_observation()
        self.assertTrue(o.objects['target'].support.value)
        self.assertFalse(o.contacts)
        self.assertEqual(o.interaction.object_slip.status,'UNKNOWN')
        self.assertEqual(o.grasp.task_wrench_margin.status,'UNKNOWN')

    def test_support_motion_does_not_move_palm_or_teleport_object(self):
        a=FixedPalmSupportAdapter('wuji',WorldConfig(friction=1.2))
        p=a.data.xpos[a.palm_id].copy();q=a.data.qpos.copy()
        profile=a.support.profile(.001)
        next(profile)
        np.testing.assert_array_equal(q,a.data.qpos) # command alone never edits qpos
        for _ in profile:
            a.step()
            np.testing.assert_array_equal(p,a.data.xpos[a.palm_id])
        self.assertLess(a.data.geom_xpos[a.support.geom,2],.2375-.0009)
