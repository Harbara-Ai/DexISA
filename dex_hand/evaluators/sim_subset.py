"""Read-only evaluator for the common supported-object Skill subset.

Uses the existing shared Skill thresholds; never commands the adapter.
"""
import numpy as np


def evaluate(adapter, stage, groups, *, reference=None, mode=None, shape_site_targets=None):
    o=adapter.build_canonical_observation()
    required={g.group_id for g in groups if g.required}
    loads={g:sum(c.normal_load.value for c in o.contacts if c.contact_group_id==g) for g in required}
    present={c.contact_group_id for c in o.contacts}
    object_state=o.objects.get('target')
    drift=(float(np.linalg.norm(np.asarray(object_state.relative_pose.value.position)-reference))
           if reference is not None and object_state and object_state.relative_pose.valid else None)
    base=(not o.hand.collision.value and not (present-required) and
          all(v<=4 for v in loads.values()) and (drift is None or drift<=.015))
    if stage=='SHAPE_HAND':
        shape_error=(max(float(np.linalg.norm(adapter.data.site_xpos[adapter.sites[g.group_id]]-
                            shape_site_targets[g.group_id])) for g in groups)
                     if shape_site_targets is not None else adapter.configuration_error())
        passed=base and not present and shape_error<.002
    elif stage=='MAKE_CONTACT':
        passed=base and required<=present and all(loads[g]>1e-5 for g in required)
    elif stage=='ESTABLISH_GRASP':
        vel=object_state.relative_velocity.value if object_state else None
        passed=base and required<=present and all(loads[g]>=.15 for g in required) and (
            vel is not None and np.linalg.norm(vel['linear'])<.015 and
            np.linalg.norm(vel['angular'])<.5 and drift is not None and drift<.008)
    elif stage=='MAINTAIN_GRASP':
        passed=(base and required<=present and all(loads[g]>=.02 for g in required)
                and drift is not None and drift<=.012 and (mode is None or mode.query()['health']!='CRITICAL'))
    elif stage=='BREAK_CONTACT':
        passed=base and not present and object_state is not None and object_state.support.valid and object_state.support.value
    else:
        raise ValueError(stage)
    return {'stage':stage,'pass':bool(passed),'time_s':o.timestamp,
            'groups_present':sorted(present),'group_loads_N':loads,
            'object_drift_m':drift,'collision':o.hand.collision.value,
            'supported':object_state.support.value if object_state and object_state.support.valid else None,
            'configuration_error_m':shape_error if stage=='SHAPE_HAND' else None}
