---
name: dexisa
description: Use the DexISA physical-interaction interface to operate one explicitly selected Wuji, Sharpa, Allegro V5 4F, or Robotiq 2F-85 embodiment in this project's offline MuJoCo simulation.
---

# DexISA

Use this skill as the **Codex client for DexISA**. DexISA exposes shared, semantic physical-interaction instructions while each selected Adapter handles embodiment-specific kinematics, contact estimation, target generation, and local control.

This skill is **offline MuJoCo only**. It must never select, invoke, or adapt a real-hardware backend.

## 1. Select the Adapter explicitly

Every DexISA session controls exactly one Adapter. The caller must explicitly select one of:

- `wuji`
- `sharpa`
- `allegro_v5`
- `robotiq_2f85`

Do not silently default to an embodiment.

The current bridge uses `--hand` as the CLI selector; treat its value as the session `adapter_id`:

```text
dexisa-mujoco --hand wuji
dexisa-mujoco --hand sharpa
dexisa-mujoco --hand allegro_v5
dexisa-mujoco --hand robotiq_2f85
```

After `python -m pip install -e .`, use `python -m dex_hand.bridge.mujoco_adapter --hand <adapter_id>` if the `dexisa-mujoco` command is not on PATH. Install and configure the external hand assets first; see `docs/ASSETS.md`.

Start one persistent bridge process per simulation session. The selected Adapter is fixed for that session. To switch embodiments, end the current bridge and start a new session with a different `adapter_id`.

If the user has not specified an embodiment and there is no active DexISA session, ask which Adapter to use rather than choosing one implicitly.

## 2. Discover the session before acting

Send one JSON object per line on stdin and read one JSON object per line on stdout.

On startup, inspect the `READY` line and capability declaration. At minimum, identify:

- selected `--hand` value, reported as `embodiment` (the session `adapter_id`)
- backend (`mujoco`, an offline simulation)
- supported Skills
- available observations
- semantic postures / grasp capabilities when exposed

Use `describe_capabilities` before relying on an embodiment-specific capability:

```json
{"tool":"describe_capabilities"}
{"tool":"get_state"}
```

The current bridge does not expose `describe_skills` or per-Skill argument schemas. Its `describe_capabilities` response reports Adapter and observation capabilities, not the accepted argument list; an Adapter may advertise an operation that this bridge does not dispatch. Check `dex_hand/bridge/mujoco_adapter.py` when arguments matter. Do not invent missing Skill arguments or silently substitute scene-specific defaults.

## 3. Call semantic, parameterized DexISA instructions

Choose Skills from the user's physical goal and the current observation. Typical operations include:

```text
SHAPE_HAND(...)
MAKE_CONTACT(...)
ESTABLISH_GRASP(...)
MAINTAIN_GRASP(...)
BREAK_CONTACT(...)
```

Skill arguments should express **task-level physical intent**, not embodiment-specific joint indices, link names, IK solutions, or controller gains.

General DexISA designs may use semantic arguments such as:

- desired posture or preshape
- object identifier
- virtual contact groups / target regions
- aperture / clearance
- required wrench or stability requirement
- task-level hold duration or release condition

**Current bridge limit:** it binds the object to `target` and selects the configured contact groups for the chosen hand. `SHAPE_HAND` accepts optional `aperture_m` and `clearance_m`; `MAINTAIN_GRASP` accepts optional `duration_s`. The other exposed Skills currently accept no task arguments and use their controller defaults. These bare calls operate only on the bridge's supported-object scene; do not present them as a general parameterized interface. If the task requires another object, target region, posture, wrench requirement, or release condition that the bridge cannot express, report the missing interface rather than pretending the fixed scene satisfies the request.

## 4. Use observations as beliefs, not raw assumptions

Inspect `observation` after actions and state queries.

Respect observation validity and provenance. In particular:

- `UNKNOWN` is not zero
- `UNAVAILABLE` is not “no contact”
- `STALE` is not a current measurement

Do not infer unavailable force, contact, object-pose, or stability values from defaults.

## 5. Handle SkillOutcome explicitly

Inspect `skill_outcome` after each Skill call.

A failed outcome must remain visible in the trace. The current bridge emits local `SkillOutcome.to_dict()` fields. Preserve and use:

- `status`
- `failure_class`
- `failure_detail`
- `achieved_state`
- `residual_uncertainty`
- `diagnostics`

The draft ISA wire fields `achieved`, `belief_updates`, `local_recovery_applied`, `suggested_recovery`, and `adapter_diagnostics` are not emitted by this bridge. Do not infer values for them from absent fields.

Do not silently replace a failed action with another action as though the failure had not occurred.

A failure is not automatically terminal. If the task remains recoverable, choose an explicit recovery action from the current observation and failure semantics. For example, a grasp precondition failure may justify establishing contact and then retrying the grasp.

Treat `NOT_SUPPORTED` as a capability result. Do not emulate an unsupported Skill with a different hidden operation.

`diagnostics` is debugging information only. Do not build cross-embodiment task logic around vendor-specific or embodiment-specific diagnostic fields.

## 6. Do not impose a fixed Skill sequence

Do **not** require a fixed sequence such as:

```text
SHAPE_HAND -> MAKE_CONTACT -> ESTABLISH_GRASP -> MAINTAIN_GRASP -> BREAK_CONTACT
```

unless the user's task itself requires those intermediate physical conditions.

Choose actions from the current state. Individual Skills may enforce their own preconditions and return structured failures.

A successful Skill call is not by itself proof that the user's overall manipulation task succeeded. Judge the terminal task from the requested physical outcome and current state; when an external task evaluator is available, use that evaluator rather than Agent text or a Skill's self-report.

## 7. MAINTAIN_GRASP semantics

`MAINTAIN_GRASP` represents local persistent closed-loop grasp maintenance. The Agent must not perform millisecond-scale slip or force regulation itself.

If the current MuJoCo bridge exposes:

```json
{"tool":"MAINTAIN_GRASP","arguments":{"duration_s":0.3}}
```

treat it as a **bounded simulation wrapper over the persistent MAINTAIN_GRASP mode**, not as evidence that grasp maintenance is an open-loop one-shot action.

## 8. Session discipline

Keep one persistent bridge alive for the interaction so state, object dynamics, and controller state remain continuous.

Before changing to another embodiment, close the existing session and start a new one explicitly.

Do not use this skill for benchmark scoring, token accounting, Direct-Agent comparison, or real-hardware control. Those concerns belong outside the DexISA control interface.
