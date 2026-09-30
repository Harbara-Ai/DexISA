from .base import Skill, guarded, contacts, loads
from dex_hand.core.outcome import FailureClass as F


class ApplyWrench(Skill):
    @guarded("APPLY_WRENCH")
    def run(self, object_id, groups, target_force=1.8, max_load=3., termination="activation", target_displacement=.008,
            max_displacement=.025, timeout=6., force_tolerance=.05):
        o=self.validate(object_id,groups)
        if not 0<target_force<max_load or target_displacement<0 or max_displacement<=0 or not 0<=force_tolerance<target_force:
            return self.fail(F.PRECONDITION_FAILED,"invalid load/displacement bounds")
        if termination not in ("activation","force","displacement"):
            return self.fail(F.NOT_SUPPORTED,"unsupported wrench termination")
        required={g.group_id for g in groups}
        if not required <= {c.contact_group_id for c in contacts(o,object_id)}:
            return self.fail(F.PRECONDITION_FAILED,"APPLY_WRENCH requires existing target contacts")
        field=o.objects[object_id].activated if termination=="activation" else o.objects[object_id].displacement
        if termination!="force" and not field.valid:
            return self.fail(F.NOT_SUPPORTED,"termination observable unavailable")
        self.a.phase="FORCE_RAMP"
        travel=0.
        force_dwell=0.
        for _ in range(int(timeout/self.a.dt)):
            o=self.a.build_canonical_observation()
            self.check(o,max_load)
            current=loads(o,groups,object_id)
            if not required <= {c.contact_group_id for c in contacts(o,object_id)}:
                return self.fail(F.CONTACT_LOST,"contact disappeared during wrench application")
            if max(current.values())>max_load:return self.fail(F.WRENCH_LIMIT_EXCEEDED,"group load exceeded envelope")
            force=sum(current.values())
            force_dwell=force_dwell+self.a.dt if abs(force-target_force)<=force_tolerance else 0.
            obj=o.objects[object_id]
            reached=(termination=="activation" and obj.activated.valid and obj.activated.value
                     or termination=="displacement" and obj.displacement.valid and obj.displacement.value>=target_displacement
                     or termination=="force" and force_dwell>=.04)
            if reached:return self.ok(termination=termination,normal_load_n=force,force_tolerance_n=force_tolerance,displacement_m=obj.displacement.value,activated=obj.activated.value)
            if travel>=max_displacement:return self.fail(F.JAMMED,"press travel bound exhausted")
            # Admittance: increase motion until desired measured normal load.
            inc=max(-.003,min(.008,(target_force-force)*.012))*self.a.dt
            self.a.advance_groups(object_id,groups,[inc]*len(groups))
            travel+=abs(inc)
            self.a.step()
        return self.fail(F.TIMEOUT,"wrench termination condition not reached")
