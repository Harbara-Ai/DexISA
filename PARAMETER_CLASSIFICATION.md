# Parameter classification — source baseline

A = task operand; B = execution constraint; C = termination; D = runtime default; E = private controller/Adapter realization; F = retained hard invariant. A/B/C classification does not mean every field is exposed by the current bridge. D labels the fallback value independently of the parameter role.

| Entry point | Parameter | Role | Existing fallback |
| --- | --- | --- | --- |
| skills/apply_wrench.py:run | `object_id` | A | required |
| skills/apply_wrench.py:run | `groups` | A | required |
| skills/apply_wrench.py:run | `target_force` | A | D: `1.8` |
| skills/apply_wrench.py:run | `max_load` | B | D: `3.0` |
| skills/apply_wrench.py:run | `termination` | C | D: `'activation'` |
| skills/apply_wrench.py:run | `target_displacement` | C | D: `0.008` |
| skills/apply_wrench.py:run | `max_displacement` | B | D: `0.025` |
| skills/apply_wrench.py:run | `timeout` | B | D: `6.0` |
| skills/apply_wrench.py:run | `force_tolerance` | C | D: `0.05` |
| skills/break_contact.py:run | `object_id` | A | required |
| skills/break_contact.py:run | `groups` | A | required |
| skills/break_contact.py:run | `support_state` | A | D: `'SURFACE'` |
| skills/break_contact.py:run | `allow_drop` | A | D: `False` |
| skills/break_contact.py:run | `mode` | A | D: `'GRADUAL'` |
| skills/break_contact.py:run | `retreat` | C | D: `0.012` |
| skills/break_contact.py:run | `speed` | E | D: `0.006` |
| skills/break_contact.py:run | `max_object_drift` | B | D: `0.015` |
| skills/break_contact.py:run | `timeout` | B | D: `5.0` |
| skills/establish_grasp.py:run | `object_id` | A | required |
| skills/establish_grasp.py:run | `groups` | A | required |
| skills/establish_grasp.py:run | `minimum_load` | C | D: `0.15` |
| skills/establish_grasp.py:run | `target_load` | A | D: `0.6` |
| skills/establish_grasp.py:run | `max_load` | B | D: `4.0` |
| skills/establish_grasp.py:run | `timeout` | B | D: `5.0` |
| skills/establish_grasp.py:run | `required_wrench_set` | A | D: `None` |
| skills/make_contact.py:run | `object_id` | A | required |
| skills/make_contact.py:run | `groups` | A | required |
| skills/make_contact.py:run | `speed` | E | D: `0.008` |
| skills/make_contact.py:run | `max_displacement` | B | D: `0.045` |
| skills/make_contact.py:run | `max_load` | B | D: `4.0` |
| skills/make_contact.py:run | `require_all_groups` | C | D: `True` |
| skills/make_contact.py:run | `max_object_drift` | B | D: `0.015` |
| skills/make_contact.py:run | `timeout` | B | D: `8.0` |
| skills/make_contact.py:run | `approach_frame` | A | D: `'object'` |
| skills/make_contact.py:run | `direction` | A | D: `None` |
| skills/shape_hand.py:run | `object_id` | A | required |
| skills/shape_hand.py:run | `groups` | A | required |
| skills/shape_hand.py:run | `profile` | A | D: `'PRESHAPE'` |
| skills/shape_hand.py:run | `aperture` | A | D: `0.04` |
| skills/shape_hand.py:run | `clearance` | B | D: `0.012` |
| skills/shape_hand.py:run | `timeout` | B | D: `3.0` |
| skills/shape_posture.py:shape_hand | `goal` | A | required |
| skills/shape_posture.py:shape_hand | `speed_scale` | A | D: `0.5` |
| skills/shape_posture.py:shape_hand | `abort_on_contact` | B | D: `True` |
| skills/shape_posture.py:shape_hand | `timeout_s` | B | D: `8.0` |
| skills/shape_posture.py:shape_hand | `**runtime` | E; backend-specific forwarding, not arbitrary ISA operands | none |
| modes/maintain_grasp.py:enter | `object_id` | A | required |
| modes/maintain_grasp.py:enter | `groups` | A | required |
| modes/maintain_grasp.py:enter | `target_load` | A | D: `0.6` |
| modes/maintain_grasp.py:enter | `max_load` | B | D: `4.0` |
| modes/maintain_grasp.py:enter | `max_drift` | B | D: `0.012` |
| modes/maintain_grasp.py:enter | `recovery_budget` | B | D: `0.015` |
| modes/maintain_grasp.py:update | `target_load` | A | D: `None` |
| modes/maintain_grasp.py:update | `max_drift` | B | D: `None` |

## Interpretation and invariants

- MAKE_CONTACT speed is the current private guarded-approach realization (draft has approach.speed_m_s, but this pilot does not expose controller tuning). max_displacement, max_load, max_object_drift and timeout are task constraints; require_all_groups is contact event termination. Frame/direction are operands but non-default forms are explicitly unsupported.
- ESTABLISH_GRASP minimum_load defines BASELINE_STATIC_V1 acceptance, not an arbitrary wrench guarantee. target_load is desired preload; actual regulation gain/clamps are E. required_wrench_set remains NOT_SUPPORTED.
- MAINTAIN_GRASP target_load is interaction intent; max_load/max_drift/recovery_budget are bounded maintenance constraints. Mode update may tighten drift only. They are not evaluation hold duration.
- BREAK_CONTACT support/drop are task support intent/authorization. The no-drop observed-support check is a retained F conditional guard; do not weaken it. Retreat is a reference termination target. Speed is private.
- APPLY_WRENCH target force is task intent; activation/force/displacement select termination. Force dwell 0.04 s is D reference implementation; admittance gain 0.012 and rate clamps are E.
- ShapeHand configuration tolerance 0.002 m and BreakContact clear dwell 0.1 s are existing D reference semantics, independently of evaluation rules with the same numbers. No consolidation in Phase 1.
- F: source joint ranges/actuator effort limits, forbidden collision handling, explicit backend faults and finite-state checks in Adapter.step. No vendor absolute contact-force rating is inferred from the runtime 4 N default.
- E: IK iterations, residual thresholds, morphology normals/sites/mimic projection, gains and per-step increments remain untouched.
- The new MAKE_CONTACT pilot accepts only object/group operands, bounded constraint fields and contact_present/contact_stable termination. Legacy defaults continue to come from the existing Skill signature.
