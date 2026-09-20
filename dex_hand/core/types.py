from dataclasses import dataclass


@dataclass(frozen=True)
class ContactGroup:
    group_id: str
    # Object-centric outward surface normal; no finger names in the contract.
    outward: tuple[float, float, float]
    frame: str = "object"
    required: bool = True


PINCH_GROUPS = (ContactGroup("opposition", (1., 0., 0.)), ContactGroup("primary", (-1., 0., 0.)))
PRESS_GROUPS = (ContactGroup("primary", (0., -1., 0.)),)
