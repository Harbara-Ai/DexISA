# DexISA reference architecture — Phase 1

DexISA defines interaction instructions; the reference runtime executes them through Adapter primitives. Evaluation measures particular tasks independently. Package name remains `dex_hand`.

| Layer | Owner / entry points | Responsibilities | Exclusions |
| --- | --- | --- | --- |
| Spec | spec/, root normative v0.2 Markdown | Taxonomy, types, instruction contract, constraints and termination intent | Model mapping, gains, task score |
| Runtime | dex_hand/core, skills, modes, runtime/session.py and requests.py | Validate → resolve → execute existing closed loop → enforce constraints → evaluate termination → SkillOutcome | API inference, token accounting, external task scoring |
| Adapter | dex_hand/adapters and simulation fixtures | Map abstract groups, realize kinematics/servo targets, expose canonical observations, enforce source joint/actuator/backend bounds | Independent per-hand MAKE_CONTACT state machines |
| Bridge | dex_hand/bridge/mujoco_adapter.py | JSONL parse → InstructionRequest → runtime call → serialize | Instruction defaults and task predicates |
| Evaluation | evaluation/tasks, evaluators, agents, safety, runners, metrics, records index | Frozen A-D tasks, external scoring, shared shield, interfaces, orchestration and native usage | Required runtime dependency or universal instruction thresholds |

Runtime depends on core and Adapter primitives; bridge depends on runtime; evaluation depends on runtime/Adapters. Runtime never imports evaluation. Existing `sim/runner.py` and experiment fixtures remain compatibility debt, not a mandatory evaluation layer.

## Parameter ownership

| Concept | Owner | Examples / precedence |
| --- | --- | --- |
| Task operands | ISA request | Object and selected virtual contact-group IDs |
| Task constraints | ISA request, validated/resolved by runtime | Requested force/drift/travel/deadline bounds; caller may tighten current reference envelope |
| Termination | ISA request + runtime | Contact present (legacy event), optional continuous contact dwell; evaluation hold/retreat rules remain separate |
| Reference defaults | Existing Skill signature; runtime scene plan for morphology and legacy wrappers | Contact 4 N / 15 mm / 8 s; internal speed 8 mm/s; bridge does not duplicate these defaults |
| Controller realization | Existing Skill/Adapter code | Gain, numerical clamps, inward direction from prepared object-frame regions |
| Hard safety | Source model + backend + runtime guards | Joint ranges, absolute actuator bounds, collisions/faults; cannot be disabled by Agent |
| Evaluation rules | evaluation only | POINT 2 mm, release actual 2 mm, clear 100 ms, further hold 0.5 s |
| Historical data | Original record files | Read-only; no recomputation or relocation |

Effective execution constraints = Agent constraints ∩ Adapter capabilities ∩ retained safety envelope. The MAKE_CONTACT JSONL pilot keeps its existing reference 4 N envelope non-relaxable; this is a conservative implementation compatibility policy, **not a new hardware rating**. Other direct Python Skill APIs retain their existing signatures and semantics. No global safety policy is silently substituted.

## Spec versus supported reference subset

The normative v0.2 Markdown remains authoritative for taxonomy and draft semantics. Its packaged byte-identical copy supports wheel result validation. A consistency test and reproducible extractor guard the remaining duplication. spec/instructions contains only exact MAKE_CONTACT/BREAK_CONTACT draft schema extracts; they are not advertised as fully implemented wire interfaces.

The JSONL MAKE_CONTACT pilot uses named group IDs resolved against the selected scene's existing ContactGroup plan, not arbitrary draft VirtualContactGroup regions. Only `target` exists in prepared scenes. Unknown objects/groups/fields and unavailable capabilities fail explicitly; no mock fallback. Arbitrary directions, region definitions, wrench feasibility and parameterized BREAK_CONTACT are deferred.

Legacy bridge Session import and bare calls remain supported. Persistent MAINTAIN_GRASP remains the same callback mode with the existing bounded bridge wrapper. FailureClass, validity, provenance and UNKNOWN semantics are unchanged.

## Publication boundary

Only the destination repository is edited/pushed. DexISA_v2 is public with a fresh root commit; no source Git history is transferred. Source origin/head and historical-record hashes are verified before publication. Local external models, private credentials and unpublished result folders are excluded. Audit provenance identifies the source commit without publishing its history.
