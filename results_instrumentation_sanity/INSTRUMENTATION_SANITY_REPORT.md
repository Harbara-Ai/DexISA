# NON_FORMAL instrumentation sanity check

`formal = false`; `purpose = instrumentation_sanity_check`.

INSTRUMENTATION GATE: PASS

Exactly one Wuji / SKILL_AGENT / GUARDED_CONTACT episode ran, with native GPT-5.6 Luna and low reasoning. No reruns and no formal benchmark. These files are isolated from all benchmark CSV/statistics and support no Skill-vs-Direct performance conclusion.

| Metric | Value |
| --- | ---: |
| Outcome | SUCCESS |
| Input tokens | 7216 |
| Cached input tokens | 2816 |
| Output tokens | 65 |
| Reasoning output tokens | 14 |
| Total tokens | 7281 |
| T_startup | 1.418875400 |
| T_active | 4.577506900 |
| T_agent | 4.279016900 |
| T_tool | 0.169850000 |
| T_physical | 0.676000000 |
| T_total | 5.996382300 |
| Decision cycles | 2 |
| Control interventions | 1 |
| Tool calls | 1 |
| State queries | 0 |

All times are seconds. Cache-write input tokens: 0. Cached/reasoning tokens are breakdowns, not extra terms in the total.

Native thread/session: `01a0be2a-97ed-71c1-b6c2-6ae0781bfe1c`. Turn: `01a0be2a-984e-7ec2-ba40-5b1296a008a2`. Runtime: `0.155.0-alpha.9.2`. Resolved model and effort are verified against native sampling spans and rollout turn context.

Usage source: `native_turn_usage`, specifically two `rawResponse/completed` notifications. Both decision cycles share one native turn ID and have distinct response IDs. Their sum exactly matches native thread total and independently read session rollout total. The rollout is a cross-check, not the usage fallback. No model self-report, tokenizer, or character estimate was used.

Timing uses the native `responses_websocket.stream_request` span start/end for each inference. The warmup span is explicitly excluded. Request latency includes network/provider processing; it is not a claim about GPU-only compute. `run_sampling_request` spans are unsuitable here because they include tool draining. Tool boundaries use `perf_counter_ns`; episode/runtime boundaries use the same host UTC nanosecond clock. `T_agent` is never a residual. Raw timestamps and span IDs are preserved in decision_trace.jsonl.

The terminal boundary is receipt of native `turn/completed` with the independently established physical outcome; the final inference is included in tokens, decisions and active time. The earlier MAKE_CONTACT completion is separately saved as `t_physical_outcome`; execution.json preserves that original physical boundary. This avoids excluding terminal inference time while still charging its tokens. Simulator time pauses between tools. Physical elapsed time matches 338 recorded frames at 0.002 seconds each, excluding preshape/setup.

Observed semantic calls: MAKE_CONTACT. Queries and terminal responses do not count as control interventions. Runtime tool-builder telemetry reports exactly three semantic tool specs at every capture: get_state, describe_capabilities, MAKE_CONTACT. The native code-mode `exec` wrapper remains the runtime transport; its one call is recorded separately and is not an additional robot intervention. Native runtime automatically injected its skill catalog and permissions context; the supplied task prompt stayed short and no full robot Skill spec was sent. The model's wrapper did not print the structured MAKE_CONTACT return into the outer transcript, so contact success is certified by the host's saved tool result and simulation, not by a model success claim. This is not evidence about agent feedback quality.

The prepared state exactly matches the previously verified nominal Wuji CONTACT setup (qpos/qvel/ctrl/time/group targets/XML hash). Before/after hashes of Skill, adapter, world/safety code and assets match. MAKE_CONTACT continues to call the existing PilotEpisode dispatcher with no parameter changes.

Instrumentation changes are confined to scripts/instrumentation_sanity.py (native App Server client, local OTel collector, one-shot lock, three-tool dispatcher) and scripts/summarize_instrumentation_sanity.py (offline usage, span and trace audit). Legacy scripts/contact_native_bridge.py still contains the obsolete UNAVAILABLE/residual/all-calls-intervention fields and must not be used for formal measurement. This sanity runner is the verified replacement path; no formal-run authorization is implied.

Official runtime protocol reference: [Codex App Server](https://learn.chatgpt.com/docs/app-server). The installed runtime's experimental generated JSON schemas are saved under protocol_schema; they define RawResponseCompletedNotification and its token breakdown fields.

Audit checks: {"real_native_luna_low": true, "token_usage_available": true, "positive_input_output": true, "usage_matches_native_thread_total": true, "usage_matches_session_rollout": true, "valid_timing": true, "distinct_counts": true, "only_three_semantic_tools": true, "physical_episode_executed": true, "unchanged_implementation_and_assets": true, "identical_nominal_prepared_state": true, "no_infrastructure_error": true}
