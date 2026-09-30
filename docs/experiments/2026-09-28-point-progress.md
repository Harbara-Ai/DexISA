# POINT native-agent experiment snapshot

## Native model experiment progress: POINT in MuJoCo (2026-09-28)

**Frozen progress snapshot: 2026-09-28T07:02:43+00:00; 781/800 completed native model episodes.** The model is `gpt-5.6-luna` with `low` reasoning and no fallback. Each episode uses an independent Agent context. The benchmark executes outside this ISA repository; this update publishes results and does not alter runtime or Skill behavior.

### All completed episodes

| Embodiment / interface | Completed / planned | Success | Failure | Native total tokens | Cumulative wall time (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| wuji / SKILL_AGENT | 100/100 | 100 | 0 | 2,643,049 | 1333.657 |
| wuji / DIRECT_AGENT | 100/100 | 44 | 56 | 3,707,185 | 4130.281 |
| sharpa / SKILL_AGENT | 100/100 | 82 | 18 | 2,739,107 | 1422.023 |
| sharpa / DIRECT_AGENT | 100/100 | 59 | 41 | 4,752,620 | 4077.718 |
| allegro_v5 / SKILL_AGENT | 100/100 | 15 | 85 | 3,169,279 | 2387.942 |
| allegro_v5 / DIRECT_AGENT | 81/100 | 17 | 64 | 3,350,394 | 4279.617 |
| robotiq_2f85 / SKILL_AGENT | 100/100 | 4 | 96 | 1,082,520 | 1603.677 |
| robotiq_2f85 / DIRECT_AGENT | 100/100 | 4 | 96 | 2,321,787 | 2956.921 |

Totals include failures. Wall time is the sum of episode durations, not elapsed time of the parallel batch. An incomplete condition is a progress snapshot, not a final success rate.

### Average cost of all successful episodes

Each interface independently includes every successful measured episode with valid native token audits. No seed matching or equal-count subsampling; failed and unfinished episodes excluded from success-only means.

| Embodiment / interface | Successful samples | Mean native tokens | Mean wall time (s) | Mean Agent-active (s) | Mean simulation (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| wuji / SKILL_AGENT | 100 | 26,430.5 | 13.337 | 13.318 | 0.287 |
| wuji / DIRECT_AGENT | 44 | 37,458.9 | 41.887 | 41.803 | 1.587 |
| sharpa / SKILL_AGENT | 82 | 26,449.6 | 13.525 | 13.508 | 0.242 |
| sharpa / DIRECT_AGENT | 59 | 42,214.9 | 34.270 | 34.124 | 2.209 |
| allegro_v5 / SKILL_AGENT | 15 | 25,247.9 | 15.346 | 15.321 | 0.356 |
| allegro_v5 / DIRECT_AGENT | 17 | 23,950.2 | 32.907 | 32.858 | 0.878 |
| robotiq_2f85 / SKILL_AGENT | 4 | 8,073.2 | 7.213 | 7.201 | 0.193 |
| robotiq_2f85 / DIRECT_AGENT | 4 | 9,469.5 | 10.864 | 10.846 | 0.441 |

These success-only averages use each interface's own successful cases, so the case sets and counts can differ. They exclude failure cost and do not estimate overall efficiency.

### Tasks and experimental settings

| Item | Setting / physical goal | Qualification / execution |
| --- | --- | --- |
| Model | GPT-5.6 Luna; reasoning `low`; no model fallback; independent Agent context per episode | Actual native model calls |
| Platforms and physics | Wuji Hand2, Sharpa Wave, Allegro V5 4F and Robotiq 2F-85; fixed palm; offline MuJoCo; 2 ms timestep, implicitfast, gravity −9.81 m/s², 80 solver iterations | No physical hardware, moving wrist or robot arm |
| A — POINT | Empty physical target scene; index fingertip to a world point with ≤2 mm error continuously for 100 ms; 3 s simulation budget | Wuji/Sharpa A baseline plus the nominally qualified Allegro/Robotiq A fixtures below; randomized-goal reachability is a separate limitation |
| B — TOUCH | Supported cylinder; index contact in target region for 100 ms; object translation ≤2 mm; continued inward travel after contact ≤0.5 mm; 8 s budget | Wuji/Sharpa bindings unqualified; Allegro/Robotiq not assessed for this task; no model episodes |
| C — PRESS | Activate spring button at ≥8 mm displacement, then actual retreat ≥2 mm and geometrically no contact for 100 ms; 22 s budget | Wuji/Sharpa bindings unqualified; Allegro/Robotiq not assessed for this task; no model episodes |
| D — SLIDE | Start in index contact on fixed plane; slide to endpoint 20 mm away, error ≤2 mm for 100 ms; retain contact while moving; 10 s budget | Wuji/Sharpa bindings unqualified; Allegro/Robotiq not assessed for this task; no model episodes |
| E — ADD_CONTACT | Preserve thumb contact; add index target contact for 100 ms; whole-episode translation <2 mm, rotation <3°; 8 s budget | Wuji/Sharpa bindings unqualified; Allegro/Robotiq not assessed for this task; no model episodes |
| F — STABILIZE | Initial supported dual contact; independent physical stability for 0.5 s; no external disturbance; 5.5 s budget | Wuji/Sharpa bindings unqualified; Allegro/Robotiq not assessed for this task; no model episodes |
| G — RELEASE | Initial supported stable grasp; remove all geometric hand–object contacts, actual retreat ≥2 mm, supported and clear for 100 ms; 5 s budget | Wuji/Sharpa bindings unqualified; Allegro/Robotiq not assessed for this task; no model episodes |
| H — GRASP_FORMATION | From no contact, establish thumb/index contacts in specified regions and physical stability for 0.5 s; no lift or mandatory POINT/Skill stage order; 16.5 s budget | Wuji/Sharpa bindings unqualified; Allegro/Robotiq not assessed for this task; no model episodes |
| I — RELEASE_REGRASP | Initial stable region set A; physically controlled release, then region set B stable for 0.5 s; 22 s budget | Wuji/Sharpa bindings unqualified; Allegro/Robotiq not assessed for this task; no model episodes |
| J — ROTATE | Supported stable cylinder; signed ±30° about initial palm +Z; full orientation error <5°, translation <5 mm, final stability for 0.5 s; 10 s budget | Wuji/Sharpa bindings unqualified; Allegro/Robotiq not assessed for this task; no model episodes |
| Sampling and pairing | 100 requested seeds / hand (0–99); shared seeded initial checkpoint, physics model, goal, observations and evaluator for both interfaces; invalid resets are recorded without resampling | A budget: 4 hands ×100 seeds ×2 interfaces = 800 episodes |
| Reset distribution | Object/virtual-frame XY ±10 mm, Z ±3 mm, roll/pitch/yaw ±5°; friction 0.6–1.0, mass 0.8–1.2×, joint noise ±0.01 rad; fixture-specific exceptions apply | A has no physical object/support; friction and mass draws are not physical A parameters |
| Action interfaces | Skill: existing SHAPE_HAND POINT semantics realized by external benchmark IK + source-model position servo. Direct: named joint targets; no IK or semantic controller | Both observe fingertip position and local Jacobian; no required intermediate posture or Skill call order |
| Common safety | No forbidden self/environment contact; source joint/actuator limits retained; contact-group normal load cap 4 N (C: 3 N); benchmark penetration cap 1 mm; saturation >0.2 s abort; simulator faults abort | Evaluated each physical step; whole-episode violations prevent success |
| Timing and token accounting | Wall: episode thread/start to native turn completion. Agent-active: wall minus robot-tool handling (includes final model response). Simulation: MuJoCo time. Tokens: native response usage summed and audited against thread usage | Runtime initialization and full desktop startup are not included in wall time |
| Qualification denominator | Original Wuji/Sharpa A–J plan: 4,000 requests; 3,600 B–J unqualified. Added Allegro/Robotiq scope: A only, 400 requests | Unqualified bindings are not Agent failures |

### Additional-hand interpretation

- Allegro and Robotiq use deterministic, fixed palm mounts registered before scoring to the unchanged nominal world goal. Both interfaces share the same resolved model and reset checkpoint for each seed; mount configuration is included in the published JSON.
- Robotiq has one active degree of freedom and coupled planar jaws. **80/100 randomized A goals lie more than 2 mm outside its fixed jaw-tip plane and are physically unreachable.** Those seeds were retained under the original task rule. Its failures therefore mix embodiment workspace limits with controller/Agent performance; nominal qualification and reset safety do not establish reachability for every seed.
- Allegro Skill uses the frozen external POINT IK and source servo binding for this snapshot. The earlier local Allegro ramp-controller batch used a different fixed mount/controller and is not merged into these tables.
- Most recorded failures are `GOAL_NOT_REACHED_WITHIN_BUDGET`; source actuator-limit failures are separately listed in the failure CSV and JSON.
- Four attempts interrupted by the desktop restart were preserved locally. Completed responses consumed at least 33,483 additional tokens; terminal token accounting and complete wall times were unavailable. These costs are separate from the completed-episode totals.

This is an A-only simulation comparison, not a completed A–J benchmark or real-hardware result. Skill-side POINT control is an external experimental realization of existing SHAPE_HAND semantics, not a claim that the published Codex Skill executes A–J unchanged.

Public data: [snapshot JSON](2026-09-28-point-progress.json), [all-episode totals CSV](2026-09-28-point-progress-all.csv), [all-success mean costs CSV](2026-09-28-point-progress-successful.csv), [per-episode metrics CSV](2026-09-28-point-progress-episodes.csv), [failure reasons CSV](2026-09-28-point-progress-failures.csv), and [experiment report](2026-09-28-point-progress.md). GitHub shows a frozen snapshot and does not automatically follow the ongoing local batch.
