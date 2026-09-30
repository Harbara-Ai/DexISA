from dataclasses import dataclass, field, asdict
from enum import StrEnum
from typing import Generic, TypeVar
import math

T = TypeVar("T")


class ValueStatus(StrEnum):
    VALID = "VALID"
    UNKNOWN = "UNKNOWN"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


class Method(StrEnum):
    DIRECT = "DIRECT"
    ESTIMATED = "ESTIMATED"
    DERIVED = "DERIVED"
    FUSED = "FUSED"


class ContactMotionState(StrEnum):
    STICK="STICK"
    SLIDE="SLIDE"
    ROLL="ROLL"
    SEPARATING="SEPARATING"
    UNKNOWN="UNKNOWN"


class GraspState(StrEnum):
    STABLE="STABLE"
    MARGINAL="MARGINAL"
    UNSTABLE="UNSTABLE"
    UNKNOWN="UNKNOWN"


@dataclass(frozen=True)
class ObservedValue(Generic[T]):
    status: ValueStatus
    value: T | None
    method: Method = Method.DERIVED
    confidence: float = 0.0
    sample_time: float = 0.0
    provenance: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self,"status",ValueStatus(self.status))
        object.__setattr__(self,"method",Method(self.method))
        if not math.isfinite(self.sample_time):raise ValueError("sample_time must be finite")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be in [0,1]")
        if self.status == ValueStatus.VALID and self.value is None:
            raise ValueError("VALID requires a value")
        if self.status in (ValueStatus.UNKNOWN, ValueStatus.UNAVAILABLE) and self.value is not None:
            raise ValueError("UNKNOWN/UNAVAILABLE cannot masquerade as a numeric or boolean value")

    @property
    def valid(self):
        return self.status == ValueStatus.VALID


def known(value, time, source="SIM_STATE", method=Method.DIRECT, confidence=1.0):
    return ObservedValue(ValueStatus.VALID, value, method, confidence, time, (source,))


def unknown(time, source="NOT_ESTIMATED", unavailable=False):
    return ObservedValue(ValueStatus.UNAVAILABLE if unavailable else ValueStatus.UNKNOWN, None,
                         Method.ESTIMATED, 0, time, (source,))


@dataclass(frozen=True)
class Pose:
    frame: str
    position: list[float]
    quaternion_wxyz: list[float]


@dataclass
class ContactObservation:
    contact_id: str
    contact_group_id: str
    object_id: str
    presence: ObservedValue
    position: ObservedValue  # {frame, xyz}, m
    normal: ObservedValue    # {frame, xyz}, hand -> object
    normal_load: ObservedValue  # N
    tangential_load: ObservedValue  # {frame, xyz}, N
    motion_state: ObservedValue


@dataclass
class ObjectObservation:
    pose: ObservedValue
    velocity: ObservedValue
    relative_pose: ObservedValue
    relative_velocity: ObservedValue
    displacement: ObservedValue
    activated: ObservedValue
    support: ObservedValue


@dataclass
class HandObservation:
    joint_position: ObservedValue
    joint_velocity: ObservedValue
    joint_effort: ObservedValue
    actuator_saturated: ObservedValue
    collision: ObservedValue


@dataclass
class InteractionObservation:
    object_slip: ObservedValue
    interaction_wrench: ObservedValue


@dataclass
class GraspObservation:
    state: ObservedValue
    task_wrench_margin: ObservedValue


@dataclass
class CanonicalObservation:
    timestamp: float
    hand: HandObservation
    contacts: list[ContactObservation]
    objects: dict[str, ObjectObservation]
    interaction: InteractionObservation
    grasp: GraspObservation
    active_modes: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)
