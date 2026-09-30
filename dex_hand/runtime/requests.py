"""Resolve MAKE_CONTACT intent into the existing reference Skill arguments.

The legacy Skill signature owns defaults. This path may only tighten its
reference bounds; it does not claim a vendor absolute contact-force rating.
"""
from dataclasses import dataclass
from inspect import signature
import math
from dex_hand.core.outcome import AdapterError, FailureClass as F
from dex_hand.skills.make_contact import MakeContact

MAKE_CONTACT_KEYS={"object_id","contact_groups","constraints","termination"}
CONSTRAINT_FIELDS={"max_normal_force_n":"max_load","max_object_drift_m":"max_object_drift",
                   "max_displacement_m":"max_displacement","timeout_s":"timeout"}

def _fields(value,allowed,label):
    if not isinstance(value,dict):
        raise ValueError(label+" must be a JSON object")
    unknown=set(value)-allowed
    if unknown:
        raise AdapterError(F.NOT_SUPPORTED,"unsupported "+label+": "+', '.join(sorted(unknown)))
    return value

def _number(value,label,*,zero=False):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError(label+" must be a finite number")
    if value<0 or (not zero and value==0):
        raise ValueError(label+" must be "+("nonnegative" if zero else "positive"))
    return float(value)

@dataclass(frozen=True)
class ResolvedMakeContact:
    object_id: str
    groups: tuple
    parameters: dict

    def execute(self,adapter):
        return MakeContact(adapter).run(self.object_id,self.groups,**self.parameters)

def resolve_make_contact(request,adapter,default_groups):
    args=_fields(request.arguments,MAKE_CONTACT_KEYS,"MAKE_CONTACT arguments")
    object_id=args.get("object_id","target")
    if not isinstance(object_id,str) or not object_id:
        raise ValueError("object_id must be a nonempty string")
    observation=adapter.build_canonical_observation()
    if object_id not in observation.objects:
        raise AdapterError(F.PRECONDITION_FAILED,"unknown object: "+object_id)
    group_ids=args.get("contact_groups",[g.group_id for g in default_groups])
    if (not isinstance(group_ids,list) or not group_ids or
            any(not isinstance(g,str) or not g for g in group_ids) or len(set(group_ids))!=len(group_ids)):
        raise ValueError("contact_groups must be nonempty unique group IDs")
    plan={g.group_id:g for g in default_groups}
    missing=set(group_ids)-set(plan)
    if missing:
        raise AdapterError(F.NOT_SUPPORTED,"no prepared scene region for groups: "+', '.join(sorted(missing)))
    groups=tuple(plan[g] for g in group_ids)
    for group in groups:
        adapter.resolve_contact_group(group)
    constraints=_fields(args.get("constraints",{}),set(CONSTRAINT_FIELDS)|{"forbid_unplanned_contact"},"constraints")
    parameters={}
    defaults=signature(MakeContact.run).parameters
    for public,private in CONSTRAINT_FIELDS.items():
        if public not in constraints:continue
        value=_number(constraints[public],public,zero=private in {"max_displacement","max_object_drift"})
        if value>defaults[private].default:
            raise ValueError(public+" may only tighten the existing reference envelope")
        parameters[private]=value
    if "forbid_unplanned_contact" in constraints and constraints["forbid_unplanned_contact"] is not True:
        raise AdapterError(F.NOT_SUPPORTED,"unplanned-contact rejection cannot be disabled")
    termination=_fields(args.get("termination",{}),{"type","duration_s","require_all_groups"},"termination")
    kind=termination.get("type","contact_present")
    if kind not in ("contact_present","contact_stable"):
        raise AdapterError(F.NOT_SUPPORTED,"unsupported contact termination: "+str(kind))
    if "require_all_groups" in termination:
        if not isinstance(termination["require_all_groups"],bool):
            raise ValueError("require_all_groups must be boolean")
        parameters["require_all_groups"]=termination["require_all_groups"]
    if kind=="contact_stable":
        if "duration_s" not in termination:
            raise ValueError("contact_stable requires duration_s")
        parameters["contact_stable_s"]=_number(termination["duration_s"],"duration_s")
    elif "duration_s" in termination:
        raise AdapterError(F.NOT_SUPPORTED,"duration_s requires contact_stable termination")
    return ResolvedMakeContact(object_id,groups,parameters)
