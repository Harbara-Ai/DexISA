import unittest
import numpy as np
import mujoco
from dex_hand.sim.worlds import build_world, WorldConfig


class ModelSmoke(unittest.TestCase):
    def test_real_model_stable(self):
        model, _ = build_world(WorldConfig(kind="empty"))
        data = mujoco.MjData(model)
        for _ in range(1000):
            mujoco.mj_step(model, data)
        self.assertEqual(model.nu, 20)
        self.assertTrue(np.isfinite(data.qpos).all())
        self.assertLess(np.max(np.abs(data.qvel)), .1)
        self.assertEqual(sum(w.number for w in data.warning), 0)


if __name__ == "__main__":
    unittest.main()
