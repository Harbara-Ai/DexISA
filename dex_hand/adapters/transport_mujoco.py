"""Translation-only simulated wrist. No changes to shared hand Skills or modes."""
import xml.etree.ElementTree as ET
import numpy as np
import mujoco
from . import create_adapter
from .mujoco_base import MuJoCoHandAdapter
from dex_hand.core.observation import known, Method


class TransportAdapter(MuJoCoHandAdapter):
    arm_kp=100000.
    arm_kd=800.
    arm_force_cap=100.
    def __init__(self, hand, config, landing_x=.1):
        base = create_adapter(hand, config=config)
        root = ET.fromstring(base.xml)
        world = root.find('worldbody')
        palm_name = base.model.body(base.palm_id).name
        palm = world.find(f"body[@name='{palm_name}']")
        palm_index=list(world).index(palm)
        world.remove(palm)
        carriage = ET.SubElement(world, 'body', name='transport_carriage')
        world.remove(carriage)
        world.insert(palm_index,carriage)
        ET.SubElement(carriage, 'inertial', pos='0 0 0', mass='1', diaginertia='.01 .01 .01')
        for axis, direction in zip('xyz', ('1 0 0', '0 1 0', '0 0 1')):
            ET.SubElement(carriage, 'joint', name='transport_'+axis, type='slide', axis=direction,
                          limited='false', damping='0', armature='0', stiffness='0', frictionloss='0')
        carriage.append(palm)
        if landing_x > 0:
            cx, cy, cz = config.center
            ET.SubElement(world, 'geom', name='landing', type='box', size='.012 .012 .01',
                          pos=f'{cx+landing_x} {cy} {cz-config.height/2-.01}',
                          friction='.4 .005 .0001', rgba='.3 .5 .3 1')
            ET.SubElement(root.find('contact'), 'pair', geom1='target_geom', geom2='landing',
                          condim='3', friction='.4 .4 .005 .0001 .0001')
        xml = ET.tostring(root, encoding='unicode')
        model = mujoco.MjModel.from_xml_string(xml)
        super().__init__(config, (model, xml), base.group_map,
                         {k:base.model.site(v).name for k,v in base.sites.items()},
                         palm_name, base.model_name, base.source)
        self.data.qpos[self.qids] = base.get_joint_positions()
        self.command_joint_targets(self.get_joint_positions())
        self.transport_joints = [model.joint('transport_'+axis).id for axis in 'xyz']
        self.transport_qids = model.jnt_qposadr[self.transport_joints]
        self.transport_dofs = model.jnt_dofadr[self.transport_joints]
        self.wrist_target = np.zeros(3)
        self.wrist_velocity = np.zeros(3)
        self.wrist_command = {'kind':'hold', 'position':[0.,0.,0.], 'velocity':[0.,0.,0.]}
        self.wrist_force = np.zeros(3)
        self.after_step = []
        self.original_hand_force_ranges = base.model.actuator_forcerange.tolist()
        assert np.array_equal(model.actuator_forcerange, base.model.actuator_forcerange)
        mujoco.mj_forward(model,self.data)

    def body_velocity(self, bid):
        jp, jr = np.zeros((3,self.model.nv)), np.zeros((3,self.model.nv))
        mujoco.mj_jacBody(self.model,self.data,jp,jr,bid)
        return jp@self.data.qvel, jr@self.data.qvel

    def build_canonical_observation(self):
        o = super().build_canonical_observation()
        if self.object_id is None:return o
        p, w = self.body_velocity(self.palm_id)
        v, wo = self.body_velocity(self.object_id)
        R = self.data.xmat[self.palm_id].reshape(3,3)
        rel = R.T@(v-p-np.cross(w,self.data.xpos[self.object_id]-self.data.xpos[self.palm_id]))
        angular = R.T@(wo-w)
        o.objects['target'].relative_velocity = known({'frame':'palm','linear':rel.tolist(),
            'angular':angular.tolist()}, o.timestamp, 'SIM_BODY_JACOBIAN', Method.DERIVED)
        loads = [sum(c.normal_load.value for c in o.contacts if c.contact_group_id==g) for g in self.verified_groups]
        within = self.verified_reference is not None and np.linalg.norm(
            np.array(o.objects['target'].relative_pose.value.position)-self.verified_reference)<.008
        stable = self.grasp_verified and bool(loads) and min(loads)>=.15 and within and np.linalg.norm(rel)<.015 and np.linalg.norm(angular)<.5
        o.grasp.state = known('STABLE' if stable else 'MARGINAL' if o.contacts else 'UNSTABLE',
                              o.timestamp,'BASELINE_STATIC_V1',Method.ESTIMATED,.6)
        return o

    def support_contacts(self):
        result=[]
        for i in range(self.data.ncon):
            c=self.data.contact[i]
            if self.object_geom not in (c.geom1,c.geom2):continue
            other=int(c.geom2 if c.geom1==self.object_geom else c.geom1)
            # All benchmark environment geometry belongs to world; hand geometry
            # is articulated under the carriage. Include floor and landing too.
            if self.model.geom_bodyid[other]!=0:continue
            f=np.zeros(6)
            mujoco.mj_contactForce(self.model,self.data,i,f)
            if f[0]>1e-5:result.append({'geom':self.model.geom(other).name,'normal_load':float(f[0]),'position':c.pos.tolist()})
        return result

    def step(self, steps=1):
        for _ in range(steps):
            old=self.data.xpos[self.palm_id].copy()
            # Independent finite-force arm controller; no hand force cap changes.
            q=self.data.qpos[self.transport_qids]
            v=self.data.qvel[self.transport_dofs]
            self.wrist_force=np.clip(self.arm_kp*(self.wrist_target-q)+self.arm_kd*(self.wrist_velocity-v)
                                    +self.data.qfrc_bias[self.transport_dofs],-self.arm_force_cap,self.arm_force_cap)
            self.data.qfrc_applied[self.transport_dofs]=self.wrist_force
            mujoco.mj_step(self.model,self.data)
            mujoco.mj_forward(self.model,self.data)
            shift=self.data.xpos[self.palm_id]-old
            self.group_targets={k:p+shift for k,p in self.group_targets.items()}
            if not np.isfinite(self.data.qpos).all():raise RuntimeError('nonfinite simulation state')
            for callback in tuple(self.callbacks):callback(self.build_canonical_observation())
            for callback in tuple(self.after_step):callback(self.build_canonical_observation())

