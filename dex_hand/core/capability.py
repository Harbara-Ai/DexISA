from dataclasses import dataclass
from enum import StrEnum
from .observation import Method


class Availability(StrEnum):
    ALWAYS = "ALWAYS"
    CONDITIONAL = "CONDITIONAL"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class ObservationCapability:
    availability: Availability
    method: Method
    nominal_rate_hz: float
    nominal_latency_ms: float
    provenance: tuple[str, ...]


OBSERVABLES = ("joint_position joint_velocity joint_effort contact_presence contact_position "
               "contact_normal normal_load tangential_load contact_motion_state object_pose "
               "object_velocity object_relative_pose object_relative_velocity object_slip "
               "interaction_wrench grasp_state task_wrench_margin").split()


def mujoco_capabilities(rate):
    result = {}
    for name in OBSERVABLES:
        unavailable = name in ("contact_motion_state", "object_slip", "task_wrench_margin")
        contact = name.startswith("contact_") or name in ("normal_load", "tangential_load", "interaction_wrench")
        result[name] = ObservationCapability(
            Availability.UNAVAILABLE if unavailable else Availability.CONDITIONAL if contact or name == "grasp_state" else Availability.ALWAYS,
            Method.ESTIMATED if name == "grasp_state" or unavailable else Method.DERIVED if name in ("interaction_wrench", "object_relative_pose", "object_relative_velocity", "tangential_load") else Method.DIRECT,
            0 if unavailable else rate, 0, ("NOT_ESTIMATED" if unavailable else "BASELINE_STATIC_V1" if name == "grasp_state" else "SIM_CONTACT" if contact else "SIM_STATE",))
    return result
