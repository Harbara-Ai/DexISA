# Phase 1 refactor and migration results

**Status after Phase 2:** the original findings below describe the Phase 1 publication. Current Runtime uses injected Adapter/ScenePlan with external bootstrap; MAKE_CONTACT now exposes object/group operands and contact_present/contact_dwell termination, with no Agent constraints. See [PHASE2_RESULTS.md](PHASE2_RESULTS.md) and [ARCHITECTURE.md](ARCHITECTURE.md) for current APIs. Pilot stability naming below is historical migration context, not a supported alias.

## Publication and preservation

Source: private Harbara-Ai/DexISA main `5429c8ea06834652a0c1a93f9f9ca0084a18a7a0`. Destination: public Harbara-Ai/DexISA_v2. The owner explicitly requested a fresh code publication without source Git history. No source push, branch, configuration, visibility or file modification was performed. The destination publication has a new root commit attributed to Codex <codex@openai.com>.

The six docs/experiments POINT files remain at their original paths and SHA-256 bytes. Removed old contact-pilot result folders are not restored. Hand models/meshes and credentials are not included. .gitattributes preserves source/artifact bytes across platforms; line-ending normalization is deferred.

**No intentional physical-control semantic changes in Phase 1 for legacy calls.** Adapter implementations, source effort/joint limits, world composition/physics, ESTABLISH_GRASP, MAINTAIN_GRASP, APPLY_WRENCH and BREAK_CONTACT are unchanged. Existing MAKE_CONTACT speed/increments/guards and default event termination are preserved.

## Moved or extracted files

| Source | Destination | Compatibility |
| --- | --- | --- |
| agent-interface-benchmark-spec-v0.2.md | agent-interface-evaluation-spec-v0.2.md | Old path link stub; only title terminology changed in destination; original body/task numbers retained |
| pilot/interfaces.py | evaluation/runners/episode.py plus tasks/definitions.py, evaluators/task_state.py, safety/common_shield.py, agents/surfaces.py | pilot.interfaces module alias preserves imports and monkeypatch identity |
| pilot/protocol.py | evaluation/agents/protocol.py | pilot.protocol module alias; prompt/tool values unchanged |
| pilot/run.py | evaluation/runners/pilot.py plus metrics/native_usage.py | pilot.run module alias and direct CLI wrapper; frozen pairing unchanged |
| dex_hand/evaluators/sim_subset.py | evaluation/evaluators/sim_subset.py | Old evaluate import retained; scorer code unchanged |
| bridge Session and HANDS defaults | dex_hand/runtime/session.py | bridge Session/HANDS/ARGUMENT_KEYS imports retained; CLI entry point unchanged |

Because the public destination intentionally omits source history, Git rename history cannot span the two repositories. This map plus the source commit identifier records provenance; it does not claim to preserve the original commit graph.

## Additions and intentionally changed behavior

- Required audit/architecture/parameter/plan/results documents; spec index and only two exact draft input-schema extracts with a reproducible extractor.
- Unified InstructionRequest and MAKE_CONTACT resolver; transport contains only JSONL parsing/calling/serialization/startup/error handling.
- Optional keyword-only contact_stable_s (default zero) reuses the existing contact-acquisition loop. Explicit contact_stable requests keep observing while holding existing servo targets; timer resets on contact loss and guards remain active. This new requested termination intentionally extends simulation duration; it is not a new grasp controller.
- New JSONL fields expose object/group selection and bounded force/drift/displacement/deadline constraints. Requests may tighten the current reference envelope, not relax it. Existing 4 N contact cap remains; no vendor force rating is invented.
- Unknown envelope fields now fail explicitly instead of being silently ignored. Invalid/unsupported new fields fail before motion; validation errors retain the existing bridge error shape.
- freeze_order now creates its output directory. Episode compact/result output converts task_success/physical_success NumPy booleans to JSON booleans. Only serialization changes; task predicates are unchanged.
- Missing unpublished historical checksum test is explicitly skipped, while the original checksum comparison is retained when its artifact exists. New preservation tests separately check immutable files and unchanged physics/controller bytes; this is not a substitute for missing historical evidence.
- Source/wheel packaging includes optional evaluation and pilot compatibility packages. No extra runtime dependency or real hardware path was introduced.
- Destination README/Skill documents the actual parameterized subset and does not impose a fixed stage order.

## Tests before and after

Environment: existing Python 3.12.14 simulation venv, MuJoCo 3.13.0, NumPy 2.5.3, declared jsonschema dependency, four existing external assets configured via environment variables. No LLM/API model calls, hardware connections, new Agent benchmark, multi-seed study or token claims.

| Check | Result |
| --- | --- |
| Source suite, before edits | 46 tests: 44 passed; 2 errors (unpublished results_cross/shared_before.json and absent results_pilot output directory) |
| Extraction-only suite, before MAKE_CONTACT pilot | 48 tests: 47 passed; 1 explicit historical-evidence skip |
| Final suite | 66 tests: 65 passed; 1 explicit historical-evidence skip; no failures/errors |
| Four-hand legacy chain | All 5 stages SUCCESS on each hand; complete JSON-serialized responses, qpos/qvel/ctrl and warnings exactly match captured source baseline |
| A-D extraction characterization | 16 scripted cases (4 tasks ×2 existing hands ×2 interfaces); action outputs, qpos and evaluator counters identical after normalizing legacy NumPy booleans; not an Agent performance experiment |
| New MAKE_CONTACT validation/dwell | Unknown/relaxed/nonfinite inputs, mode conflict, contact-loss reset, deadline, overload/collision/drift during dwell checked; invalid physical request leaves qpos/time unchanged |
| New four-hand contact request | 2 N bound, 2 mm drift bound, 100 ms continuous contact; all four SUCCESS, actual MuJoCo contacts, zero warnings |
| Architecture boundaries | Runtime does not import evaluation; bridge does not construct Skills/Adapters/modes; legacy evaluation module aliases preserve identity |
| Historical/physical preservation | All six record bytes and selected unchanged controller/Adapter/scene/core files match source SHA-256 manifest |
| Draft schema extraction | Both extracts validated and reproduced exactly from normative source |
| Installed wheel | Built and installed outside source checkout; packaged schema, compatibility imports, Wuji shaping and parameterized physical contact smoke passed |
| Distributed Codex Skill | skill-creator quick_validate.py passed using isolated validation-only PyYAML dependency |

The initial bundled interpreter lacked MuJoCo; baseline was rerun with the existing simulation venv. Skill validator initially lacked PyYAML; it was supplied in an isolated tooling directory, not added to runtime dependencies. These environment issues did not justify substituting mocks for physics checks.

## MAKE_CONTACT physical verification

| Hand | Result | Continuous contact (s) | Skill simulation duration (s) | MuJoCo warnings | Legacy five-stage exact match |
| --- | --- | ---: | ---: | ---: | --- |
| wuji | SUCCESS | 0.100 | 0.774 | 0 | yes |
| sharpa | SUCCESS | 0.100 | 1.410 | 0 | yes |
| allegro_v5 | SUCCESS | 0.100 | 1.078 | 0 | yes |
| robotiq_2f85 | SUCCESS | 0.100 | 0.466 | 0 | yes |

These timings are Skill execution simulation time, not Agent time or benchmark performance. Contact_stable certifies continuous contact under requested guards, not stable grasp or free-space force closure.

## Known risks / remaining debt

- Draft Markdown defaults and supported Python realization defaults differ; those differences are documented rather than silently harmonized. Root/package normative duplication remains, guarded by consistency tests.
- Full VirtualContactGroup regions, arbitrary directions/objects, constraint allocation, wrench feasibility and belief-planning semantics are not implemented by this pilot. Unsupported capability requests stay explicit.
- Existing Adapter grasp estimators and external scoring use related baseline predicates; consolidation requires a separate semantic review because their references/timing differ.
- Existing official Adapter benchmark-readiness validation depends on unpublished asset/readiness evidence. A successful simulation refactor check does not make those flags or every evaluation fixture formally ready.
- Existing sim/runner.py, experiment fixtures and legacy contact instrumentation scripts remain in their old locations to preserve reproduction paths.
- The recorded external POINT experiment uses A-J labels; the included legacy pilot uses A-D with D grasp/hold/release. They remain separate and are not relabeled.
- Existing pilot API execution still requires its explicit preflight gate artifact and credentials. No formal API experiment is launched by this migration.
- Vendor assets remain external and code redistribution licensing remains undeclared as in the source. The refactor does not silently select a license.

Recommended next phase: review one additional instruction mapping and separate remaining fixture/readiness evidence from Adapter capability reporting, with characterized behavior and explicit spec-to-runtime mappings. No additional phase was implemented here.

## Exact Phase 1 file inventory

Modified/replaced source paths:

- `.agents/skills/dexisa/SKILL.md`
- `.gitattributes`
- `.gitignore`
- `README.md`
- `agent-interface-benchmark-spec-v0.2.md`
- `dex_hand/bridge/mujoco_adapter.py`
- `dex_hand/evaluators/sim_subset.py`
- `dex_hand/skills/make_contact.py`
- `pilot/interfaces.py`
- `pilot/protocol.py`
- `pilot/run.py`
- `pyproject.toml`
- `tests/test_m8.py`

Added destination paths:

- `ARCHITECTURE.md`
- `ARCHITECTURE_AUDIT.md`
- `MANIFEST.in`
- `PARAMETER_CLASSIFICATION.md`
- `REFACTOR_PLAN.md`
- `agent-interface-evaluation-spec-v0.2.md`
- `dex_hand/core/request.py`
- `dex_hand/runtime/__init__.py`
- `dex_hand/runtime/requests.py`
- `dex_hand/runtime/session.py`
- `docs/MAKE_CONTACT_INTERFACE.md`
- `evaluation/README.md`
- `evaluation/__init__.py`
- `evaluation/agents/__init__.py`
- `evaluation/agents/protocol.py`
- `evaluation/agents/surfaces.py`
- `evaluation/evaluators/__init__.py`
- `evaluation/evaluators/sim_subset.py`
- `evaluation/evaluators/task_state.py`
- `evaluation/metrics/__init__.py`
- `evaluation/metrics/native_usage.py`
- `evaluation/records/README.md`
- `evaluation/runners/__init__.py`
- `evaluation/runners/episode.py`
- `evaluation/runners/pilot.py`
- `evaluation/safety/__init__.py`
- `evaluation/safety/common_shield.py`
- `evaluation/tasks/__init__.py`
- `evaluation/tasks/definitions.py`
- `scripts/extract_instruction_schemas.py`
- `spec/README.md`
- `spec/instructions/break_contact.schema.json`
- `spec/instructions/make_contact.schema.json`
- `tests/fixtures/source_preservation.json`
- `tests/test_architecture_layers.py`
- `tests/test_make_contact_request.py`
- `tests/test_phase1_preservation.py`
- `REFACTOR_RESULTS.md`
