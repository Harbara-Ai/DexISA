"""Persistent, simulation-only JSONL bridge to the project's four DexISA adapters."""

import argparse
import json
import math
import sys
from dex_hand.adapters import create_adapter
from dex_hand.core.outcome import AdapterError, FailureClass, SkillOutcome
from dex_hand.core.schema import validate_outcome
from dex_hand.core.types import ContactGroup, PINCH_GROUPS
from dex_hand.modes.maintain_grasp import MaintainGrasp
from dex_hand.sim.perturbation import MujocoPerturbation
from dex_hand.sim.worlds import WorldConfig
from dex_hand.skills.break_contact import BreakContact
from dex_hand.skills.establish_grasp import EstablishGrasp
from dex_hand.skills.make_contact import MakeContact
from dex_hand.skills.shape_hand import ShapeHand


HANDS = {
    "wuji": {"groups": PINCH_GROUPS, "aperture": 0.04, "clearance": 0.012},
    "sharpa": {"groups": PINCH_GROUPS, "aperture": 0.04, "clearance": 0.012},
    "allegro_v5": {
        "groups": (ContactGroup("primary", (0, -1, 0)), ContactGroup("opposition", (0, 1, 0))),
        "aperture": 0.05,
        "clearance": 0.02,
    },
    "robotiq_2f85": {
        "groups": (ContactGroup("primary", (1, 0, 0)), ContactGroup("opposition", (-1, 0, 0))),
        "aperture": 0.06,
        "clearance": 0.012,
    },
}


ARGUMENT_KEYS = {
    "get_state": {"wait_s"},
    "describe_capabilities": set(),
    "SHAPE_HAND": {"aperture_m", "clearance_m"},
    "MAKE_CONTACT": set(),
    "ESTABLISH_GRASP": set(),
    "MAINTAIN_GRASP": {"duration_s"},
    "BREAK_CONTACT": set(),
}


class Session:
    def __init__(self, hand):
        self.hand = hand
        self.plan = HANDS[hand]
        options = {"backend": "mujoco"}
        if hand in ("wuji", "sharpa"):
            options["config"] = WorldConfig()
        self.adapter = create_adapter(hand, **options)
        self.probe = MujocoPerturbation(self.adapter)
        self.mode = MaintainGrasp(self.adapter)

    def observation(self):
        return self.adapter.build_canonical_observation().to_dict()

    def execute(self, request):
        if not isinstance(request, dict):
            raise ValueError("request must be a JSON object")
        name = request.get("tool")
        args = request.get("arguments", {})
        if not isinstance(args, dict):
            raise ValueError("arguments must be a JSON object")
        if name not in ARGUMENT_KEYS:
            raise AdapterError(FailureClass.NOT_SUPPORTED, f"unsupported tool: {name}")
        unsupported = set(args) - ARGUMENT_KEYS[name]
        if unsupported:
            raise AdapterError(FailureClass.NOT_SUPPORTED,
                               f"unsupported arguments for {name}: {', '.join(sorted(unsupported))}")
        groups = self.plan["groups"]
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
                "target", groups,
                aperture=float(args.get("aperture_m", self.plan["aperture"])),
                clearance=float(args.get("clearance_m", self.plan["clearance"])),
            )
            result = self._outcome(outcome)
        elif name == "MAKE_CONTACT":
            result = self._outcome(MakeContact(adapter).run("target", groups))
        elif name == "ESTABLISH_GRASP":
            result = self._outcome(EstablishGrasp(adapter, self.probe).run("target", groups))
        elif name == "MAINTAIN_GRASP":
            duration = float(args.get("duration_s", 0.3))
            if not math.isfinite(duration) or duration <= 0:
                raise ValueError("duration_s must be finite and positive")
            outcome = self.mode.enter("target", groups)
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
            result = self._outcome(BreakContact(adapter).run("target", groups))
        else:
            raise ValueError(f"unsupported tool: {name}")
        return {"tool": name, **result, "observation": self.observation(),
                "simulation_time_s": float(adapter.data.time)}

    @staticmethod
    def _outcome(outcome):
        validate_outcome(outcome)
        return {"skill_outcome": outcome.to_dict()}

    def close(self):
        self.probe.clear()
        if self.mode.active:
            self.mode.exit()


def emit(value):
    print(json.dumps(value, ensure_ascii=False, default=str), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hand", required=True, choices=tuple(HANDS))
    hand = parser.parse_args().hand
    try:
        session = Session(hand)
    except (AdapterError, FileNotFoundError, ValueError) as exc:
        emit({"status": "FAILED", "failure_class": getattr(exc, "failure_class", "NOT_SUPPORTED"),
              "failure_detail": str(exc), "embodiment": hand})
        return 1
    emit({"status": "READY", "embodiment": hand, "backend": "mujoco",
          "capabilities": session.adapter.get_capabilities()})
    try:
        for line in sys.stdin:
            try:
                response = session.execute(json.loads(line))
            except (AdapterError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                response = {"status": "FAILED", "failure_class": getattr(exc, "failure_class", "PRECONDITION_FAILED"),
                            "failure_detail": str(exc)}
            except Exception as exc:
                session.adapter.safe_hold()
                response = {"status": "FAILED", "failure_class": "SIMULATION_ERROR",
                            "failure_detail": f"{type(exc).__name__}: {exc}"}
            emit(response)
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
