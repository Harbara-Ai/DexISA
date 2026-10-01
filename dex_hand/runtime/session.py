"""Shared execution session; Adapter and scene binding are injected."""

import math
from dex_hand.adapters.base import HandAdapter
from dex_hand.core.outcome import AdapterError, FailureClass, SkillOutcome
from dex_hand.core.schema import validate_outcome
from dex_hand.core.scene import ScenePlan
from dex_hand.core.request import InstructionRequest
from dex_hand.runtime.requests import MAKE_CONTACT_KEYS, resolve_make_contact
from dex_hand.modes.maintain_grasp import MaintainGrasp
from dex_hand.skills.break_contact import BreakContact
from dex_hand.skills.establish_grasp import EstablishGrasp
from dex_hand.skills.shape_hand import ShapeHand


ARGUMENT_KEYS = {
    "get_state": {"wait_s"},
    "describe_capabilities": set(),
    "SHAPE_HAND": {"aperture_m", "clearance_m"},
    "MAKE_CONTACT": MAKE_CONTACT_KEYS,
    "ESTABLISH_GRASP": set(),
    "MAINTAIN_GRASP": {"duration_s"},
    "BREAK_CONTACT": set(),
}


class RuntimeSession:
    def __init__(self, *, adapter: HandAdapter, scene_plan: ScenePlan, perturbation=None):
        self.adapter = adapter
        self.scene_plan = scene_plan
        self.probe = perturbation
        self.mode = MaintainGrasp(adapter)

    def observation(self):
        return self.adapter.build_canonical_observation().to_dict()

    def execute(self, request):
        if not isinstance(request, InstructionRequest):
            request = InstructionRequest.from_mapping(request)
        name, args = request.tool, request.arguments
        if name not in ARGUMENT_KEYS:
            raise AdapterError(FailureClass.NOT_SUPPORTED, f"unsupported tool: {name}")
        unsupported = set(args) - ARGUMENT_KEYS[name]
        if unsupported:
            raise AdapterError(FailureClass.NOT_SUPPORTED,
                               f"unsupported arguments for {name}: {', '.join(sorted(unsupported))}")
        groups = self.scene_plan.groups
        adapter = self.adapter
        if name == "get_state":
            wait = float(args.get("wait_s", 0))
            if not math.isfinite(wait) or wait < 0:
                raise ValueError("wait_s must be finite and nonnegative")
            if wait:
                adapter.step(max(1, math.ceil(wait / adapter.dt)))
            result = {"status": "OK"}
        elif name == "describe_capabilities":
            result = {"status": "OK", "capabilities": adapter.get_capabilities(),
                      "observation_capabilities": {
                          key: value.__dict__ for key, value in adapter.get_observation_capabilities().items()
                      }}
        elif name == "SHAPE_HAND":
            outcome = ShapeHand(adapter).run(
                self.scene_plan.object_id, groups,
                aperture=float(args.get("aperture_m", self.scene_plan.aperture)),
                clearance=float(args.get("clearance_m", self.scene_plan.clearance)),
            )
            result = self._outcome(outcome)
        elif name == "MAKE_CONTACT":
            resolved = resolve_make_contact(request, adapter, self.scene_plan)
            result = self._outcome(resolved.execute(adapter))
        elif name == "ESTABLISH_GRASP":
            result = self._outcome(EstablishGrasp(adapter, self.probe).run(self.scene_plan.object_id, groups))
        elif name == "MAINTAIN_GRASP":
            duration = float(args.get("duration_s", 0.3))
            if not math.isfinite(duration) or duration <= 0:
                raise ValueError("duration_s must be finite and positive")
            outcome = self.mode.enter(self.scene_plan.object_id, groups)
            if outcome.success:
                steps = max(1, math.ceil(duration / adapter.dt))
                for _ in range(steps):
                    adapter.step()
                    if not self.mode.active:
                        break
                if self.mode.event:
                    event = self.mode.event
                    outcome = SkillOutcome("FAILED", "MAINTAIN_GRASP",
                                           FailureClass(event["failure_class"]),
                                           event["failure_detail"])
                else:
                    outcome = SkillOutcome("SUCCESS", "MAINTAIN_GRASP", achieved_state={
                        "maintained_s": self.mode.elapsed, "mode_health": self.mode.query()
                    })
                if self.mode.active:
                    self.mode.exit()
            result = self._outcome(outcome)
        elif name == "BREAK_CONTACT":
            result = self._outcome(BreakContact(adapter).run(self.scene_plan.object_id, groups))
        else:
            raise ValueError(f"unsupported tool: {name}")
        observation = self.observation()
        return {"tool": name, **result, "observation": observation,
                "simulation_time_s": float(observation["timestamp"])}

    @staticmethod
    def _outcome(outcome):
        validate_outcome(outcome)
        return {"skill_outcome": outcome.to_dict()}

    def close(self):
        if self.probe is not None:
            self.probe.clear()
        if self.mode.active:
            self.mode.exit()
