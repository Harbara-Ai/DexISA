"""Resolve object/group/termination operands; reference guards stay in the Skill."""
from dataclasses import dataclass
import math
from jsonschema.exceptions import ValidationError
from dex_hand.core.instruction_schema import MAKE_CONTACT_SCHEMA, MAKE_CONTACT_VALIDATOR
from dex_hand.core.outcome import AdapterError, FailureClass as F
from dex_hand.core.scene import ScenePlan
from dex_hand.skills.make_contact import MakeContact

MAKE_CONTACT_KEYS=set(MAKE_CONTACT_SCHEMA["properties"])

def _fields(value,allowed,label):
    if not isinstance(value,dict):
        raise ValueError(label+" must be a JSON object")
    unknown=set(value)-allowed
    if unknown:
        raise AdapterError(F.NOT_SUPPORTED,"unsupported "+label+": "+', '.join(sorted(unknown)))
    return value

@dataclass(frozen=True)
class ResolvedMakeContact:
    object_id: str
    groups: tuple
    contact_dwell_s: float = 0.

    def execute(self,adapter):
        # No Agent-to-guard mapping: all reference defaults remain Skill-owned.
        return MakeContact(adapter).run(self.object_id,self.groups,
                                        contact_dwell_s=self.contact_dwell_s)

def resolve_make_contact(request,adapter,scene_plan: ScenePlan):
    args=_fields(request.arguments,MAKE_CONTACT_KEYS,"MAKE_CONTACT arguments")
    termination=_fields(args.get("termination",{}),{"type","duration_s"},"termination")
    kind=termination.get("type","contact_present")
    if kind not in ("contact_present","contact_dwell"):
        raise AdapterError(F.NOT_SUPPORTED,"unsupported contact termination: "+str(kind))
    if kind=="contact_present" and "duration_s" in termination:
        raise AdapterError(F.NOT_SUPPORTED,"duration_s requires contact_dwell termination")
    try:
        MAKE_CONTACT_VALIDATOR.validate(args)
    except ValidationError as exc:
        raise ValueError("invalid MAKE_CONTACT arguments: "+exc.message) from exc
    dwell=0.
    if kind=="contact_dwell":
        try:
            dwell=float(termination["duration_s"])
        except OverflowError as exc:
            raise ValueError("duration_s must be finite") from exc
        if not math.isfinite(dwell):
            raise ValueError("duration_s must be finite")
    object_id=args.get("object_id",scene_plan.object_id)
    observation=adapter.build_canonical_observation()
    if object_id not in observation.objects:
        raise AdapterError(F.PRECONDITION_FAILED,"unknown object: "+object_id)
    group_ids=args.get("contact_groups",[g.group_id for g in scene_plan.groups])
    plan={g.group_id:g for g in scene_plan.groups}
    missing=set(group_ids)-set(plan)
    if missing:
        raise AdapterError(F.NOT_SUPPORTED,"no prepared scene region for groups: "+', '.join(sorted(missing)))
    groups=tuple(plan[g] for g in group_ids)
    for group in groups:
        adapter.resolve_contact_group(group)
    return ResolvedMakeContact(object_id,groups,dwell)
