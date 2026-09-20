# NON_FORMAL Wuji CONTACT Direct single episode

`formal=false`; `purpose=single_pair_comparison`; **preliminary single-pair evidence**.
One new Direct episode, no reruns. The existing Skill sanity result is reused without modification. No formal CSV/statistics are updated.

| Metric | Direct |
| --- | ---: |
| Outcome | SUCCESS |
| Terminal quality | SUCCESS |
| Input tokens | 49173 |
| Cached input | 33536 |
| Output tokens | 871 |
| Reasoning output | 613 |
| Total tokens | 50044 |
| T_startup | 1.5541787 |
| T_active | 40.8632101 |
| T_agent | 39.8834320 |
| T_tool | 0.3230779 |
| T_physical | 2.1000000 |
| T_total | 42.4173888 |
| Decision cycles | 7 |
| Control interventions | 5 |
| Tool calls | 6 |
| State queries | 0 |
| Low level command calls | 5 |
| Peak group load N | 0.4053196 |
| Max object drift m | 0.0031222 |
| Failure class | NONE |

## Pair comparison

| Metric | Skill Agent | Direct Agent | Difference / Ratio |
| --- | ---: | ---: | ---: |
| Success | SUCCESS | SUCCESS | — |
| Total tokens | 7281 | 50044 | D-S=42763.0000000; D/S=6.8732 |
| Decision cycles | 2 | 7 | D-S=5.0000000; D/S=3.5000 |
| Control interventions | 1 | 5 | D-S=4.0000000; D/S=5.0000 |
| T_active s | 4.5775069 | 40.8632101 | D-S=36.2857032; D/S=8.9270 |
| T_agent s | 4.2790169 | 39.8834320 | D-S=35.6044151; D/S=9.3207 |
| T_physical s | 0.6760000 | 2.1000000 | D-S=1.4240000; D/S=3.1065 |
| T_total s | 5.9963823 | 42.4173888 | D-S=36.4210065; D/S=7.0738 |
| Peak load N | 0.1051479 | 0.4053196 | D-S=0.3001717; D/S=3.8548 |
| Max drift m | 0.0000109 | 0.0031222 | D-S=0.0031113; D/S=285.8751 |

Ratios are Direct/Skill. Times compare **time-to-terminal-outcome**; a failed Direct episode is not a successful completion-time measurement. One pair provides no statistical significance or population-level claim.

## Visible action trace

Skill baseline: `MAKE_CONTACT → terminal`

Direct: `describe_hand → set_joint_targets → set_joint_targets → set_joint_targets → set_joint_targets → set_joint_targets → terminal`

Exact Direct joint targets/durations are preserved in visible_action_trace.json and tool_trace.jsonl. No hidden reasoning is reproduced. Direct made no explicit stop call; after its last finite-duration command it ended the native turn. First contact preceded that command's end by 0.3000000 simulation seconds. This is action-boundary termination, not immediate contact-triggered stopping. The common evaluator reports SUCCESS because terminal contact, load, drift and collision constraints are valid. State-query count is zero because the initial observation and each of the five command-boundary observations supplied feedback without separate get_state calls.

## Scene and evaluator equivalence

`initial_state_equivalent=true`.
Skill prepared-state SHA256: `e7c3d742f91af5ebcf841c73d197f3da6ec26e3229697661cbfaa056aae33ed0`.
Direct prepared-state SHA256: `e7c3d742f91af5ebcf841c73d197f3da6ec26e3229697661cbfaa056aae33ed0`.
Scene XML SHA256 (both): `8bc958899bcbc3b3a3df758d635b266609613f323196cd7ddd7bfda9e3c9e633`.
The same Wuji adapter, fixed palm, medium supported cylinder, pose/friction, preshape, effort limits and PilotEpisode.tick evaluator were used. The low-level dispatcher executes the requested duration even after a legal contact; the evaluator records success but does not stop motion. No trajectory, IK helper, contact advance helper, Skill implementation, Skill trace or Skill usage was sent to Direct.

## Safety and timeout separation

- **Common safety shield:** existing joint-range validation and original model effort caps, saturation guard, group load (4 N), object drift (0.015 m), unrelated collision/contact checks and motion latch. Shared code is unchanged. **The common shield currently has no independent joint velocity threshold.** A common-shield violation is reported in tool feedback; Direct may then query or call stop. `shield_triggered=False`; explicit agent stop: `False`.
- **Skill-internal guards / timeout:** MAKE_CONTACT's contact-triggered termination, guarded advance/displacement checks and 8-second physical timeout belong to the Skill implementation. They were not copied to Direct. Direct has no equivalent physical acquisition timeout or automatic success-triggered stopping. This is a validity limitation of this single pair, not proof of identical internal termination mechanisms.
- **Benchmark-level episode timeout:** 180 seconds from native turn/start dispatch, matching the pre-existing sanity runner's timeout duration/origin. This watchdog is independent of contact. On expiration it terminates the episode and holds posture; it is reported separately from the common shield. Triggered: `False`. No extra delay or tuned joint-command budget was introduced.

## Native instrumentation and feedback

Requested/resolved model: `gpt-5.6-luna` / `gpt-5.6-luna`; reasoning: `low`; runtime: `0.155.0-alpha.9.2`.
Thread/session: `01a0be3e-94aa-76b0-a664-ea9fc7048bb9`; turn: `01a0be3e-9508-7b71-a3cd-5f105b1fd880`.
Usage source: `native_turn_usage` (`rawResponse/completed`), cross-checked with native thread total and session rollout. No token estimates. Cache-write input: `0`. Cached and reasoning tokens are breakdowns, not extra additions.

Decision cycles count actual native non-warmup inference requests. Control interventions count only set_joint_targets and stop. Low-level command calls count set_joint_targets; stop is separately observable. Robot tool calls exclude the native code-mode transport wrapper (wrapper calls: 6). Native OTel websocket stream spans supply request_start/response_end and T_agent, never a total-minus-tools residual. Terminal time includes final native inference; simulation pauses during inference. 1050 simulation frames at 0.002 s match physical elapsed time.

Direct receives the same CanonicalObservation contacts/object/status source and precision as Skill, with relevant joint positions/velocities, load, drift and collision fields added for low-level decisions. Static joint metadata is returned only once by describe_hand. The low-level API's action-boundary state is retained. Runtime transport descriptions explicitly tell the model to display the full tool return, addressing the baseline's known omission of printed structured feedback; this transport/prompt difference is a validity limitation. Fresh context and disabled environment tools prevent file access to the baseline. Native events show a general host skill catalog and permissions context were still injected despite the requested skip-host-skill-discovery setting, as in the Skill baseline; neither context included the robot Skill implementation or its successful trace. Thus the literal desired context-only restriction is not fully enforced by this runtime. Token comparisons include actual context differences and are not a controlled estimate of semantic-tool schema savings.

The semantic tool allowlist is audited against session_meta.dynamic_tools and native append_dynamic_tool_runtimes.dynamic_tool_count (four), not merge_into_namespaces.tool_spec_count (three native transport specs in both conditions). This offline audit-field correction does not change or rerun the episode. All six observed robot calls belong to the authorized four-tool allowlist.

No post-stop physical dwell test was added. Safe terminal evidence is limited to the recorded state, native turn termination and existing hold cleanup. The reused Skill baseline also has this limitation.

## Audit

{
  "initial_state_equivalent": true,
  "shared_sources_unchanged": true,
  "skill_baseline_files_unchanged": true,
  "native_usage_matches_thread_total": true,
  "native_usage_matches_rollout_total": true,
  "native_tool_count_matches": true,
  "only_four_semantic_tools": true,
  "physical_trace_time_matches": true,
  "native_timing_valid": true,
  "runtime_version_matches_skill": true
}

Errors: `[]`.

This single pair can inform a separately authorized CONTACT repeat plan if measurement checks pass; it remains **preliminary single-pair evidence**. No additional episodes have been started.
