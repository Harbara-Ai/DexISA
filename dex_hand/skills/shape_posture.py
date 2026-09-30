"""Additive v0.2 posture entry point. No device identifiers or vendor SDK.

The existing object-conditioned ShapeHand.run and all shared schemas remain
unchanged. Backends implement execute_posture; unsupported goals fail closed.
"""
from dex_hand.core.outcome import SkillOutcome, FailureClass as F


def shape_hand(adapter, *, goal, speed_scale=.5, abort_on_contact=True, timeout_s=8., **runtime):
    if not isinstance(goal,dict) or set(goal)!={"type","semantic"} or goal["type"]!="posture":
        return SkillOutcome("FAILED","SHAPE_HAND",F.NOT_SUPPORTED,"This entry point implements semantic posture only")
    if not isinstance(goal["semantic"],str) or not callable(getattr(adapter,"execute_posture",None)):
        return SkillOutcome("FAILED","SHAPE_HAND",F.NOT_SUPPORTED,"Backend does not support semantic posture")
    if adapter.active_modes:
        return SkillOutcome("FAILED","SHAPE_HAND",F.PRECONDITION_FAILED,"Conflicting persistent mode")
    return adapter.execute_posture(goal["semantic"],speed_scale=speed_scale,timeout_s=timeout_s,
                                   abort_on_contact=abort_on_contact,**runtime)
