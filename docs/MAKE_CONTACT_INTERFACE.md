# MAKE_CONTACT implemented public interface — Phase 2

The canonical argument contract is [spec/instructions/make_contact.schema.json](../spec/instructions/make_contact.schema.json). The Runtime validates requests against its packaged mirror. The old v0.2 Markdown describes a broader historical design, not this API.

Current instruction = opcode + object/contact operands + termination. Agent-visible constraints are intentionally deferred. No speed, force, drift, travel, timeout or gain operand is accepted.

## Supported requests

```json
{"tool":"MAKE_CONTACT"}
```

```json
{
  "tool": "MAKE_CONTACT",
  "arguments": {
    "object_id": "target",
    "contact_groups": ["primary"],
    "termination": {"type": "contact_present"}
  }
}
```

```json
{
  "tool": "MAKE_CONTACT",
  "arguments": {
    "termination": {"type": "contact_dwell", "duration_s": 0.1}
  }
}
```

| Field | Meaning |
| --- | --- |
| object_id | Existing observed scene object; omission uses ScenePlan.object_id (target in supplied bindings) |
| contact_groups | Nonempty unique prepared group IDs; order retained; omission uses ScenePlan.groups |
| termination.type | contact_present (default) or contact_dwell |
| termination.duration_s | Required positive finite continuous contact duration for contact_dwell; rejected for contact_present |

An omitted or empty termination object means contact_present. All selected required groups must meet the existing contact event. There is no public require_all_groups override. Object/group availability is checked against the Adapter and prepared scene; an accepted contract does not create objects, regions or prove reachability.

## Reference execution policy and safety

The existing controller owns speed 0.008 m/s, max_displacement 0.045 m, max_load 4 N, max_object_drift 0.015 m and timeout 8 s. The resolver passes only operands and contact_dwell_s; it no longer maps Agent constraints to guard parameters. Deadline includes acquisition and dwell. Load/drift/travel/deadline, collision, source joint/actuator and backend checks are retained.

4 N is a reference load guard, not a vendor absolute hardware force limit. Adapter capability answers whether observations/groups/operations are available; it does not own controller defaults. Hard safety comes from existing source model/backend/fault protections and cannot be overridden.

contact_dwell starts its timer at the first qualifying contact observation, resets on loss, and uses simulation timestamps. It holds existing prepared servo targets while continuing guard checks. It does not establish force stability, slip stability, stable grasp, wrench feasibility or force closure. Contact loss may resume the original guarded approach; overload, collision and drift retain their existing failures.

## Explicit rejections and results

Even `{"tool":"MAKE_CONTACT","arguments":{"constraints":{}}}` returns NOT_SUPPORTED before motion. Unknown argument/termination fields and unsupported group regions also return NOT_SUPPORTED. Invalid numeric/type shape or an unknown object returns PRECONDITION_FAILED at request/availability validation. Nonfinite decoder extensions are rejected. Runtime acquisition/deadline/safety FailureClass values are unchanged.

The old pilot termination name has no compatibility alias. Direct Skill execution uses keyword-only contact_dwell_s (default zero); dwell success includes achieved_state.contact_dwell_s. Other SkillOutcome fields and CanonicalObservation are unchanged. Validation failures retain the bridge's existing status/failure_class/failure_detail response without claiming the Skill executed.

The JSONL envelope accepts only tool and optional arguments. SHAPE_HAND and MAINTAIN_GRASP keep their existing narrow arguments; no BREAK_CONTACT or APPLY_WRENCH parameterization is introduced. No operation is silently substituted or sent to a mock/hardware backend.
