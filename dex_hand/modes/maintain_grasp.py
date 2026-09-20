import numpy as np
from dex_hand.core.outcome import SkillOutcome, AdapterError, FailureClass as F
from dex_hand.skills.base import loads, position


class MaintainGrasp:
    name="MAINTAIN_GRASP"

    def __init__(self, adapter):
        self.a=adapter
        self.active=False
        self.health="INACTIVE"
        self.recovery_count=0
        self.contact_loss_count=0
        self.event=None
        self.elapsed=0.
        self.lost_time=0.
        self.recovery_travel=0.
        self.max_drift=0.
        self.saturated_time=0.

    def enter(self, object_id, groups, target_load=.6, max_load=4., max_drift=.012, recovery_budget=.015):
        o=self.a.build_canonical_observation()
        if self.active or self.a.active_modes or not self.a.grasp_verified or o.grasp.state.value != "STABLE":
            return SkillOutcome("FAILED",self.name,F.PRECONDITION_FAILED,"verified stable grasp required; mode must be inactive")
        if not 0<target_load<max_load or max_drift<=0 or recovery_budget<=0:
            return SkillOutcome("FAILED",self.name,F.PRECONDITION_FAILED,"invalid mode bounds")
        if object_id not in o.objects or not groups or len({g.group_id for g in groups})!=len(groups):
            return SkillOutcome("FAILED",self.name,F.PRECONDITION_FAILED,"valid object and unique groups required")
        try:
            for group in groups:self.a.resolve_contact_group(group)
            if min(loads(o,groups,object_id).values())<.15:
                return SkillOutcome("FAILED",self.name,F.PRECONDITION_FAILED,"requested groups are not loaded")
        except AdapterError as e:
            return SkillOutcome("FAILED",self.name,e.failure_class,str(e))
        self.object_id,self.groups=object_id,groups
        self.target_load,self.max_load=target_load,max_load
        self.drift_limit,self.recovery_budget=max_drift,recovery_budget
        self.reference=position(o,object_id)
        self.active=True
        self.a.mode_controller=self
        self.health="NOMINAL"
        self.event=None
        self.elapsed=self.lost_time=self.recovery_travel=self.max_drift=0.
        self.saturated_time=0.
        self.recovery_count=self.contact_loss_count=0
        self.was_degraded=False
        self.a.active_modes.append(self.name)
        self.a.add_step_callback(self._tick)
        return SkillOutcome("SUCCEEDED",self.name,achieved_state={"active":True})

    def update(self, *, target_load=None, max_drift=None):
        if not self.active:
            return SkillOutcome("FAILED",self.name,F.PRECONDITION_FAILED,"mode inactive")
        if target_load is not None and not 0<target_load<self.max_load:
            return SkillOutcome("FAILED",self.name,F.PRECONDITION_FAILED,"load update outside safety envelope")
        if max_drift is not None and not 0<max_drift<=self.drift_limit:
            return SkillOutcome("FAILED",self.name,F.PRECONDITION_FAILED,"drift update may only tighten bound")
        if target_load is not None: self.target_load=target_load
        if max_drift is not None: self.drift_limit=max_drift
        return SkillOutcome("SUCCEEDED",self.name,achieved_state=self.query())

    def query(self):
        return {"active":self.active,"health":self.health,"elapsed_s":self.elapsed,
                "local_recovery_count":self.recovery_count,"contact_loss_count":self.contact_loss_count,
                "recovery_travel_m":self.recovery_travel,"max_relative_drift_m":self.max_drift,
                "failure_event":self.event}

    def exit(self):
        self.a.remove_step_callback(self._tick)
        if self.name in self.a.active_modes:self.a.active_modes.remove(self.name)
        self.active=False
        if self.health != "CRITICAL":self.health="INACTIVE"
        return SkillOutcome("SUCCEEDED",self.name,achieved_state={"active":False})

    def _critical(self, failure, detail):
        self.health="CRITICAL"
        self.event=SkillOutcome("FAILED",self.name,failure,detail,diagnostics={"timestamp":self.a.build_canonical_observation().timestamp}).to_dict()
        self.a.events.append(self.event)
        self.a.grasp_verified=False
        self.exit()
        self.a.safe_hold()

    def _tick(self,o):
        if not self.active:return
        self.elapsed+=self.a.dt
        try:
            current=loads(o,self.groups,self.object_id)
            if not o.hand.joint_effort.valid or not o.hand.actuator_saturated.valid:
                return self._critical(F.SENSOR_UNAVAILABLE,"joint effort safety feedback unavailable")
            self.saturated_time=self.saturated_time+self.a.dt if o.hand.actuator_saturated.value else 0.
            if self.saturated_time>.2:return self._critical(F.ACTUATOR_LIMIT,"actuator effort saturated for over 200 ms")
            drift=float(np.linalg.norm(position(o,self.object_id)-self.reference))
            self.max_drift=max(self.max_drift,drift)
            if o.hand.collision.value:return self._critical(F.COLLISION,"unexpected collision")
            if max(current.values())>self.max_load:return self._critical(F.WRENCH_LIMIT_EXCEEDED,"group normal load exceeded envelope")
            if drift>self.drift_limit:return self._critical(F.OBJECT_DISPLACED,"relative object drift exceeded bounded recovery envelope")
            missing=min(current.values())<.02
            if missing:
                if self.lost_time==0:self.contact_loss_count+=1
                self.lost_time+=self.a.dt
            else:self.lost_time=0.
            if self.lost_time>.25:return self._critical(F.CONTACT_LOST,"contact not recovered within 250 ms")
            degraded=missing or min(current.values())<.15 or drift>.004
            if degraded and not self.was_degraded:self.recovery_count+=1
            self.was_degraded=degraded
            self.health="DEGRADED" if degraded else "NOMINAL"
            inc=np.array([np.clip((self.target_load-current[g.group_id])*.003,-.002,.002)*self.a.dt for g in self.groups])
            if degraded:self.recovery_travel+=float(np.max(np.abs(inc)))
            if self.recovery_travel>self.recovery_budget:return self._critical(F.SLIP_UNRECOVERABLE,"local recovery motion budget exhausted (drift proxy; slip itself unknown)")
            self.a.advance_groups(self.object_id,self.groups,inc)
        except AdapterError as e:
            self._critical(e.failure_class,str(e))
