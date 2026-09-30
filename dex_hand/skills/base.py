import functools
import numpy as np
from dex_hand.core.outcome import SkillOutcome, AdapterError, FailureClass as F


def contacts(observation, object_id="target"):
    if any(c.object_id==object_id and not c.presence.valid for c in observation.contacts):
        raise AdapterError(F.SENSOR_UNAVAILABLE,"contact presence is uncertain or stale")
    return [c for c in observation.contacts if c.object_id == object_id and c.presence.valid and c.presence.value]


def loads(observation, groups, object_id="target"):
    if any(not c.normal_load.valid for c in contacts(observation,object_id) if c.contact_group_id in {g.group_id for g in groups}):
        raise AdapterError(F.SENSOR_UNAVAILABLE,"required normal load is uncertain or stale")
    return {g.group_id: sum(c.normal_load.value for c in contacts(observation,object_id)
                           if c.contact_group_id == g.group_id and c.normal_load.valid) for g in groups}


def position(observation, object_id):
    obj = observation.objects.get(object_id)
    if obj is None or not obj.relative_pose.valid:
        raise AdapterError(F.SENSOR_UNAVAILABLE, "object relative pose not available")
    return np.array(obj.relative_pose.value.position)


def guarded(name):
    def decorate(fn):
        @functools.wraps(fn)
        def call(self, *args, **kwargs):
            self.a.skill, self.a.phase = name, "PRECONDITION"
            start = self.a.build_canonical_observation().timestamp
            try:
                if self.a.active_modes and name != "BREAK_CONTACT":
                    result=SkillOutcome("FAILED",name,F.PRECONDITION_FAILED,"conflicting persistent mode is active")
                else:
                    result = fn(self, *args, **kwargs)
            except AdapterError as error:
                result = SkillOutcome("FAILED", name, error.failure_class, str(error))
            result.diagnostics["execution_time_s"] = self.a.build_canonical_observation().timestamp-start
            self.a.phase = result.status
            if not result.success:
                if self.a.build_canonical_observation().timestamp > start:self.a.safe_hold()
                self.a.events.append(result.to_dict())
            return result
        return call
    return decorate


class Skill:
    def __init__(self, adapter): self.a = adapter

    def check(self, o, max_load=8.):
        if not o.hand.collision.valid:
            raise AdapterError(F.SENSOR_UNAVAILABLE,"collision observable unavailable")
        if o.hand.collision.valid and o.hand.collision.value:
            raise AdapterError(F.COLLISION, "unexpected hand/environment or self contact")
        groups={c.contact_group_id for c in o.contacts}
        if any(not c.normal_load.valid for c in o.contacts):
            raise AdapterError(F.SENSOR_UNAVAILABLE,"load safety observable unavailable")
        if any(sum(c.normal_load.value for c in o.contacts if c.contact_group_id==g)>max_load for g in groups):
            raise AdapterError(F.WRENCH_LIMIT_EXCEEDED,"measured contact load exceeded limit")

    def ok(self, **state):
        return SkillOutcome("SUCCEEDED",self.a.skill,achieved_state=state)

    def fail(self, failure, detail):
        return SkillOutcome("FAILED",self.a.skill,failure,detail)

    def validate(self, object_id, groups):
        o = self.a.build_canonical_observation()
        if object_id not in o.objects: raise AdapterError(F.PRECONDITION_FAILED,"unknown object")
        if not groups or len({g.group_id for g in groups}) != len(groups):
            raise AdapterError(F.PRECONDITION_FAILED,"contact groups must be nonempty and unique")
        for g in groups: self.a.resolve_contact_group(g)
        return o
