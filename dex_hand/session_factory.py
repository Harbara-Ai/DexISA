"""Offline MuJoCo embodiment binding; deliberately outside shared Runtime."""
from dex_hand.adapters import create_adapter
from dex_hand.core.scene import ScenePlan
from dex_hand.core.types import ContactGroup, PINCH_GROUPS
from dex_hand.runtime.session import RuntimeSession
from dex_hand.sim.perturbation import MujocoPerturbation
from dex_hand.sim.worlds import WorldConfig

SCENE_PLANS = {
    "wuji": ScenePlan(PINCH_GROUPS, aperture=0.04, clearance=0.012),
    "sharpa": ScenePlan(PINCH_GROUPS, aperture=0.04, clearance=0.012),
    "allegro_v5": ScenePlan(
        (ContactGroup("primary", (0, -1, 0)), ContactGroup("opposition", (0, 1, 0))),
        aperture=0.05, clearance=0.02,
    ),
    "robotiq_2f85": ScenePlan(
        (ContactGroup("primary", (1, 0, 0)), ContactGroup("opposition", (-1, 0, 0))),
        aperture=0.06, clearance=0.012,
    ),
}

def create_mujoco_session(hand):
    plan = SCENE_PLANS[hand]
    options = {"backend": "mujoco"}
    if hand in ("wuji", "sharpa"):
        options["config"] = WorldConfig()
    adapter = create_adapter(hand, **options)
    return RuntimeSession(adapter=adapter, scene_plan=plan,
                          perturbation=MujocoPerturbation(adapter))
