# DexISA reference architecture — Phase 2

Agent-visible instructions currently contain an opcode, target/contact operands and termination. Generic Agent-visible execution constraints are intentionally deferred until more complex deployment scenarios provide concrete requirements.

```text
Agent → Bridge → InstructionRequest → RuntimeSession
                                        ↓
                         Adapter capability / retained safety
                                        ↓
                            Adapter → Controller / Robot
```

Bootstrap is outside this execution chain: hand ID → concrete Adapter + prepared ScenePlan + perturbation apparatus → injected RuntimeSession. No new constraint language or policy engine is introduced.

## Responsibilities

| Layer | Owner / entry points | Responsibilities |
| --- | --- | --- |
| Implemented ISA contract | spec/instructions/make_contact.schema.json | Current MAKE_CONTACT arguments; packaged mirror is used by the Runtime validator |
| Broader design reference | dexterous-hand-skill-mcp-spec-v0.2.md | Historical v0.2 taxonomy, contact/belief/uncertainty concepts and broader draft schemas; not the implemented request contract |
| Runtime | dex_hand/core, skills, modes, runtime/session.py and requests.py | Shared validate/resolve/execute/monitor/termination/outcome semantics; receives its Adapter and ScenePlan |
| Bootstrap / binding | dex_hand/session_factory.py; core/scene.py | Creates concrete MuJoCo Adapter, chooses ScenePlan, injects perturbation apparatus; preserves existing scene values |
| Adapter | dex_hand/adapters and simulation fixtures | Morphology-specific mapping, kinematics/servo commands, canonical observation and source/backend limits |
| Bridge | dex_hand/bridge/mujoco_adapter.py | CLI selection through factory, JSON parse, runtime call and result serialization |
| Evaluation | evaluation/, pilot/ compatibility entry points | Existing A-D task definitions, external scoring, Agent surfaces, shield, orchestration and metrics; unchanged in Phase 2 |

Agent decides what interaction to perform, its target/contact operands, and when the instruction should terminate. Runtime decides how shared ISA semantics execute, reference execution policy, runtime guards and failure semantics. Adapter decides embodiment-specific realization. Safety decides non-negotiable physical/backend limits.

`dex_hand/runtime/` neither chooses a hand nor creates an Adapter, scene or MuJoCo perturbation. It has no concrete hand branches or backend model/data access. Time comes from CanonicalObservation. Bootstrap alone knows the four hand IDs. A prepared ScenePlan contains groups, aperture, clearance and object_id; it is a small data object, not a scene description language.

## Construction and dispatch

```python
from dex_hand.runtime.session import RuntimeSession
from dex_hand.core.scene import ScenePlan

session = RuntimeSession(adapter=adapter, scene_plan=scene_plan,
                         perturbation=perturbation)
```

The optional perturbation is injected because existing grasp certification requires apparatus. Without it ESTABLISH_GRASP retains its NOT_SUPPORTED result; Runtime does not invent a backend helper. Runtime constructs the existing shared Skills/mode, not a second runtime.

For offline deployment use `create_mujoco_session(hand_id)` in dex_hand/session_factory.py. The CLI remains `dexisa-mujoco --hand <hand>`. The old bridge `Session(hand)` convenience delegates to this factory. The Phase 1 runtime Session(hand) constructor is replaced by injected RuntimeSession; Runtime does not import a compatibility factory.

## Parameter owners

| Category | Owner | Current meaning |
| --- | --- | --- |
| Agent operands and termination | Implemented MAKE_CONTACT schema | Existing object ID, prepared group IDs, contact_present or explicitly timed contact_dwell |
| Reference execution defaults | Existing Skill signature/execution implementation | Contact speed 0.008 m/s, travel 0.045 m, load guard 4 N, relative drift guard 0.015 m, deadline 8 s; all selected required groups |
| Adapter capability | Adapter/observation contract + prepared scene binding | Can/cannot observe contact, resolve an object/group or support an operation; does not store controller defaults |
| Hard safety | Source model, backend and retained runtime collision/fault handling | Source joint/actuator limits, forbidden collisions, backend faults; cannot be overridden by Agent or redefined by reference defaults |
| Controller realization | Existing Skill/Adapter code | Servo law, gains, increments, IK and contact estimator; unchanged |
| Evaluation rules | Existing evaluation only | POINT 2 mm, release actual 2 mm, clear 100 ms, further hold 0.5 s; unchanged |

**4 N is the current reference runtime load guard, not a vendor hardware absolute limit.** Removing the public constraints object does not remove max_load, max_object_drift, max_displacement, timeout, collision checks, model limits or backend checks. These internal guards remain exactly as before. Capability answers availability, not preferred speed/force/timeout. Safety is not a new class or framework; the identified existing enforcement remains in place.

Direct engineering Skill APIs still accept their existing internal policy parameters; the Agent JSONL contract exposes none of them. No arbitrary force/drift/travel/speed/gain/timeout override is accepted.

## Contract and compatibility

The authored contract is spec/instructions/make_contact.schema.json. Its byte-identical packaged mirror dex_hand/schema/make_contact.schema.json feeds the runtime validator, and MAKE_CONTACT_KEYS is derived from it. `python scripts/extract_instruction_schemas.py --check` verifies the mirror and the separate historical BREAK_CONTACT draft extract. Generation never replaces implemented MAKE_CONTACT from old Markdown.

Omitted operands resolve from the injected ScenePlan; omitted termination means contact_present. Unknown fields, including constraints, return NOT_SUPPORTED before motion. Shape/type errors are PRECONDITION_FAILED at transport validation; object/group availability is a dynamic Adapter/binding check rather than a schema promise of reachability.

contact_dwell means continuous requested contact presence under retained guards. It does not certify force/slip/grasp stability, wrench feasibility or force closure. The timer starts at contact, resets on loss and succeeds at the requested duration. No deprecated alias is retained for the previous pilot name; current examples/tests use the canonical name. Result metadata uses contact_dwell_s.

Other instruction APIs and legacy physical defaults are unchanged. Existing MAKE_CONTACT bare calls and five-stage simulation behavior are verified against pre-change states. Evaluation still calls Skills through its existing paths; rerouting it through Runtime is explicitly deferred.
