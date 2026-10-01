"""Prepared scene operands chosen by bootstrap, consumed by shared runtime."""
from dataclasses import dataclass
from dex_hand.core.types import ContactGroup

@dataclass(frozen=True)
class ScenePlan:
    groups: tuple[ContactGroup, ...]
    aperture: float
    clearance: float
    object_id: str = "target"
