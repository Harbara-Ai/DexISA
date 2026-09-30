# Phase 1 organization plan

Execute after source audit and baseline tests. All paths below refer to the independent destination worktree, never the original repository.

| Current path | Target / operation | Reason | Risk and compatibility |
| --- | --- | --- | --- |
| root normative ISA + packaged copy | Retain; add spec/README and two reproducible schema extracts | Preserve human normative text, wheel resources, taxonomy | Copies guarded by consistency test; full canonicalization deferred |
| agent-interface-benchmark-spec-v0.2.md | Rename to agent-interface-evaluation-spec-v0.2.md; old path becomes link stub | Clarify evaluation boundary | Content body retained; record source→target mapping because new public history is intentionally fresh |
| pilot/interfaces.py TASKS/BUTTON_RELATIVE | evaluation/tasks/definitions.py | Task owner | Exact definitions; compatibility exports |
| pilot/interfaces.py tick scoring | evaluation/evaluators/task_state.py | External task predicates | Preserve literals, update order and exception behavior |
| pilot/interfaces.py shield expression | evaluation/safety/common_shield.py | Common safety owner | Same predicate priority, force bounds, saturation timing |
| pilot/interfaces.py Agent branches | evaluation/agents/surfaces.py | Separate Agent action surfaces | Same registry/actions; bookkeeping remains episode runner |
| remaining PilotEpisode | evaluation/runners/episode.py | Own scene, stepping, trace and counters | pilot.interfaces module alias; no scoring/controller changes |
| pilot/protocol.py | evaluation/agents/protocol.py | Prompts/schema separate from runtime | pilot.protocol alias; values unchanged |
| pilot/run.py | evaluation/runners/pilot.py | Evaluation orchestration | pilot.run alias and direct-script support; fix missing output directory creation |
| pilot/run.py parse_usage | evaluation/metrics/native_usage.py | Authoritative usage accounting | Same validation and subset accounting |
| dex_hand/evaluators/sim_subset.py | evaluation/evaluators/sim_subset.py | Read-only task scoring | Old module re-export; original evaluator function unchanged |
| bridge Session/HANDS/ARGUMENT_KEYS | dex_hand/runtime/session.py | Runtime dispatch/defaults outside transport | bridge still exports Session/HANDS/ARGUMENT_KEYS; all legacy results characterized |
| no unified request | dex_hand/core/request.py | Shared request shape | Strict envelope validation; retain legacy tool+arguments form |
| bare MAKE_CONTACT bridge branch | dex_hand/runtime/requests.py resolver + existing MakeContact | Parameterized pilot | Bounded fields; rejected unsupported fields; optional dwell is intentional new termination only |
| tests/test_m8 historical hash check | Keep check; explicitly skip if unpublished historical artifact absent | Honest portable suite | Skip reported, not claimed passed; new migration manifest tests record unchanged files |
| docs/experiments/* | No move or edit | Immutable historical records | Verify all six SHA-256 hashes |
| adapters, physics scenes, grasp/hold/release controllers | No edit | Preserve behavior | File fingerprints checked |
| README / distributed Codex Skill | Navigation and current-interface links | Usable destination | No new fixed task stage sequence; runtime stays optional to evaluation |

Validation gates: existing suite → audit docs → extraction-only suite and exact four-hand legacy state comparison → MAKE_CONTACT pilot tests → full suite and installed-wheel smoke → source read-only/publication checks. No LLM, hardware, threshold redesign, new controller or second runtime.
