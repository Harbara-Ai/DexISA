# Wuji2 real-hardware V-sign pilot — 2026-10-01

One fresh Agent per interface made a V sign (比耶) on the same real Wuji2 right hand, using **gpt-6.1-sol / xhigh**, no model fallback, and the same low-level SDK driver. DexISA exposed generic finger-shaping operands; Direct exposed native joint targets. Neither Agent received a V-sign target or prior Agent history. The operator judged both physical gestures **successful**; there was no automatic gesture evaluator. The live adapter and external Wuji driver used for this pilot remain local extensions.

**Starting poses differed:** after a reset did not meet its existing settling criterion, the operator accepted the current pose for Direct. The measured initial joint states differ by up to **0.1072768 rad**. This is one measured episode per interface with different starting poses; it does not establish comparative performance.

| Metric | DexISA | Direct |
| --- | ---: | ---: |
| Human gesture judgement | Success | Success |
| Measured episodes | 1 | 1 |
| Native total tokens | 43,797 | 55,528 |
| Input tokens | 42,766 | 53,926 |
| Cached input tokens (included in input) | 23,168 | 27,648 |
| Non-cached input tokens | 19,598 | 26,278 |
| Output tokens | 1,031 | 1,602 |
| Reasoning tokens (included in output) | 810 | 1,117 |
| Episode wall time (s) | 54.540 | 84.066 |
| Native inference time (s) | 48.326 | 77.799 |
| Motion-command intervals (s) | 4.009 | 4.516 |
| Shaping / joint-tool time (s) | 4.126 | 4.609 |
| Enabled interval (s) | 9.513 | 27.912 |
| Tool calls | 4 | 5 |
| Explicit state-query calls | 1 | 1 |
| Native inference responses | 4 | 5 |
| Motion calls | 1 `SHAPE_HAND` | 2 `set_joint_targets` |

In these two episodes, Direct used 11,731 more total tokens (+26.8%) and 29.526 s more episode wall time (+54.1%).

## Accounting and interpretation

Tokens are authoritative native usage, cross-checked between `thread/tokenUsage/updated` and the sum of `rawResponse/completed` events; both audits passed. Cached input is part of input, and reasoning is part of output. Episode wall time excludes setup, preceding resets, and operator-confirmation waits. Inference and robot-tool handling are components of episode wall time. Motion-command intervals measure driver execution, not visually measured physical movement. Direct's preceding reset lasted 60.004569 s and stopped before Agent creation. The operator then explicitly authorized the measured current pose for the separate Direct episode.

Both episodes retained a `VELOCITY_LIMIT` error after the SDK disable request. The operator judgement records successful hand shapes separately from these runtime errors.

The source episodes are `results_wuji2_v_sign_real_20261001_03` (DexISA) and `results_wuji2_v_sign_real_20261001_06` (Direct). Each used one fresh Agent with identical model/reasoning and the shared low-level real interface. No source/config hash differences were found between the compared runs. Other attempts and the OK-sign task are outside this table. CPU/GPU utilization, electrical energy, and billing amounts were not measured.

The receipt-age policy was `DIAGNOSTIC_ONLY` in both host and native bridge. Actual SDK/IPC errors and other existing protections remained recorded. Human success does not replace or erase recorded runtime errors.

## Published results and local archive

[Aggregate metrics JSON](2026-10-01-wuji2-v-sign-real-pilot.json) retains full-precision counts, times, comparison qualifiers and timing definitions. Figures were verified against each episode's original native metrics and driver timing records. The original local run archive retains native usage events, Agent decisions, tool arguments/results, initial/final joint samples, SDK diagnostics, errors and raw traces. This publication contains aggregate experiment results; raw hardware and runtime evidence remains local. Original historical artifacts are unchanged.

The pilot used a local real-hand extension based on upstream `5699359c836805ad5327a16696176eb78ac04ba5`. This commit adds README documentation and aggregate results; it does not change runtime, driver, SDK code or hardware state.
