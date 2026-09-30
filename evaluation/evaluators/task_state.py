"""Frozen A-D scoring and hold-envelope checks; called after the shield."""
import numpy as np
from dex_hand.core.outcome import AdapterError, FailureClass as F

def evaluate_tick(self,o,loads,drift):
    a=self.a;dt=a.dt
    if self.task=='A':self.success=np.linalg.norm(a.data.site_xpos[a.sites['primary']]-self.goal_world)<.002 and not o.contacts
    if self.task=='B':self.success=loads['primary']>1e-5 and all(c.contact_group_id=='primary' for c in o.contacts) and drift<=.015
    if self.task=='C' and o.objects['target'].activated.value:self.activated=True
    if self.task=='D':
        p=np.array(o.objects['target'].relative_pose.value.position);vel=o.objects['target'].relative_velocity.value
        both=min(loads['primary'],loads['opposition'])>=.15
        if self.baseline_ref is None and both:self.baseline_ref=p.copy()
        within=self.baseline_ref is not None and np.linalg.norm(p-self.baseline_ref)<.008
        stable=both and within and np.linalg.norm(vel['linear'])<.015 and np.linalg.norm(vel['angular'])<.5
        if not self.certified:
            self.stable_s=self.stable_s+dt if stable else 0.
            if self.stable_s>=.55:self.certified=True;self.hold_ref=p.copy()
        elif not self.hold_pass:
            self.hold_lost_s=self.hold_lost_s+dt if min(loads['primary'],loads['opposition'])<.02 else 0.
            if self.hold_lost_s>.25 or np.linalg.norm(p-self.hold_ref)>.012:
                code=F.CONTACT_LOST if self.hold_lost_s>.25 else F.OBJECT_DISPLACED
                self.shield_failure=str(code);a.safe_hold()
                raise AdapterError(code,'common grasp hold evaluator exceeded frozen mode envelope')
            else:self.hold_s+=dt
            if self.hold_s>=.5:self.hold_pass=True
    ready=self.activated if self.task=='C' else self.hold_pass if self.task=='D' else False
    if ready:
        if self.release_ref is None:self.release_ref={g.group_id:a.data.site_xpos[a.sites[g.group_id]].copy() for g in self.groups}
        self.clear_s=self.clear_s+dt if not o.contacts else 0.
        retreats=[np.dot(a.data.site_xpos[a.sites[g.group_id]]-self.release_ref[g.group_id],np.array(g.outward)) for g in self.groups]
        self.success=bool(self.clear_s>=.1 and min(retreats)>=.002-1e-6)
