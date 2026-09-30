import unittest
import numpy as np
import mujoco
from dex_hand.adapters import create_adapter
from dex_hand.adapters.transport_mujoco import TransportAdapter
from dex_hand.sim.worlds import WorldConfig
from dex_hand.sim.palm_transport import PalmTransportController


class TransportTests(unittest.TestCase):
    def test_body_origin_relative_velocity_matches_kinematics(self):
        a=TransportAdapter('wuji',WorldConfig())
        a.data.qvel[a.transport_dofs]=[.03,-.01,.02]
        mujoco.mj_forward(a.model,a.data)
        before=np.array(a.build_canonical_observation().objects['target'].relative_pose.value.position)
        observed=a.build_canonical_observation().objects['target'].relative_velocity.value
        eps=1e-6
        mujoco.mj_integratePos(a.model,a.data.qpos,a.data.qvel,eps)
        mujoco.mj_forward(a.model,a.data)
        after=np.array(a.build_canonical_observation().objects['target'].relative_pose.value.position)
        np.testing.assert_allclose((after-before)/eps,observed['linear'],atol=1e-8)
        np.testing.assert_allclose(observed['linear'],[-.03,.01,-.02],atol=1e-10)

    def test_physical_hand_properties_and_mounts_preserved(self):
        for hand in ('wuji','sharpa'):
            base=create_adapter(hand);a=TransportAdapter(hand,WorldConfig())
            np.testing.assert_array_equal(base.model.actuator_forcerange,a.model.actuator_forcerange)
            np.testing.assert_array_equal(base.get_joint_positions(),a.get_joint_positions())
            np.testing.assert_allclose(base.data.xpos[base.palm_id],a.data.xpos[a.palm_id])
            self.assertEqual(a.model.neq,base.model.neq)  # no weld or new constraints
            for i in range(base.model.ngeom):
                name=base.model.geom(i).name
                if not name:continue
                j=a.model.geom(name).id
                np.testing.assert_array_equal(base.model.geom_size[i],a.model.geom_size[j])
                self.assertEqual(base.model.geom_contype[i],a.model.geom_contype[j])
                self.assertEqual(base.model.geom_conaffinity[i],a.model.geom_conaffinity[j])
            self.assertEqual(a.model.body_mass[a.object_id],.06)

    def test_trajectory_bounds_and_no_teleport(self):
        # Only simulation step changes measured qpos; command generation cannot.
        class Mock:
            dt=.002
            def __init__(self):
                self.wrist_target=np.zeros(3);self.wrist_velocity=np.zeros(3)
                self.transport_qids=np.arange(3)
                self.data=type('Data',(),{'qpos':np.zeros(3)})()
                self.samples=[]
            def step(self):
                if self.samples:np.testing.assert_array_equal(self.data.qpos,self.samples[-1][0])
                self.samples.append((self.wrist_target.copy(),self.wrist_velocity.copy()))
                self.data.qpos[:]=self.wrist_target
        a=Mock();c=PalmTransportController(a)
        self.assertEqual(c.move_linear((.1,0,0),.02,.05),'REACHED')
        positions=np.array([x[0] for x in a.samples]);velocities=np.array([x[1] for x in a.samples])
        self.assertLessEqual(np.max(np.linalg.norm(np.diff(positions,axis=0),axis=1)),.02*a.dt+1e-10)
        self.assertLessEqual(np.max(np.linalg.norm(np.diff(velocities,axis=0),axis=1))/a.dt,.05+1e-10)
        np.testing.assert_allclose(positions[-1],[.1,0,0])

    def test_support_detector_includes_other_environment(self):
        a=TransportAdapter('wuji',WorldConfig())
        # Diagnostic fixture positioning in a unit test, never part of task motion.
        q=a.model.jnt_qposadr[a.model.joint('object_free').id]
        a.data.qpos[q:q+3]=[.5,.5,.04+.0125-.0001]
        mujoco.mj_forward(a.model,a.data)
        self.assertTrue(any(c['geom']=='floor' for c in a.support_contacts()))
        self.assertTrue(a.build_canonical_observation().objects['target'].support.value)
