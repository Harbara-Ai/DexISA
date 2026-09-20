import numpy as np
from .base import Skill, guarded, contacts, loads, position
from dex_hand.core.outcome import FailureClass as F


class BaselineStability:
    """Replaceable contact/load/relative-motion predicate; NOT wrench feasibility."""
    version = "BASELINE_STATIC_V1"

    def evaluate(self, o, object_id, groups, minimum_load, reference):
        current = loads(o,groups,object_id)
        velocity = o.objects[object_id].relative_velocity
        return (bool(current) and min(current.values()) >= minimum_load and velocity.valid
                and np.linalg.norm(velocity.value["linear"]) < .015
                and np.linalg.norm(velocity.value["angular"]) < .5
                and np.linalg.norm(position(o,object_id)-reference) < .008)


class EstablishGrasp(Skill):
    def __init__(self, adapter, perturbation=None, evaluator=None):
        super().__init__(adapter)
        self.perturbation = perturbation
        self.evaluator = evaluator or BaselineStability()

    @guarded("ESTABLISH_GRASP")
    def run(self, object_id, groups, minimum_load=.15, target_load=.6, max_load=4., timeout=5., required_wrench_set=None):
        o=self.validate(object_id,groups)
        if len(groups)<2 or not contacts(o,object_id):
            return self.fail(F.PRECONDITION_FAILED,"partial contact with a multi-group plan required")
        if required_wrench_set is not None:
            return self.fail(F.NOT_SUPPORTED,"baseline cannot certify required wrench sets or task wrench margin")
        if not 0 < minimum_load <= target_load < max_load:
            return self.fail(F.PRECONDITION_FAILED,"invalid load envelope")
        if self.perturbation is None:
            return self.fail(F.NOT_SUPPORTED,"baseline verification requires injected perturbation apparatus")
        reference=position(o,object_id)
        stable_time=0.
        travel=np.zeros(len(groups))
        probe_started=False
        self.a.phase="LOAD_RAMP"
        try:
            for _ in range(int(timeout/self.a.dt)):
                o=self.a.build_canonical_observation()
                self.check(o,max_load)
                if np.linalg.norm(position(o,object_id)-reference)>.02:
                    return self.fail(F.OBJECT_DISPLACED,"object escaped during load ramp")
                current=loads(o,groups,object_id)
                inc=np.array([np.clip((target_load-current[g.group_id])*.003,-.002,.002)*self.a.dt for g in groups])
                travel+=np.abs(inc)
                if np.max(travel)>.02: return self.fail(F.ACTUATOR_LIMIT,"bounded preload travel exhausted")
                self.a.advance_groups(object_id,groups,inc)
                if self.evaluator.evaluate(o,object_id,groups,minimum_load,reference):
                    stable_time+=self.a.dt
                    if stable_time>=.2 and not probe_started:
                        self.perturbation.set_wrench(force=(.15,0.,.1))
                        probe_started=True
                        self.a.phase="PERTURBATION_VERIFY"
                    if stable_time>=.55 and probe_started:
                        self.a.grasp_verified=True
                        self.a.verified_groups=tuple(g.group_id for g in groups)
                        self.a.verified_reference=reference.copy()
                        out=self.ok(grasp_state="STABLE",evaluator=self.evaluator.version,
                                    verification_wrench={"frame":"world","force_n":[.15,0.,.1],"duration_s":.35},
                                    support_context="tabletop; no free-space force-closure certificate")
                        out.residual_uncertainty=["task_wrench_margin UNKNOWN", "object_slip UNKNOWN", "only baseline perturbation verified"]
                        return out
                else:
                    stable_time=0.
                    if probe_started:
                        self.perturbation.clear()
                        probe_started=False
                        self.a.phase="LOAD_RAMP"
                self.a.step()
            return self.fail(F.TIMEOUT,"baseline stability plus perturbation not established")
        finally:
            self.perturbation.clear()
