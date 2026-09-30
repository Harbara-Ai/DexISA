"""Two tool surfaces over one world, control observation and safety shield."""
import json,math,time
from pathlib import Path
from dataclasses import replace
import numpy as np
import mujoco
from dex_hand.adapters import create_adapter
from dex_hand.core.observation import known,Pose,Method
from dex_hand.core.outcome import AdapterError,FailureClass as F
from dex_hand.core.types import PINCH_GROUPS,PRESS_GROUPS
from dex_hand.modes.maintain_grasp import MaintainGrasp
from dex_hand.sim.worlds import WorldConfig

from evaluation.tasks.definitions import BUTTON_RELATIVE, TASKS



def rounded(x):return np.round(x,6).tolist()

class TaskProbe:
    """Shared evaluation apparatus owns the disturbance, not an agent helper."""
    def set_wrench(self,**kwargs):pass
    def clear(self):pass


from evaluation.safety.common_shield import shield_violation
from evaluation.evaluators.task_state import evaluate_tick
from evaluation.agents.surfaces import direct_action, skill_action


class PilotEpisode:
    def __init__(self,task,hand,condition,scenario,folder):
        self.task,self.hand,self.condition,self.scenario=task,hand,condition,scenario
        self.folder=Path(folder);self.folder.mkdir(parents=True,exist_ok=True)
        base=create_adapter(hand);center=(.025,.065,.26)
        if task=='C':center=tuple(base.data.xpos[base.palm_id]+BUTTON_RELATIVE)
        self.nominal_center=np.array(center)
        self.estimate_bias=np.array([0.,-.005,0.]) if scenario=='recovery' else np.zeros(3)
        actual=np.array(center)-self.estimate_bias
        self.config=WorldConfig(kind='button' if task=='C' else 'grasp',center=tuple(actual),friction=1.2)
        self.a=create_adapter(hand,config=self.config)
        if scenario=='safe_failure':
            self.a.model.jnt_stiffness[self.a.model.joint('button_slide').id]=2000.
            # Save the exact compiled scene modification, not an unmodified XML.
            import xml.etree.ElementTree as ET
            root=ET.fromstring(self.a.xml);root.find(".//joint[@name='button_slide']").set('stiffness','2000')
            self.a.xml=ET.tostring(root,encoding='unicode')
            mujoco.mj_forward(self.a.model,self.a.data)
        self.groups=PINCH_GROUPS if task=='D' else PRESS_GROUPS if task=='C' else (PINCH_GROUPS[1],)
        self.force_limit=3. if task=='C' else 4.
        self.mode=MaintainGrasp(self.a);self.probe=TaskProbe()
        self.shield_failure=None;self.action_failures=0;self.recovery_attempts=0;self.last_failed=False
        self.initial_object=self.a.data.xpos[self.a.object_id].copy()
        self.goal_world=self.nominal_center+np.array(self.groups[0].outward)*(.004+.012 if task=='C' else .02+.012)
        self.baseline_ref=None;self.stable_s=0.;self.certified=False;self.hold_s=0.;self.hold_pass=False;self.hold_lost_s=0.
        self.activated=False;self.release_ref=None;self.clear_s=0.;self.success=False
        self.max_group_force=0.;self.max_drift=0.;self.saturated_s=0.;self.sim_wall=0.
        self.trace=(self.folder/'simulation.jsonl').open('w',encoding='utf-8')
        self.tool_trace=[];self.calls=0;self.queries=0;self.tool_wall=0.
        self.first_contact_time=None;self.last_motion_end=None
        self.static_sent=True
        # Same stale object belief for control observation AND preshape targeting.
        original_observe=self.a.build_canonical_observation
        def observe():
            o=original_observe()
            if np.any(self.estimate_bias):
                obj=o.objects['target'];R=self.a.data.xmat[self.a.palm_id].reshape(3,3)
                obj.pose=replace(obj.pose,value=replace(obj.pose.value,position=(np.array(obj.pose.value.position)+self.estimate_bias).tolist()))
                obj.relative_pose=replace(obj.relative_pose,value=replace(obj.relative_pose.value,position=(np.array(obj.relative_pose.value.position)+R.T@self.estimate_bias).tolist()))
            return o
        self.a.build_canonical_observation=observe
        original_prepare=self.a.prepare_configuration
        def prepare(profile,object_id,groups,aperture=.06,clearance=.008):
            original_prepare(profile,object_id,groups,aperture,clearance)
            if np.any(self.estimate_bias):
                points={k:v+self.estimate_bias for k,v in self.a.group_targets.items()}
                q,residual=self.a._ik(points)
                if residual>.003:raise AdapterError(F.UNREACHABLE,'belief-frame IK residual exceeds existing tolerance')
                self.a.group_targets=points;self.a.command_joint_targets(q)
        self.a.prepare_configuration=prepare
        old_step=self.a.step
        def step(n=1):
            start=time.perf_counter()
            try:
                for _ in range(n):
                    # Same independent BASELINE_STATIC_V1 probe for both agents.
                    self.a.data.xfrc_applied[self.a.object_id,:]=0
                    if task=='D' and not self.certified and self.stable_s>=.2:
                        self.a.data.xfrc_applied[self.a.object_id,:3]=[.15,0,.1]
                    old_step()
            finally:self.sim_wall+=time.perf_counter()-start
        self.a.step=step
        self.a.add_step_callback(self.tick)
        (self.folder/'scene.xml').write_text(self.a.xml,encoding='utf-8')
        (self.folder/'initial_state.json').write_text(json.dumps(self.static(),indent=2),encoding='utf-8')

    def tick(self,o):
        a=self.a;dt=a.dt
        loads={g:sum(c.normal_load.value for c in o.contacts if c.contact_group_id==g) for g in a.group_map}
        peak=max(loads.values(),default=0);self.max_group_force=max(self.max_group_force,peak)
        if self.task=='B' and loads['primary']>1e-5 and self.first_contact_time is None:self.first_contact_time=float(o.timestamp)
        drift=float(np.linalg.norm(a.data.xpos[a.object_id]-self.initial_object));self.max_drift=max(self.max_drift,drift)
        self.saturated_s=self.saturated_s+dt if o.hand.actuator_saturated.value else 0.
        violation=shield_violation(self,o,peak,drift)
        self.trace.write(json.dumps({'observation':o.to_dict(),'qpos':a.data.qpos.tolist(),'qvel':a.data.qvel.tolist(),
            'joint_command':a.last_command,'skill':a.skill,'phase':a.phase,'shield_violation':violation,
            'object_ground_truth':a.data.xpos[a.object_id].tolist(),'probe':a.data.xfrc_applied[a.object_id].tolist()})+'\n')
        if violation:
            self.shield_failure=violation;a.safe_hold();raise AdapterError(F(violation),'common pilot safety shield stopped motion')
        evaluate_tick(self,o,loads,drift)

    def compact(self,fields=None):
        o=self.a.build_canonical_observation()
        fields=fields if fields is not None else ['contacts','object_relative_pose','status']+(['joint_state'] if self.condition=='DIRECT_AGENT' else [])
        result={'time':round(o.timestamp,4)}
        if 'joint_state' in fields:result['q']=rounded(o.hand.joint_position.value)
        if 'contacts' in fields:result['contacts']=[{'group':c.contact_group_id,'normal_load':round(c.normal_load.value,4),
            'position':rounded(c.position.value['xyz'])} for c in o.contacts]
        if 'object_relative_pose' in fields:result['object_relative_pose']={'position':rounded(o.objects['target'].relative_pose.value.position),'quaternion':rounded(o.objects['target'].relative_pose.value.quaternion_wxyz)}
        if 'status' in fields:result.update(phase=self.a.phase,active_modes=o.active_modes,grasp=o.grasp.state.value,
            activated=o.objects['target'].activated.value,mode_health=self.mode.health,event=self.shield_failure,
            task_success=bool(self.success),baseline_verified=self.certified,hold_survived=self.hold_pass)
        return result

    def static(self):
        a=self.a;m=a.model
        data={'task':TASKS[self.task],'object':{'nominal_world_position':self.nominal_center.tolist(),
            'radius':self.config.radius,'height':self.config.height,'mass':self.config.mass,'friction':1.2},
            'safety':{'group_force_limit_N':self.force_limit,'joint_effort_caps':'original model; unchanged','max_recovery':1},
            'groups':[g.group_id for g in self.groups],'target_primary_site_world':self.goal_world.tolist(),
            'palm_native_world_pose':{'position':a.data.xpos[a.palm_id].tolist(),'quaternion':a.data.xquat[a.palm_id].tolist()},
            'task_frame':'palm origin + world-aligned fixed installation axes; native palm frame is retained in observations',
            'initial_state':self.compact()}
        if self.task=='C':data['object'].update(button_target_in_installation_frame=BUTTON_RELATIVE,
            activation_displacement=.008,stiffness=float(m.jnt_stiffness[m.joint('button_slide').id]),slide_axis_world=[0,1,0])
        if self.condition=='SKILL_AGENT':data['capabilities']=a.get_capabilities()
        else:
            data['joint_definitions']=[{'index':i,'name':m.joint(j).name,'range':m.jnt_range[j].tolist(),
                'effort_cap':m.actuator_forcerange[i].tolist(),'body':int(m.jnt_bodyid[j]),'axis':m.jnt_axis[j].tolist(),'anchor':m.jnt_pos[j].tolist()}
                for i,j in enumerate(a.joints)]
            relevant=set()
            for g in self.groups:
                bid=int(m.site_bodyid[a.sites[g.group_id]])
                while bid and bid!=a.palm_id:relevant.add(bid);bid=int(m.body_parentid[bid])
            data['kinematic_chain']=[{'body':b,'parent':int(m.body_parentid[b]),'position':m.body_pos[b].tolist(),'quaternion':m.body_quat[b].tolist()} for b in sorted(relevant)]
            data['sites']={g.group_id:{'body':int(m.site_bodyid[a.sites[g.group_id]]),'local_position':m.site_pos[a.sites[g.group_id]].tolist()} for g in self.groups}
        return data

    def dispatch(self,name,args):
        start=time.perf_counter();self.calls+=1
        action=name not in ('get_state','describe_hand','describe_capabilities','MAINTAIN_GRASP_query')
        if self.last_failed and action:
            self.recovery_attempts+=1;self.last_failed=False
            if self.recovery_attempts>1:return {'failure':'RECOVERY_BUDGET_EXHAUSTED'}
        try:
            if self.shield_failure and name not in ('get_state','stop','MAINTAIN_GRASP_exit'):
                return {'failure':self.shield_failure,'motion_latched_off':True}
            if name=='get_state':
                self.queries+=1
                duration=float(args.get('wait_s',0))
                if not 0<=duration<=1:raise ValueError('wait_s must be 0..1')
                self.a.step(round(duration/self.a.dt));result=self.compact(args.get('fields'))
            elif name in ('describe_hand','describe_capabilities'):
                result={'static_context':'Already supplied once in initial context; consult it.'}
            elif self.condition=='DIRECT_AGENT':
                result=direct_action(self,name,args)
            else:
                result=skill_action(self,name,args)
            return result
        except (AdapterError,ValueError,KeyError,TypeError) as e:
            self.action_failures+=1;self.last_failed=True
            return {'failure':str(e.failure_class) if isinstance(e,AdapterError) else 'INVALID_ARGUMENT','detail':str(e),'state':self.compact()}
        finally:
            self.tool_wall+=time.perf_counter()-start
            if action:self.last_motion_end=float(self.a.data.time)
            self.tool_trace.append({'name':name,'arguments':args,'simulation_time':float(self.a.data.time)})

    def finish(self,claimed):
        safe=self.scenario=='safe_failure' and claimed=='safe_failure' and not self.shield_failure and not self.activated
        result={'outcome':'SUCCESS' if self.success and not self.shield_failure else 'SAFE_FAILURE' if safe else 'FAILED',
            'claimed':claimed,'shield_failure':self.shield_failure,'physical_success':bool(self.success),
            'recovery_attempts':self.recovery_attempts,'action_failures':self.action_failures,
            'max_group_force':self.max_group_force,'max_object_drift':self.max_drift,'task_baseline_verified':self.certified,
            'hold_survived':self.hold_pass,'tool_calls':self.calls,'state_queries':self.queries,
            'T_tool':self.tool_wall,'T_physical_sim':float(self.a.data.time),'T_sim_compute':self.sim_wall,
            'first_contact_time':self.first_contact_time,
            'contact_to_action_end_s':max(0.,self.last_motion_end-self.first_contact_time) if self.first_contact_time is not None and self.last_motion_end is not None else None,
            'mujoco_warnings':sum(w.number for w in self.a.data.warning),'final_state':self.compact()}
        self.mode.exit();self.a.safe_hold();self.trace.close()
        (self.folder/'simulation_result.json').write_text(json.dumps(result,indent=2))
        (self.folder/'tool_calls.json').write_text(json.dumps(self.tool_trace,indent=2))
        return result
