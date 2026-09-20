import numpy as np
from .base import Skill, guarded, contacts, loads, position
from dex_hand.core.outcome import FailureClass as F


class MakeContact(Skill):
    @guarded("MAKE_CONTACT")
    def run(self, object_id, groups, speed=.008, max_displacement=.045, max_load=4.,
            require_all_groups=True, max_object_drift=.015, timeout=8., approach_frame="object", direction=None):
        o = self.validate(object_id,groups)
        if speed <= 0 or max_displacement < 0 or max_load <= 0 or timeout <= 0:
            return self.fail(F.PRECONDITION_FAILED,"positive motion/load/time bounds required")
        if direction is not None or approach_frame != "object":
            return self.fail(F.NOT_SUPPORTED,"baseline uses the inward normals of object-frame target regions")
        required = {g.group_id for g in groups if g.required}
        if not required: return self.fail(F.PRECONDITION_FAILED,"at least one required group needed")
        initial = position(o,object_id)
        distance = {g.group_id:0. for g in groups}
        self.a.phase = "GUARDED_APPROACH"
        for _ in range(int(timeout/self.a.dt)):
            o = self.a.build_canonical_observation()
            self.check(o,max_load)
            present = {c.contact_group_id for c in contacts(o,object_id)}
            if present-set(distance): return self.fail(F.PREMATURE_CONTACT,"nonparticipating contact group touched object")
            if np.linalg.norm(position(o,object_id)-initial) > max_object_drift:
                return self.fail(F.OBJECT_DISPLACED,"object moved during guarded approach")
            if (required <= present) if require_all_groups else bool(required & present):
                return self.ok(contact_groups=sorted(present),displacements_m=distance)
            increments = [0. if g.group_id in present else min(speed*self.a.dt,max_displacement-distance[g.group_id]) for g in groups]
            if max(increments) < 1e-10:
                return self.fail(F.INCOMPLETE_CONTACT_SET if present else F.NO_CONTACT_FOUND,"guarded displacement exhausted")
            self.a.advance_groups(object_id,groups,increments)
            for g, inc in zip(groups,increments): distance[g.group_id] += inc
            self.a.step()
        return self.fail(F.TIMEOUT,"contact acquisition deadline exceeded")
