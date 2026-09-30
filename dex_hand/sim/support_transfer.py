"""Fixed-palm support-removal apparatus; oracle diagnostics never feed Skills."""
import xml.etree.ElementTree as ET
import numpy as np
import mujoco
from dex_hand.adapters import create_adapter
from dex_hand.adapters.mujoco_base import MuJoCoHandAdapter
from dex_hand.core.observation import known, Method


class MovableSupportSurface:
    """One physical slide DOF with finite force servo, no object state edits."""
    speed=.002
    acceleration=.004
    kp=100000.
    kd=800.
    force_cap=100.

    def __init__(self,a):
        self.a=a
        jid=a.model.joint('support_slide').id
        self.qid=int(a.model.jnt_qposadr[jid]);self.dof=int(a.model.jnt_dofadr[jid])
        self.geom=a.model.geom('table').id
        self.body=a.model.body('movable_support').id
        self.target=0.;self.velocity=0.;self.force=0.

    def apply(self):
        a=self.a
        self.force=float(np.clip(self.kp*(self.target-a.data.qpos[self.qid])+
            self.kd*(self.velocity-a.data.qvel[self.dof])+a.data.qfrc_bias[self.dof],-self.force_cap,self.force_cap))
        a.data.qfrc_applied[self.dof]=self.force

    def profile(self,distance=.005):
        # Symmetric trapezoid, 0.5 s acceleration/deceleration at default speed.
        ramp=min(self.speed/self.acceleration,np.sqrt(distance/self.acceleration))
        peak=self.acceleration*ramp;cruise=max(0.,distance/peak-ramp)
        duration=2*ramp+cruise;origin=self.target
        for i in range(1,int(np.ceil(duration/self.a.dt))+1):
            t=min(i*self.a.dt,duration)
            if t<ramp:s=.5*self.acceleration*t*t;v=self.acceleration*t
            elif t<ramp+cruise:s=.5*peak*ramp+peak*(t-ramp);v=peak
            else:left=duration-t;s=distance-.5*self.acceleration*left*left;v=self.acceleration*left
            self.target=origin-s;self.velocity=-v
            yield
        self.velocity=0.


class FixedPalmSupportAdapter(MuJoCoHandAdapter):
    """Same hand model/control observation, with explicit environment mapping."""
    def __init__(self,hand,config):
        base=create_adapter(hand,config=config)
        root=ET.fromstring(base.xml);world=root.find('worldbody')
        table=world.find("geom[@name='table']");pos=table.get('pos');world.remove(table)
        body=ET.SubElement(world,'body',name='movable_support',pos=pos)
        ET.SubElement(body,'inertial',mass='1',pos='0 0 0',diaginertia='.01 .01 .01')
        ET.SubElement(body,'joint',name='support_slide',type='slide',axis='0 0 1',
                      limited='false',damping='0',armature='0',stiffness='0',frictionloss='0')
        table.set('pos','0 0 0');body.append(table)
        xml=ET.tostring(root,encoding='unicode');model=mujoco.MjModel.from_xml_string(xml)
        super().__init__(config,(model,xml),base.group_map,
            {k:base.model.site(v).name for k,v in base.sites.items()},base.model.body(base.palm_id).name,
            base.model_name,base.source)
        self.data.qpos[self.qids]=base.get_joint_positions()
        self.command_joint_targets(self.get_joint_positions())
        self.support=MovableSupportSurface(self);self.after_step=[]
        self.fixed_palm_position=base.data.xpos[base.palm_id].copy()
        self.fixed_palm_quaternion=base.data.xquat[base.palm_id].copy()
        self.environment_geoms={i for i in range(model.ngeom) if model.geom_bodyid[i]==0}|{self.support.geom}
        np.testing.assert_array_equal(base.model.actuator_forcerange,model.actuator_forcerange)
        assert model.nv==base.model.nv+1 and model.neq==base.model.neq
        mujoco.mj_forward(model,self.data)

    def build_canonical_observation(self):
        o=super().build_canonical_observation()
        if not hasattr(self,'support'):return o
        # Base adapter identifies static world geoms as environment. The moving
        # table now has a body ID: correct only that environment/contact mapping.
        # No load-fraction or oracle value is added to the control observation.
        table_id=self.support.geom
        table_contacts=[c for c in o.contacts if int(c.contact_id.split(':')[1])==table_id]
        o.contacts=[c for c in o.contacts if c not in table_contacts]
        supported=o.objects['target'].support.value or bool(table_contacts)
        o.objects['target'].support=known(supported,o.timestamp,'SIM_CONTACT',Method.DERIVED)
        force=np.zeros(3);torque=np.zeros(3)
        for i in range(self.data.ncon):
            c=self.data.contact[i]
            if self.object_geom not in (c.geom1,c.geom2):continue
            other=int(c.geom2 if c.geom1==self.object_geom else c.geom1)
            if other in self.environment_geoms:continue
            raw=np.zeros(6);mujoco.mj_contactForce(self.model,self.data,i,raw)
            if raw[0]<1e-5:continue
            sign=1 if c.geom2==self.object_geom else -1
            f=sign*c.frame.reshape(3,3).T@raw[:3]
            force+=f;torque+=np.cross(c.pos-self.data.xpos[self.object_id],f)+sign*c.frame.reshape(3,3).T@raw[3:]
        o.interaction.interaction_wrench=known({'frame':'world','about':'object_com','force':force.tolist(),'torque':torque.tolist()},
                                              o.timestamp,'SIM_CONTACT',Method.DERIVED)
        # Only the no-contact diagnostic label can have included table contact;
        # stable verification/load semantics remain those of the frozen adapter.
        if not o.contacts:o.grasp.state=known('UNSTABLE',o.timestamp,'BASELINE_STATIC_V1',Method.ESTIMATED,.6)
        return o

    def step(self,steps=1):
        for _ in range(steps):
            self.support.apply()
            mujoco.mj_step(self.model,self.data);mujoco.mj_forward(self.model,self.data)
            for callback in tuple(self.callbacks):callback(self.build_canonical_observation())
            for callback in tuple(self.after_step):callback(self.build_canonical_observation())

    def evaluation_oracle(self):
        """Evaluation-only world-frame force accounting, including ALL environment."""
        if not hasattr(self,'oracle_data'):self.oracle_data=mujoco.MjData(self.model)
        d=self.oracle_data
        mujoco.mj_copyData(d,self.model,self.data)
        mujoco.mj_forward(self.model,d)
        # Independent recomputation after probe clearing / controller commands;
        # does not mutate the control state or its solver warm start.
        hand=np.zeros(3);support=np.zeros(3);contacts=[];environment_present=False
        for i in range(d.ncon):
            c=d.contact[i]
            if self.object_geom not in (c.geom1,c.geom2):continue
            other=int(c.geom2 if c.geom1==self.object_geom else c.geom1)
            raw=np.zeros(6);mujoco.mj_contactForce(self.model,d,i,raw)
            sign=1 if c.geom2==self.object_geom else -1
            force=sign*c.frame.reshape(3,3).T@raw[:3]
            env=other in self.environment_geoms
            if env:support+=force;environment_present|=raw[0]>1e-5
            else:hand+=force
            contacts.append({'geom':self.model.geom(other).name,'environment':env,'group':self.geom_groups[other],
                'position':c.pos.tolist(),'normal_world':(sign*c.frame.reshape(3,3)[0]).tolist(),
                'normal_load':float(raw[0]),'force_world':force.tolist(),'friction':c.friction.tolist()})
        # Object is a free body with its origin at the cylinder COM; its first
        # three free-joint qacc entries are COM translational acceleration.
        dof=int(self.model.jnt_dofadr[self.model.joint('object_free').id])
        acceleration=float(d.qacc[dof+2]);weight=self.config.mass*abs(self.model.opt.gravity[2])
        R=d.xmat[self.object_id].reshape(3,3)
        half_extent=self.config.height/2*abs(R[2,2])+self.config.radius*np.sqrt(R[2,0]**2+R[2,1]**2)
        top=float(d.geom_xpos[self.support.geom,2]+self.model.geom_size[self.support.geom,2])
        return {'label':'EVALUATION_ORACLE_NOT_CONTROL_FEEDBACK','F_hand_z':float(hand[2]),'F_support_z':float(support[2]),
            'object_weight':weight,'hand_load_fraction':float(hand[2]/weight),'support_load_fraction':float(support[2]/weight),
            'object_vertical_acceleration':acceleration,'external_probe_Fz':float(d.xfrc_applied[self.object_id,2]),
            'force_balance_residual_N':float(hand[2]+support[2]+d.xfrc_applied[self.object_id,2]-weight-self.config.mass*acceleration),
            'support_contact_present':bool(environment_present),'support_top_z':top,
            'object_to_support_gap':float(d.xpos[self.object_id,2]-half_extent-top),
            'contacts':contacts,'support_position':d.xpos[self.support.body].tolist(),
            'support_velocity':float(d.qvel[self.support.dof]),'support_command_position':self.support.target,
            'support_command_velocity':self.support.velocity,'support_servo_force_N':self.support.force}
