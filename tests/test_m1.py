import unittest
from dex_hand.adapters.wuji_mujoco import WujiMuJoCoAdapter
from dex_hand.core.observation import ObservedValue, ValueStatus
from dex_hand.sim.worlds import WorldConfig


class ObservationTests(unittest.TestCase):
    def test_unknown_is_not_false(self):
        with self.assertRaises(ValueError): ObservedValue(ValueStatus.UNKNOWN, False)
        with self.assertRaises(ValueError): ObservedValue(ValueStatus.UNAVAILABLE, 0.)

    def test_snapshot_and_capabilities(self):
        a = WujiMuJoCoAdapter(WorldConfig())
        a.step(20)
        o = a.build_canonical_observation()
        self.assertEqual(o.timestamp, a.data.time)
        self.assertIsNone(o.interaction.object_slip.value)
        self.assertIsNone(o.grasp.task_wrench_margin.value)
        self.assertEqual(len(o.hand.joint_position.value),20)
        self.assertEqual(len(a.get_observation_capabilities()),17)
        self.assertEqual(o.objects["target"].relative_pose.value.frame,"palm")
