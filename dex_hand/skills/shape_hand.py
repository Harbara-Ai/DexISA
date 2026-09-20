from .base import Skill, guarded, contacts
from dex_hand.core.outcome import FailureClass as F


class ShapeHand(Skill):
    @guarded("SHAPE_HAND")
    def run(self, object_id, groups, profile="PRESHAPE", aperture=.04, clearance=.012, timeout=3.):
        o = self.validate(object_id,groups)
        if contacts(o): return self.fail(F.PRECONDITION_FAILED,"SHAPE_HAND requires no task contact")
        self.a.prepare_configuration(profile,object_id,groups,aperture,clearance)
        self.a.phase = "CONFIGURING"
        for _ in range(int(timeout/self.a.dt)):
            self.a.step()
            o = self.a.build_canonical_observation()
            if contacts(o): return self.fail(F.PREMATURE_CONTACT,"contact during no-contact shaping")
            self.check(o)
            if self.a.configuration_error() < .002:
                return self.ok(profile=profile,configuration_error_m=self.a.configuration_error())
        return self.fail(F.TIMEOUT,"configuration tolerance not reached")
