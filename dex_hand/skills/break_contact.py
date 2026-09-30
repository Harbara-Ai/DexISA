import numpy as np
from .base import Skill, guarded, contacts, position
from dex_hand.core.outcome import FailureClass as F


class BreakContact(Skill):
    @guarded("BREAK_CONTACT")
    def run(self, object_id, groups, support_state="SURFACE", allow_drop=False, mode="GRADUAL", retreat=.012,
            speed=.006, max_object_drift=.015, timeout=5.):
        o=self.validate(object_id,groups)
        if support_state not in ("NONE","SURFACE","FIXTURE") or mode!="GRADUAL":
            return self.fail(F.NOT_SUPPORTED,"unsupported release/support mode")
        if not allow_drop and (support_state=="NONE" or not o.objects[object_id].support.valid or not o.objects[object_id].support.value):
            return self.fail(F.PRECONDITION_FAILED,"release requires observed support or explicit allow_drop")
        if retreat<0 or speed<=0 or timeout<=0:return self.fail(F.PRECONDITION_FAILED,"invalid retreat bounds")
        if hasattr(self.a,"mode_controller") and self.a.mode_controller.active:self.a.mode_controller.exit()
        reference=position(o,object_id)
        self.a.phase="UNLOAD_AND_RETREAT"
        travel=0.
        clear_time=0.
        for _ in range(int(timeout/self.a.dt)):
            o=self.a.build_canonical_observation()
            self.check(o)
            if not allow_drop and np.linalg.norm(position(o,object_id)-reference)>max_object_drift:
                return self.fail(F.OBJECT_DISPLACED,"unauthorized movement during release")
            remaining=contacts(o,object_id)
            clear_time=clear_time+self.a.dt if not remaining else 0.
            if clear_time>=.1 and travel>=retreat:
                self.a.grasp_verified=False
                return self.ok(contacts_present=False,retreat_m=travel)
            if travel<retreat:
                inc=min(speed*self.a.dt,retreat-travel)
                self.a.advance_groups(object_id,groups,[-inc]*len(groups))
                travel+=inc
            self.a.step()
        return self.fail(F.TIMEOUT if not contacts(o,object_id) else F.JAMMED,"release/retreat did not complete within deadline")
