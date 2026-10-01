# Phase 2 architecture repair results

Date: 2026-10-01 (Asia/Singapore). Baseline: Harbara-Ai/DexISA_v2 main `f830b3d56edeaceae83b34ca9bd64b8574d46dbe`, verified equal to remote main before edits. Work was limited to runtime binding, the implemented MAKE_CONTACT contract, internal parameter ownership and dwell naming. The original DexISA repository remains read-only.

**No intentional physical-control semantic changes in Phase 2.**

**Evaluation architecture and task semantics were intentionally left unchanged.**

## 1. Responsibilities removed from Runtime

Removed the HANDS morphology/scene table, concrete Adapter creation, hand-name branches, WorldConfig construction and MuJoCo perturbation construction from dex_hand/runtime/session.py. Runtime no longer owns a hand selector or accesses Adapter model/data state for its clock; it reads CanonicalObservation.timestamp instead.

The shared runtime still owns validate/resolve/execute/monitor/termination/outcome semantics, existing Skill construction and the existing persistent MAINTAIN_GRASP mode. No second execution implementation or framework was added. An architecture test prevents concrete hand identifiers, Adapter creation, scene/bootstrap imports and backend model/data access from returning to dex_hand/runtime/.

## 2. Bootstrap and ScenePlan

`dex_hand/session_factory.py` now contains SCENE_PLANS and `create_mujoco_session(hand)`. It creates the existing concrete Adapter with backend=mujoco, preserves the same WorldConfig choice, group normals, aperture, clearance and object binding, constructs existing perturbation apparatus, and injects them into RuntimeSession.

`dex_hand/core/scene.py` defines a frozen ScenePlan: groups, aperture, clearance, object_id. Bootstrap chooses it; Runtime only consumes it. This is prepared binding data, not a scene description language. All four existing hand IDs remain supported through the factory; no mock fallback or asset copy is introduced.

## 3. New Runtime construction / Bridge

```python
from dex_hand.runtime.session import RuntimeSession

session = RuntimeSession(adapter=adapter, scene_plan=scene_plan,
                         perturbation=perturbation)
```

The Adapter and ScenePlan are supplied by the caller. Perturbation may be omitted; the unchanged grasp Skill then reports NOT_SUPPORTED when certification apparatus is unavailable. Runtime does not create backend-specific helpers.

Deployment uses `create_mujoco_session("wuji")` outside Runtime, or the unchanged `dexisa-mujoco --hand wuji` CLI. Bridge still only handles startup selection, JSON parsing, InstructionRequest, runtime invocation and serialization. The bridge Session(hand) convenience delegates to the factory; Phase 1 runtime Session(hand) is replaced with RuntimeSession. Runtime imports no factory to preserve that obsolete constructor.

## 4. Canonical public MAKE_CONTACT contract

Only object_id, contact_groups and termination are exposed in arguments:

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

Bare `{"tool":"MAKE_CONTACT"}` remains supported: injected scene object/groups and contact_present termination. Empty/omitted termination retains the same immediate event behavior. All selected required groups use the existing internal require_all_groups=True policy. Public group IDs must be nonempty, unique and present in the prepared plan; object existence and group resolution remain dynamic Adapter/binding checks.

## 5. Public fields removed; guard ownership retained

Removed the constraints object and its max_normal_force_n, max_object_drift_m, max_displacement_m, timeout_s and forbid_unplanned_contact mappings. Even an empty constraints object returns NOT_SUPPORTED before motion. The pilot's public require_all_groups override is also removed so termination has only the current declared forms. Force, drift, travel, timeout, speed, gains and arbitrary approach/target-region fields are not public operands.

ResolvedMakeContact now carries only object_id, groups and contact_dwell_s. It invokes the existing MakeContact.run without forwarding any reference guard override.

| Owner | Current responsibility |
| --- | --- |
| Agent | Interaction choice, object/group operands, termination |
| Reference Runtime / Skill | Speed 0.008 m/s, displacement 0.045 m, load guard 4 N, relative drift guard 0.015 m, deadline 8 s; same execution/failure behavior |
| Adapter capability | Available/unavailable observation, resolvable object/group and supported operation; not controller defaults |
| Hard safety | Unchanged source joint/actuator limits, collision handling and backend fault checks; not Agent-overridable |

4 N is a reference runtime guard, **not a vendor hardware absolute limit**. max_load/max_object_drift/max_displacement/timeout, the nonparticipating-contact guard and all retained collision/model/backend protections remain. Direct engineering Skill APIs retain their internal guard parameters. No generic constraints framework or additional numeric margin was created.

Generic Agent-visible execution constraints are intentionally deferred until more complex deployment scenarios provide concrete requirements.

## 6. Termination naming

The Phase 1 pilot name contact_stable is replaced by contact_dwell. Internal keyword and success metadata contact_stable_s become contact_dwell_s. No deprecated alias is retained: no unchanged Evaluation consumer uses the pilot name, and the runtime-specific tests/examples were updated.

The controller algorithm is unchanged: qualifying contact starts contact_since; contact loss resets it; continuous observed contact reaching the requested duration succeeds. Existing servo targets and guard checks remain active during dwell. This checks contact presence, not force/slip/grasp stability, wrench feasibility or force closure. The output-key rename is intentional; consumers of the earlier pilot must update.

## 7. Machine-readable spec matches Runtime

`spec/instructions/make_contact.schema.json` is now the canonical implemented arguments schema, including legacy omissions, string group IDs, strict unknown-field rejection and contact_present/contact_dwell termination. It no longer advertises full VirtualContactGroup, arbitrary regions/directions/speed or Agent constraints.

Its byte-identical mirror `dex_hand/schema/make_contact.schema.json` is shipped in the wheel. Runtime loads that mirror with importlib.resources and uses Draft202012Validator; its accepted top-level argument keys derive from the same schema. Schema/Runtime acceptance pairs, packaged-byte equality and dynamic capability failures are tested. Nonfinite decoder extensions and non-representable duration values are explicitly rejected before motion, without inventing a new physical threshold.

`scripts/extract_instruction_schemas.py` now syncs MAKE_CONTACT from the canonical implemented file rather than overwriting it with old Markdown. It still checks the separate, unchanged BREAK_CONTACT draft extract. `spec/README.md` distinguishes the implemented contract from the broader historical v0.2 design reference. Root and packaged v0.2 Markdown, taxonomy, FailureClass, CanonicalObservation and SkillOutcome remain unchanged. Other Skills are not parameterized.

## 8. Verification before / after

Environment: existing Python 3.12.14 simulation environment, MuJoCo 3.13.0, NumPy 2.5.3, jsonschema; existing external models configured through their environment variables. All work was offline. No hardware connection, Agent model call or Agent performance experiment was run.

| Check | Result |
| --- | --- |
| Latest-main baseline suite | 66 tests: 65 passed, 1 explicit historical-evidence skip; no failure/error |
| Phase 2 full suite | 75 tests: 74 passed, 1 same historical-evidence skip; no failure/error |
| Runtime architecture / injection | No concrete hand/bootstrap/WorldConfig creation in Runtime; supplied Adapter/ScenePlan used without replacement |
| Public API/schema | Legal event/dwell requests accepted; malformed/unknown fields and constraints rejected; schema and Runtime static acceptance agree |
| Dwell guards | Contact-loss reset, deadline, collision, overload, drift and mode conflict tests pass; controller loop unchanged |
| Four-hand bootstrap and legacy chain | Each hand completes the same 5-stage chain; complete serialized responses, qpos/qvel/ctrl and warnings exactly match pre-change baseline |
| Four-hand dwell | Identical responses/physical states to pre-change dwell after normalizing only the intended achieved-state key rename |
| Actual JSONL transport | READY → state → constraints NOT_SUPPORTED with unchanged state → shape → canonical dwell SUCCESS |
| Installed wheel outside checkout | New factory, packaged canonical validator, constraints rejection and Wuji physical dwell smoke passed |
| Canonical schema/tooling | MAKE_CONTACT mirror byte-identical; BREAK_CONTACT draft check passed; generation cannot replace implemented MAKE_CONTACT from old draft |
| Codex Skill | Destination request guidance updated narrowly; skill-creator quick_validate.py passed |
| Scope preservation | 61 protected files match baseline SHA-256, including all Evaluation/Pilot code and records, evaluation specs/tests and unchanged physical implementation files |

The one skipped test still requires unpublished results_cross/shared_before.json; this is not reported as a passing historical evidence check. New preservation evidence is explicitly tied to the latest-main Phase 2 baseline. Existing Evaluation tests were run without modification.

| Embodiment | Legacy 5 stages exact match | Dwell physical state exact match | Dwell (s) | MAKE_CONTACT simulation duration (s) | Warnings |
| --- | --- | --- | ---: | ---: | ---: |
| wuji | yes | yes, output key renamed | 0.100 | 0.774 | 0 |
| sharpa | yes | yes, output key renamed | 0.100 | 1.410 | 0 |
| allegro_v5 | yes | yes, output key renamed | 0.100 | 1.078 | 0 |
| robotiq_2f85 | yes | yes, output key renamed | 0.100 | 0.466 | 0 |

Timings above are simulation execution time, not Agent inference time or performance comparisons.

## 9. Evaluation explicitly unchanged

No edits under evaluation/ or pilot/. No evaluation import rerouting, shared shield changes, A-D task changes, Skill-vs-Direct surface changes or evaluation-test edits. agent-interface-evaluation-spec-v0.2.md and the old compatibility specification are byte-identical. The six frozen historical POINT records remain at their original paths and bytes; the complete README experiment section also remains unchanged.

Evaluation's existing direct Skill calls remain intentionally separate from Runtime in this phase. Adapter controllers/IK/estimator, world physics, SHAPE_HAND, ESTABLISH_GRASP, MAINTAIN_GRASP, APPLY_WRENCH, BREAK_CONTACT and other retained safeguards are unchanged.

## 10. Scope and remaining limitations

The interface intentionally breaks only the recent pilot's public constraints/name and old runtime hand-constructor form. Bare physical calls and the deployed CLI remain compatible. The canonical schema describes argument shape, not guaranteed physical reachability or arbitrary scene construction. Broader v0.2 design features and generic Agent constraints remain deferred. BREAK_CONTACT schema remains clearly labeled as a draft extract, not an implemented parameterized API.

No Evaluation redesign, general constraints framework, full v0.3 specification or real-hardware support was introduced. The original private DexISA repository was not changed.

## Changed paths

- `.agents/skills/dexisa/SKILL.md`
- `ARCHITECTURE.md`
- `MANIFEST.in`
- `PARAMETER_CLASSIFICATION.md`
- `README.md`
- `REFACTOR_RESULTS.md`
- `dex_hand/bridge/mujoco_adapter.py`
- `dex_hand/runtime/requests.py`
- `dex_hand/runtime/session.py`
- `dex_hand/skills/make_contact.py`
- `docs/MAKE_CONTACT_INTERFACE.md`
- `pyproject.toml`
- `scripts/extract_instruction_schemas.py`
- `spec/README.md`
- `spec/instructions/make_contact.schema.json`
- `tests/test_make_contact_request.py`

## Added paths

- `dex_hand/core/instruction_schema.py`
- `dex_hand/core/scene.py`
- `dex_hand/schema/make_contact.schema.json`
- `dex_hand/session_factory.py`
- `tests/fixtures/phase2_preservation.json`
- `tests/test_phase2_architecture.py`
- `PHASE2_RESULTS.md`
