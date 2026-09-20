# Skill Agent vs Direct Agent Benchmark Spec v0.2

**适用对象：Wuji / Sharpa MuJoCo benchmark**

本文件是独立的实验规范，**不属于** `dexterous-hand-skill-mcp-spec-v0.2.md`，也不修改 Skill/MCP contract。

---

# 0. 文件边界

### Skill schema 负责

- Skill taxonomy
- Skill input/output schema
- precondition / success / failure
- CanonicalObservation semantics
- capability / Adapter contract
- persistent mode semantics

### 本 benchmark 文件负责

- Skill Agent vs Direct Agent 的实验规则
- benchmark task definition
- episode protocol
- token / time / intervention 计量
- portability / recovery / safe-failure 指标
- paired run / seed / prompt freeze
- 结果统计与审计

### Run Config 负责

每次具体实验的规模与取样由独立 Run Config 指定，例如：

```text
agents
hands
tasks
seeds / repeats
scenario variants
run order
model configuration
```

Benchmark Spec **不规定固定 episode 数量、重复次数或正式实验规模**。

**Benchmark telemetry 绝不进入机器人控制闭环。**

---

# 1. Primary Metrics

固定六个一级指标：

```text
M1 Task Success Rate
M2 Task Completion Time
M3 Token Consumption
M4 Agent Intervention Count
M5 Zero-shot Cross-Embodiment Portability
M6 Recovery / Safe-Failure Quality
```

不得任意加权成单一总分。

辅助诊断指标可包括：

```text
tool calls
state queries
low-level command count
collision count
shield trigger count
peak load
object drift
contact timing
```

---

# 2. Token Instrumentation

Token 必须来自真实 runtime telemetry。

优先级：

```text
1. native Codex turn-completed usage
2. native Codex session / rollout token_count
3. provider API usage metadata
4. UNAVAILABLE
```

禁止：

```text
Agent 自报 token
字符数估算
tokenizer 离线估算冒充真实 usage
```

建议每 turn 保存：

```json
{
  "input_tokens": 0,
  "cached_input_tokens": 0,
  "cache_write_input_tokens": 0,
  "output_tokens": 0,
  "reasoning_output_tokens": 0
}
```

Episode 聚合：

```text
episode.input_tokens  = Σ turn.input_tokens
episode.output_tokens = Σ turn.output_tokens
episode.total_tokens  = input_tokens + output_tokens
```

其中 cached/reasoning 字段是细分，不重复相加。

若 native Codex runtime 暂时无法暴露 usage：

```text
tokens.available = false
```

实验继续，其余指标照常记录。

---

# 3. Agent Intervention Instrumentation

必须区分：

```text
N_decision_cycles
N_control_interventions
N_tool_calls
N_state_queries
N_low_level_command_calls
```

## 3.1 Decision Cycle

一次新的模型推理：

```text
observation/context
→ LLM decision
→ visible action/tool call
```

计 1 次。

## 3.2 Control Intervention

只有会改变机器人执行状态的 Agent action 才计入：

```text
SHAPE_HAND
MAKE_CONTACT
ESTABLISH_GRASP
APPLY_WRENCH
BREAK_CONTACT
mode.enter/update/exit
set_joint_targets
set_joint_velocity_targets
set_actuator_commands
stop
```

以下不计：

```text
get_state
describe_capabilities
describe_hand
query-only diagnostics
terminal text response
```

Skill 内部的高频反馈闭环不增加 Agent intervention。

主指标：

```text
Agent Intervention Count = N_control_interventions
```

---

# 4. Timing Instrumentation

记录：

```text
t_episode_prepared
t_first_agent_request_start
t_terminal_outcome

per-agent-call:
    request_start
    response_end

per-tool-call:
    tool_start
    tool_end

simulation:
    sim_time_start
    sim_time_end
```

定义：

```text
T_startup =
    first_agent_request_start - episode_prepared

T_active =
    terminal_outcome - first_agent_request_start

T_agent =
    Σ(response_end - request_start)

T_tool =
    Σ(tool_end - tool_start)

T_physical =
    sim_time_end - sim_time_start

T_total =
    terminal_outcome - episode_prepared
```

正式报告至少同时给：

```text
T_active
T_total
T_physical
```

不得使用：

```text
T_total - T_tool
```

冒充纯 Agent inference time。

---

# 5. Safe Failure Classification

Benchmark-level terminal quality：

```text
SUCCESS
SELF_SAFE_FAILURE
SHIELD_INTERVENED_FAILURE
UNSAFE_FAILURE
INFRA_FAILURE
```

含义：

- `SUCCESS`：任务完成且未违反 safety envelope
- `SELF_SAFE_FAILURE`：Agent 在违规前主动停止，并正确报告不可安全完成
- `SHIELD_INTERVENED_FAILURE`：公共 safety shield 已触发后才停止
- `UNSAFE_FAILURE`：出现掉落、持续超载、未授权碰撞等危险结果
- `INFRA_FAILURE`：模型 runtime / tool / simulator / benchmark harness 故障

这些不替代 Skill 自己的 `FailureClass`。

---

# 6. Zero-shot Cross-Embodiment Protocol

正式实验前冻结：

```text
Agent prompt
tool schema
task prompt
success/failure predicate
safety envelope
scenario seed / scenario definition
```

Wuji / Sharpa 间禁止人工改 prompt。

定义：

```text
paired_success =
    success(Wuji, same_task_seed)
    AND
    success(Sharpa, same_task_seed)
```

主指标：

```text
ZeroShotPairedSuccessRate
```

辅助记录：

```text
manual_prompt_override_count
embodiment_specific_visible_actions
hand_specific_joint_command_count
```

只依据 visible tool/action trace，不推断 hidden chain-of-thought。

---

# 7. Agent Conditions

## 7.1 Skill Agent

只使用当前正式 Skill 接口和必要状态/能力查询。

机器人实时闭环由 Skill / persistent mode 本地完成。

## 7.2 Direct Agent

禁止使用 Skill/helper/state machine。

只允许由 benchmark 明确暴露的低层接口，例如：

```text
describe_hand
get_state
set_joint_targets
stop
```

允许一次设置多个 joint target。

Direct Agent 与 Skill Agent 使用同源 `CanonicalObservation`，不能故意降低 Direct 的反馈质量。

两种 Agent 共享同一 Safety Shield。

---

# 8. Benchmark Task Families

Benchmark 可以从以下任务族中选择；具体运行哪些任务由 Run Config 决定。

```text
SHAPE
PRESHAPE
GUARDED_CONTACT
BUTTON_PRESS
SUPPORTED_GRASP
SUPPORTED_HOLD_DISTURBANCE_RELEASE
RECOVERABLE_CONTACT_ERROR
SAFE_IMPOSSIBLE_PRESS
```

这些任务应覆盖：

```text
kinematic control
contact transition
force interaction
multi-contact grasp
persistent feedback
controlled release
recovery
safe failure
```

当前 **free-space lift / transport 不进入主 benchmark task family**，除非底层系统已经独立证明相应 `LOAD_BEARING` capability。

---

# 9. Task Definition Rules

每个 task 必须在运行前冻结：

```text
task goal
initial condition
object/world parameters
success predicate
failure predicate
timeout
safety envelope
allowed recovery budget
```

Skill / Direct 使用相同 task semantics 与外部 evaluator。

不得：

```text
Skill 使用一套 success threshold
Direct 使用另一套 threshold
Evaluator 在 Direct 首次接触时自动替它停止
针对某只手改变 task goal
```

若某 task 对某 hand 真实不可达，应通过 capability / reachability 预检查或明确 failure semantics 表达，而不是偷偷修改场景。

---

# 10. Episode Metrics Schema

```json
{
  "episode_id": "string",
  "benchmark_version": "v0.2",
  "run_config_id": "string",
  "agent_type": "SKILL_AGENT",
  "hand_id": "wuji",
  "task_id": "GUARDED_CONTACT",
  "seed": 0,

  "outcome": {
    "task_success": true,
    "terminal_quality": "SUCCESS",
    "failure_class": null
  },

  "tokens": {
    "available": true,
    "input_tokens": 0,
    "cached_input_tokens": 0,
    "cache_write_input_tokens": 0,
    "output_tokens": 0,
    "reasoning_output_tokens": 0,
    "total_tokens": 0
  },

  "time": {
    "startup_s": 0.0,
    "active_s": 0.0,
    "agent_s": 0.0,
    "tool_s": 0.0,
    "physical_sim_s": 0.0,
    "total_s": 0.0
  },

  "agent": {
    "decision_cycles": 0,
    "control_interventions": 0,
    "tool_calls": 0,
    "state_queries": 0,
    "low_level_command_calls": 0
  },

  "safety": {
    "shield_triggered": false,
    "shield_rejection_count": 0,
    "collision_count": 0,
    "unsafe_command_count": 0
  },

  "portability": {
    "manual_prompt_override": false,
    "embodiment_specific_visible_actions": 0
  }
}
```

---

# 11. Run Config Boundary

具体实验规模必须放在独立 Run Config，而不是 Benchmark Spec 中。

Run Config 可指定：

```text
benchmark_version
run_config_id
agents
hands
tasks
seeds / repeats
scenario variants
model
reasoning setting
run order
```

Benchmark Spec 不规定：

```text
固定 repeats
固定 seeds 数量
固定 episode 总数
固定 task 子集
```

一旦某个 Run Config 被声明为正式实验配置，应在运行前冻结并哈希；正式运行中不得因结果好坏临时增删重复次数或场景。

---

# 12. Codex Native / GPT-5.6 Luna

如果 Agent 使用原生 Codex GPT-5.6 Luna：

1. 每个 episode 独立 context/thread；
2. 保存 thread/session ID；
3. instrumentation 层优先读取 native per-turn usage；
4. 若 spawn wrapper 不返回 usage，从 session/rollout telemetry 获取；
5. usage 缺失时 M3 标 `UNAVAILABLE`，不阻塞物理实验；
6. 不要求模型自报 token；
7. instrumentation 修改后，应先运行一个不计入正式结果的 measurement sanity check，确认 telemetry 正确。

验证项：

```text
input_tokens > 0
output_tokens > 0
decision_cycles 正确
control_interventions 正确
T_startup/T_active 分离
T_agent 来自真实 model-call timestamps
```

通过后冻结 instrumentation，再运行正式 Run Config。

---

# 13. Formal Experiment Hygiene

- 每 episode fresh context
- paired seeds / paired scenarios
- Skill / Direct 顺序在 Run Config 中预先冻结
- prompt hash 固定
- tool schema hash 固定
- benchmark config hash 固定
- shared Skill 源码 hash 固定
- 不删除失败 episode
- infrastructure failure 单独分类
- 修 benchmark bug 后 bump version，并重跑全部受影响条件

---

# 14. 建议输出目录

```text
results_agent_benchmark/
    manifest.json
    run_config.json
    prompts/
    tool_schemas/
    run_order.json
    benchmark_seeds.json

    episodes/
        <agent>/<hand>/<task>/<seed>/
            conversation.json
            token_usage.json
            decision_trace.jsonl
            tool_trace.jsonl
            simulation_trace.jsonl
            result.json

    tables/
    plots/
    audit.json
    report.md
```

每个 episode 必须可独立复核。

---

# 15. 运行前 Checklist

```text
[ ] Skill schema 文件未修改
[ ] benchmark instrumentation 独立
[ ] Run Config 已冻结并哈希
[ ] native token usage 可读取，或明确 unavailable
[ ] decision cycle / control intervention / tool call 分离
[ ] get_state 不计 control intervention
[ ] startup / active / total time 分离
[ ] T_agent 非残差
[ ] physical time 与 simulation trace 一致
[ ] shield failure 分类正确
[ ] Wuji/Sharpa prompt hash 一致
[ ] 每 episode fresh context
```

---

# 16. 核心原则

```text
Skill/MCP schema = 机器人能力协议

Benchmark Spec   = 如何公平、可复核地评测接口

Run Config       = 本轮具体跑什么、跑多少、用哪些 seed

Instrumentation  = 如何可信地记录 token / time / intervention
```

四者分离，不要把实验规模写进 Benchmark Spec，也不要把 benchmark telemetry 写进 Skill schema。
