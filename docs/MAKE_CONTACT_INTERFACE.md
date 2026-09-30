# MAKE_CONTACT JSONL pilot

This is the implemented Phase 1 reference subset. It reuses dex_hand/skills/make_contact.py and Adapter primitives. It is distinct from the broader [normative draft schema](../spec/instructions/make_contact.schema.json).

## Legacy compatibility

`{"tool":"MAKE_CONTACT"}` and empty arguments resolve to `target` and the existing selected-hand scene plan. Controller defaults are unchanged: speed 0.008 m/s, displacement 0.045 m, group load 4 N, object relative drift 0.015 m, deadline 8 s, all required groups, immediate contact-event termination. They come from the Skill signature, not duplicated bridge constants.

## Parameterized request

```json
{
  "tool": "MAKE_CONTACT",
  "arguments": {
    "object_id": "target",
    "contact_groups": ["primary", "opposition"],
    "constraints": {
      "max_normal_force_n": 2.0,
      "max_object_drift_m": 0.002,
      "forbid_unplanned_contact": true
    },
    "termination": {"type": "contact_stable", "duration_s": 0.1}
  }
}
```

| Field | Supported meaning |
| --- | --- |
| object_id | Existing observed scene object; current scenes have only target |
| contact_groups | Nonempty unique IDs from the session's existing region plan; order retained; omission keeps whole plan |
| constraints.max_normal_force_n | Positive per-contact-group summed normal load; may tighten 4 N reference envelope |
| constraints.max_object_drift_m | Nonnegative displacement of canonical relative object position from the instruction-entry reference; may tighten 0.015 m |
| constraints.max_displacement_m | Nonnegative commanded inward displacement budget per group; may tighten 0.045 m |
| constraints.timeout_s | Positive total simulation deadline including acquisition and requested dwell; may tighten 8 s |
| constraints.forbid_unplanned_contact | Only true is supported; existing nonparticipating-contact rejection is retained |
| termination.type | contact_present (default) or contact_stable |
| termination.duration_s | Required positive continuous dwell for contact_stable; rejected for contact_present |
| termination.require_all_groups | Boolean, default true; false uses existing any-required-group event |

Contact_stable means continuously observed requested contact presence while existing collision/load/drift guards remain satisfied. It does **not** mean stable grasp, frictional wrench feasibility, force closure or a task score. The dwell timer starts at the first qualifying observation, resets on loss, and counts actual simulation timestamps. It does not regulate grasp force. Prepared servo targets remain active during dwell; this can legitimately produce a constraint failure.

Numeric bounds must be finite JSON numbers (booleans/strings rejected). The pilot cannot relax the reference envelope, unplanned-contact check, source actuator limits or collision guards. The 4 N reference envelope is not presented as a vendor absolute force rating. Existing direct Python APIs are unchanged except an optional keyword-only contact_stable_s with default zero.

## Explicit limitations and failures

Unknown tool/argument/constraint/termination or unsupported scene region: NOT_SUPPORTED. Unknown observed object or invalid numeric/envelope shape: PRECONDITION_FAILED at transport validation. Runtime acquisition, collision, overload, drift and deadline keep their existing FailureClass values. Validation is completed before motion. A failed request is never substituted with a different operation or mock backend.

Direction vectors, new target regions, internal gains/speeds and unimplemented draft fields are not accepted. SHAPE_HAND still accepts aperture_m/clearance_m; MAINTAIN_GRASP still accepts duration_s. ESTABLISH_GRASP and BREAK_CONTACT keep their legacy bare calls in this phase. Arbitrary object selection does not create new scene objects.

The JSONL envelope accepts tool and optional arguments only. Extra envelope fields now fail explicitly rather than being silently ignored. Results retain the existing local SkillOutcome dictionary and canonical observation; the new dwell success adds contact_stable_s to achieved_state. Validation errors retain the existing bridge failure response shape (status, failure_class, failure_detail), without pretending the instruction ran.
