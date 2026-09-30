# Phase 1 architecture audit

Source: Harbara-Ai/DexISA main `5429c8ea06834652a0c1a93f9f9ca0084a18a7a0`, inspected 2026-09-30 before edits. The source repository is read-only. Destination is Harbara-Ai/DexISA_v2, public, with a fresh publication history at the owner's request.

## Actual module map

| Source module | Actual responsibility | Layer / observation |
| --- | --- | --- |
| dexterous-hand-skill-mcp-spec-v0.2.md | Taxonomy, descriptors, input/output schemas, belief/uncertainty, ContactState, VirtualContactGroup, ConstraintAllocation, TerminationSemantics, Capability | Normative ISA draft; broader than reference implementation |
| dex_hand/schema/â€¦v0.2.md | Byte-identical packaged copy read by core/schema.py | Spec distribution; duplicated source maintained manually |
| dex_hand/core/types.py | Object-frame ContactGroup, PINCH/PRESS plans | Shared local types, smaller than normative VirtualContactGroup |
| core/observation.py, capability.py | Validity/provenance-aware CanonicalObservation and availability | Runtime data contract; UNKNOWN stays unknown |
| core/outcome.py, schema.py | Local SkillOutcome/FailureClass and conversion/validation of draft result shape | Runtime result contract; JSONL emits local shape, not to_v02 shape |
| skills/base.py | Precondition validation, exception-to-outcome, contact/load helpers, collision/load checks, timing and failure hold | Shared runtime infrastructure |
| skills/shape_hand.py, shape_posture.py | Object-conditioned shaping and additive semantic-posture entry point | Runtime; two intentionally distinct entry points |
| skills/make_contact.py | Guarded approach, required-group contact event, load/drift/displacement/deadline guards | Runtime; reused, no controller rewrite |
| skills/establish_grasp.py | Load regulation, BASELINE_STATIC_V1, injected perturbation certification | Runtime reference predicate; does not prove arbitrary wrench feasibility |
| skills/apply_wrench.py, break_contact.py | Existing-contact force application; support-gated unload/retreat | Runtime |
| modes/maintain_grasp.py | Persistent callback regulation, transactional enter/update/exit, bounded recovery | Runtime mode |
| adapters/base.py | HandAdapter Protocol for observation, mapping, commands, preparation, advancement, callbacks | Adapter boundary; no per-hand Skill state machines |
| adapters/mujoco_base.py | Real simulation contact reading, kinematics/IK, source limits, canonical estimator, stepping | Shared simulation Adapter mechanics; estimator includes baseline grasp predicate |
| wuji_mujoco.py, sharpa_mujoco.py | Morphology mapping, source model/URDF integration | Adapter |
| official_mujoco.py | Allegro/Robotiq scene realization, mimic/gap control, health/capability claims | Adapter; readiness lookup depends on historical evaluation files not distributed |
| offline_profile.py, allegro_v5.py, robotiq_2f85.py, profiles/ | Explicit joint-state mocks and pinned metadata | Adapter, not physical contact simulation; default factory backend is mock for these two hands |
| adapters/transport_mujoco.py | Transport experimental adapter, moving installation estimator | Adapter + experiment fixture, deferred |
| bridge/mujoco_adapter.py | CLI/JSONL plus Session, scene defaults, dispatch, hold wrapper, outcome serialization | Crosses transport/runtime/embodiment configuration boundaries |
| sim/worlds.py, perturbation.py | Model composition, unchanged physics settings, injected apparatus | Simulation infrastructure |
| sim/runner.py, logging.py | Scripted experiment sequence and telemetry | Evaluation orchestration/metrics physically colocated in sim; retained |
| sim/support_transfer.py, palm_transport.py | Support-transfer fixture/oracle and palm trajectory experiments | Experimental simulation infrastructure, deferred |
| evaluators/sim_subset.py | Read-only supported-object stage scoring (uses model/site state for shaping) | Evaluation, not execution dependency |
| pilot/interfaces.py | TASKS, scene/reset/belief setup, per-step shield, A-D scoring, Skill/Direct dispatch, trace/results | Major cross-layer file; Phase 1 extraction candidate |
| pilot/protocol.py | Agent prompts/tool surfaces | Evaluation agents |
| pilot/run.py | Frozen 24 episode pairing, API client, native usage accounting, run gates | Evaluation runner/metrics; not required by runtime |
| scripts/contact_native_bridge.py, instrumentation_sanity.py, run_wuji_contact_direct_single.py, summarize_* | Legacy contact comparison execution/telemetry/summarization | Evaluation scripts; no model calls in this refactor |
| scripts/build_official_mujoco.py, fetch_sharpa.py | External asset preparation | Setup tooling, no assets bundled |
| tests/test_m0â€¦m8.py, test_contracts.py | Physical controller, observation, safety/failure, cross-hand checks | Tests; m8 has missing historical checksum dependency |
| tests/test_pilot.py, test_instrumentation_sanity.py | Pairing, tool isolation, reset fairness, native telemetry | Evaluation tests |
| tests/test_distribution.py, test_support_transfer.py, test_transport.py | Distribution errors/schema; experimental fixture checks | Tests |
| docs/ASSETS.md, docs/images/ | Setup and explanation | Documentation |
| docs/experiments/2026-09-28-point-progress.* and CSVs | Six frozen POINT progress artifacts from an external benchmark | Immutable historical records; A-J naming differs from pilot A-D |

No tracked results_* directories exist in this source baseline. Previously removed contact pilot artifacts must not be restored. Existing scripts reference unpublished historical outputs; absence is explicit debt.

## Concrete coupling and duplicate concepts

- Bridge `HANDS` contains morphology-specific normals/aperture/clearance; `Session.execute` binds `target` and gives MAKE_CONTACT no arguments. It directly constructs Skills and decides bounded persistent-mode wrapper duration (0.3 s). Move that code intact to a runtime session; bridge should parse, call and serialize.
- `pilot/interfaces.py:tick` combines collision/load/saturation shield, JSON trace, task scoring and hold-envelope aborts. `dispatch` combines bookkeeping with both Agent surfaces. Extract functions while keeping step order and literals intact.
- MAKE_CONTACT Python defaults: 0.008 m/s, 0.045 m, 4 N, 0.015 m drift, 8 s. Draft section 4.2 defaults: 0.02 m/s, 0.05 m, 1 N, 10 s. They are not an implemented full draft wire contract. Preserve reference defaults and document the difference; do not silently adopt draft defaults.
- BREAK_CONTACT Python: GRADUAL, 0.012 m retreat, 0.015 m drift, 5 s. Draft section 4.8: sequential/simultaneous, 0.03 m retreat, 0.005 m drift, 8 s. No new release implementation in Phase 1.
- Runtime Skill.check has an 8 N default; contact/grasp/hold explicitly use 4 N; APPLY_WRENCH uses 3 N. Pilot shield uses 4 N except C 3 N; sim_subset scoring also uses 4 N. Equal numbers do not imply identical owners. None is established here as a vendor absolute force rating.
- Runtime BaselineStability, Adapter grasp estimator, sim_subset and pilot D use overlapping 0.15 N / 0.015 m/s / 0.5 rad/s / 0.008 m predicates. They score different timing/reference contexts. Centralizing blindly could change behavior; leave physical predicates intact and record debt.
- Runtime BREAK_CONTACT uses 100 ms clear time internally. Pilot C/D independently require 100 ms plus actual 2 mm retreat; runtime retreat is commanded-travel based. Keep the evaluator's actual geometry rule distinct.
- Adapter official_mujoco._validated_ready and readiness_digest depend on results_physics_subset and asset audits absent from this distribution. No benchmark-ready claim is fabricated.
- `sim/runner.py` is an experiment runner despite its placement; `sim/support_transfer.py` includes oracle-only force calculations. Deferred, rather than relocating experimental fixtures without reproduction evidence.

## Baseline checks

Existing environment: Python 3.12.14 venv, MuJoCo 3.13.0, NumPy 2.5.3; existing external four-hand assets configured by environment variables. No asset or hardware modification.

`python -m unittest discover -s tests -v`: 46 tests, 44 passed, 2 errors: missing results_cross/shared_before.json; freeze_order writes to absent results_pilot directory. Initial bundled interpreter lacked MuJoCo; successful baseline execution used the existing simulation venv instead.

Additional deterministic legacy JSONL Session characterization: all four hands completed SHAPE_HAND / MAKE_CONTACT / ESTABLISH_GRASP / MAINTAIN_GRASP / BREAK_CONTACT. Captured every response, qpos/qvel/ctrl and warning count outside historical records for exact after-refactor comparison. This is refactor verification, not an Agent benchmark.
