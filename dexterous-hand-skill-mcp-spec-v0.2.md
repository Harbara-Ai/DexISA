# 灵巧手通用 Skill 接口规范 v0.2（Draft）

**面向 Wuji Hand / Sharpa Hand 的 MCP Server 接口定义**

核心目标：让同一个 Agent 通过同一套 **object-centric / interaction-centric** 接口控制不同灵巧手；不同 embodiment 的差异主要由 capability、kinematics、contact mapping、sensor estimator 与 low-level controller 吸收，而不是在 Agent 层维护两套动作脚本。

> v0.2 的核心变化：`(C, S, Y, T)` 继续保留，但从 **Skill 唯一身份** 降为 **Skill type descriptor**。Skill 是否应拆分，最终由 execution contract、闭环控制骨架、状态估计、guard、failure/recovery 语义共同决定。

---

## 0. 本文档的使用方式

- 第 1 章定义分层架构与四轴描述符。
- 第 2 章定义建议的 Skill taxonomy，以及各 Skill 的物理边界。
- 第 3 章给出共享类型的 JSON Schema（`$defs`）。
- 第 4 章给出 L2 Interaction Skill 的 MCP tool 定义。
- 第 5 章定义持续模式、任务宏、能力协商、状态与 belief 管理。
- 第 6 章定义 Adapter 实现契约与合规检查。
- 第 7 章给出第一阶段最小实现范围；第 8 章给出跨手验证实验。

JSON Schema 采用 **draft 2020-12**。所有 `$ref` 指向第 3 章 `$defs`；实际部署时可以合并为单个 `schema.json`。

### 0.1 v0.1 → v0.2 主要变化

1. `(C,S,Y,T)` 不再充当 Skill 唯一坐标；允许不同 Skill 拥有相同四轴描述，只要 execution contract 明显不同。
2. `C` 从单一 `contact_mode` enum 重构为 **contact set / contact graph + topology transition**；`multi_point` 不再与 `point/surface` 混为同一维度。
3. `S` 从 `hand/environment/hand+environment` 单值重构为 **Constraint Allocation + Mobility Model**，显式表达哪些自由度由环境约束、哪些由手驱动。
4. `Y` 增加 `hand_configuration` 与 `contact_motion`，继续分离 controlled variable 与 control law。
5. `SET_HAND_POSTURE` 与 `PRESHAPE` 在 L2 合并为 `SHAPE_HAND`，通过 `goal.type` 区分；上层仍可保留语义宏。
6. `SEEK_CONTACT` 更名为 `MAKE_CONTACT`，定义为 `no-contact → contact` 的物理状态迁移。
7. `PRESS` 不再同时承担接近与施力；`press_button = MAKE_CONTACT → APPLY_WRENCH → BREAK_CONTACT`。
8. `MOVE_OBJECT_IN_HAND` 扩展为 `MANIPULATE_IN_CONTACT`，覆盖 intrinsic / extrinsic manipulation；Agent 声明允许/禁止的 stick/roll/slide 约束，Adapter 选择实现。
9. `EXPLOIT_EXTRINSIC` 不再作为独立基础 Skill，而作为 `MANIPULATE_IN_CONTACT` 的 constraint allocation / environment resource 参数化实例。
10. `APPLY_WRENCH_WITH_OBJECT` 与直接 `PRESS` 统一为 `APPLY_WRENCH`，通过 actor 指定“手直接施力”或“持物施力”。
11. `TURN_CONSTRAINED` 下沉为通用 `FOLLOW_CONSTRAINT`；旋钮、抽屉、门把手只是 mobility model 参数。
12. `VirtualFingerRole = VF1/VF2/VF3` 改为动态 `VirtualContactGroup`，避免固定三组接触。
13. 物体自身属性与接触对属性分离：`ObjectBelief` 不再把 friction 当成物体单体属性；新增 `ContactPairBelief`。
14. `ScalarEstimate` 不再强制伪装成 95% CI；支持 exact / bounded / gaussian / heuristic / unknown。
15. `ForceWindow` 降为可选 summary；抓取统一用 `GraspFeasibility` 与有明确定义的 `task_wrench_margin`。
16. 持续 mode 必须在本地闭环自主保证安全；Agent 只做 enter/update/query/exit，不参与实时 regulation。
17. 跨手合规从“内部 Skill 序列编辑距离为 0”改为“Agent-visible contract 不因 Adapter 改变”。

---

# 1. 分层架构与四轴描述符

## 1.1 四层架构

本规范区分四个层级：

```text
L3  Task / Agent Operator
    PICK, PLACE, PRESS_BUTTON, TURN_KNOB, REGRASP, PROBE_OBJECT ...

L2  Interaction Skill Contract
    SHAPE_HAND
    MAKE_CONTACT
    ESTABLISH_GRASP
    MANIPULATE_IN_CONTACT
    CHANGE_CONTACTS
    APPLY_WRENCH
    FOLLOW_CONSTRAINT
    BREAK_CONTACT
    PROBE_INTERACTION

L1  Persistent Interaction Mode
    MAINTAIN_GRASP
    SUPPORT

L0  Embodiment Policy / Controller / Adapter
    Wuji-specific / Sharpa-specific
```

- **L3** 面向 Agent 的任务语义组合，不应携带具体关节信息。
- **L2** 是 MCP 的核心“物理交互 ABI”。
- **L1** 是持续运行的本地闭环模式，不以一次 request/response 表达。
- **L0** 可以使用轨迹、IK、QP、阻抗、MPC、RL、ACT、Diffusion Policy 等任意实现，只要满足上层 contract。

## 1.2 `(C, S, Y, T)` 的角色

v0.2 继续使用：

```text
SkillDescriptor = (C, S, Y, T)
```

但它的含义是：

> **描述一个 Skill 的物理交互类型、做规划过滤与运行时一致性检查，而不是唯一确定 Skill identity。**

两个行为即使 `(C,S,Y,T)` 相同，只要下列要素有根本差异，仍允许拆成不同 Skill：

- state estimator；
- invariants；
- hybrid guards；
- success predicate；
- failure taxonomy；
- recovery skeleton；
- sensor requirements；
- 主导动力学模型。

反之，如果这些 execution contract 完全相同，仅目标值、尺寸、速度、力阈值、物体参数不同，则应保持为同一个 Skill。

### 1.2.1 Skill identity 判据

建议采用：

```text
SkillIdentity =
    Preconditions
  + StateEstimatorContract
  + ControlObjective
  + Invariants
  + Guards
  + SuccessPredicate
  + FailureSemantics
  + RecoverySkeleton
```

四轴只作为该 identity 的结构化 descriptor。

---

## 1.3 C — Contact Transition

### 1.3.1 不再使用单值 contact_mode

`point / surface / multi_point / enveloping` 混合了局部几何、接触数量与全局抓取拓扑，因此 v0.2 将运行时接触状态表示为 **ContactState.contacts[]**。

每个接触至少描述：

```text
contact_id
actor_group_id
object_id / environment_id
target_region
geometry      = point | line | patch
motion_mode   = unknown | stick | slide | roll | separating
confidence
```

其中：

- `multi-contact` 由 `contacts.length > 1` 自然得到，不是 geometry enum；
- `enveloping` 属于 grasp topology / grasp class，不属于单个 contact geometry；
- `edge` 更适合作为 `target_region.feature_type`，而不是 contact geometry；
- `grasp` 由多接触 + task stability / closure 性质描述，不作为 contact geometry。

### 1.3.2 C 描述的是 predicate transition

一个 Skill 的 C 轴不应记录某个具体对象的 contact list，而应记录：

```text
C = (
    contact_precondition,
    contact_postcondition,
    topology_effect
)
```

其中：

```text
topology_effect = preserve | add | remove | replace | task_defined
```

例：

```text
SHAPE_HAND:
    no_contact → no_contact
    topology_effect = preserve

MAKE_CONTACT:
    no_required_contact → required_contact_present
    topology_effect = add

CHANGE_CONTACTS:
    stable_contact_set_A → stable_contact_set_B
    topology_effect = replace

BREAK_CONTACT:
    target_contacts_present → target_contacts_absent
    topology_effect = remove
```

---

## 1.4 S — Constraint Allocation

v0.1 的：

```text
hand | environment | hand_and_environment
```

只描述“谁在提供约束”，但无法表达约束是方向性的。

例如桌面 pushing：

- 环境限制 object 的 `z / roll / pitch`；
- 手驱动 `x / y / yaw`；
- 因此不能简单描述成 `environment`。

v0.2 定义：

```text
S = ConstraintAllocation(
    mobility_model,
    hand_roles[],
    environment_roles[]
)
```

角色可为：

```text
support | constrain | actuate | stabilize
```

`MobilityModel` 描述物体在当前交互下允许的运动流形：

```text
free_6d
planar
axial
prismatic
revolute
fixed
custom
```

例如：

```text
桌面 pushing:
    mobility = planar
    hand_roles = [actuate]
    environment_roles = [support, constrain]

in-hand manipulation:
    mobility = free_6d
    hand_roles = [support, constrain, actuate]
    environment_roles = []

edge-assisted pivot:
    mobility = custom/revolute
    hand_roles = [actuate, stabilize]
    environment_roles = [support, constrain]
```

---

## 1.5 Y — Control Objective

继续分离“控制什么”和“怎么控制”。

### Controlled Variables

```text
hand_configuration
palm_pose
object_pose
contact_force
interaction_wrench
contact_motion
```

### Control Law

```text
position
velocity
force
impedance
admittance
hybrid_force_position
policy
```

其中 `policy` 表示实现由学习策略直接产生动作，但仍必须满足 L2 contract；它不是逃避控制语义定义的通配符。

若按方向混合位置/力控制，使用 `selection_matrix` 或等价的 task-space decomposition 显式声明。

---

## 1.6 T — Termination Semantics

```text
goal
event_guarded
duration
continuous
```

- `goal`：达到目标状态；
- `event_guarded`：由外部事件触发，如检测到 contact、按钮 click、seated；
- `duration`：指定持续时间；
- `continuous`：没有自然终止，必须由 `robot.mode.*` 表达。

`periodic` 不作为独立 T；finger gaiting 等周期行为以 `goal + internal loop` 实现。

---

# 2. 建议的 Skill taxonomy

## 2.1 L2 Interaction Skills

| Skill | 物理定义 | Contact effect | 主要控制对象 | 典型 T |
|---|---|---|---|---|
| `SHAPE_HAND` | 无接触下改变手部构形，或生成 object-conditioned preshape | preserve no-contact | hand_configuration | goal |
| `MAKE_CONTACT` | 受控运动直到建立指定接触集合 | add | hand_configuration / contact_force | event_guarded |
| `ESTABLISH_GRASP` | 从部分接触进入满足 task wrench 的稳定抓取 | preserve/add | contact_force / task stability | goal |
| `MANIPULATE_IN_CONTACT` | 在不发生未授权 topology change 的条件下改变物体位姿 | preserve | object_pose + contact_force + contact_motion | goal |
| `CHANGE_CONTACTS` | 有意改变 contact graph，同时避免物体失控 | replace/add/remove | hand_configuration + contact_force | goal |
| `APPLY_WRENCH` | 在已有接触下建立目标 interaction wrench | preserve | interaction_wrench | goal/event/duration |
| `FOLLOW_CONSTRAINT` | 沿已知/在线估计的 mobility manifold 运动 | preserve | pose + off-manifold wrench | goal |
| `BREAK_CONTACT` | 受控解除指定接触，确保对象已有安全支撑或明确授权掉落 | remove | contact_force + hand_configuration | goal |
| `PROBE_INTERACTION` | 在安全激励下主动降低物性/约束不确定性 | task_defined | excitation + observation | goal |

## 2.2 L1 Persistent Modes

| Mode | 定义 |
|---|---|
| `MAINTAIN_GRASP` | 持续维持 task wrench margin、抗滑与材料安全约束 |
| `SUPPORT` | 持续保持非闭合支撑关系，如掌面托举 |

持续 mode 必须由本地控制器自主维持 invariant。LLM/Agent **不得**参与毫秒级闭环，也不得作为唯一安全监督器。

## 2.3 L3 Task / Agent Operators

建议将下列行为定义为宏，而不是新的基础 Skill：

```text
PICK_AND_HOLD
PLACE
PRESS_BUTTON
PUSH_OBJECT
TURN_CONSTRAINED
REGRASP
VERIFY_GRASP
PROBE_OBJECT
```

示例：

```text
PRESS_BUTTON
= SHAPE_HAND(profile=POINT)
→ MAKE_CONTACT
→ APPLY_WRENCH(actor=hand)
→ BREAK_CONTACT

TURN_CONSTRAINED
= MAKE_CONTACT / ESTABLISH_GRASP
→ FOLLOW_CONSTRAINT(mobility=revolute)

PUSH_OBJECT
= MAKE_CONTACT
→ MANIPULATE_IN_CONTACT(mobility=planar)
→ BREAK_CONTACT
```

## 2.4 Coverage 检查原则

v0.2 不再要求“每个新 Skill 必须占据一个空 `(S×C)` cell”。

CI 应检查：

1. Skill descriptor 是否自洽；
2. pre/post contact predicate 是否可判定；
3. capability requirement 是否可协商；
4. success/failure 是否结构化；
5. 两个 Skill 若 descriptor 相同，是否有明确的 execution-contract 差异说明；
6. 两个 Skill 若 execution contract 实际相同，是否只是重复命名。

---

# 3. 共享类型定义（`$defs`）

以下 schema 是 v0.2 的建议基线。为可读性，一些复杂数学对象使用结构化摘要，而不是在 MCP 层暴露完整优化器内部变量。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://robot.local/schemas/dexterous-hand/v0.2",
  "$defs": {

    "Vec3": {
      "type": "array",
      "items": { "type": "number" },
      "minItems": 3,
      "maxItems": 3
    },

    "Quat": {
      "type": "array",
      "description": "四元数 [x, y, z, w]",
      "items": { "type": "number" },
      "minItems": 4,
      "maxItems": 4
    },

    "Frame": {
      "type": "string",
      "description": "所有位姿、方向、wrench 必须显式声明参考系。",
      "enum": [
        "world",
        "palm",
        "object",
        "contact",
        "support_surface",
        "constraint_axis",
        "tool"
      ]
    },

    "Pose": {
      "type": "object",
      "properties": {
        "frame": { "$ref": "#/$defs/Frame" },
        "position": { "$ref": "#/$defs/Vec3" },
        "orientation": { "$ref": "#/$defs/Quat" }
      },
      "required": ["frame", "position", "orientation"],
      "additionalProperties": false
    },

    "Wrench": {
      "type": "object",
      "properties": {
        "frame": { "$ref": "#/$defs/Frame" },
        "force": { "$ref": "#/$defs/Vec3", "description": "N" },
        "torque": { "$ref": "#/$defs/Vec3", "description": "N·m" }
      },
      "required": ["frame", "force", "torque"],
      "additionalProperties": false
    },

    "EstimateSource": {
      "type": "string",
      "enum": [
        "prior",
        "user_specified",
        "vision",
        "proprioceptive_estimate",
        "tactile",
        "force_torque",
        "current_estimate",
        "interaction_probe",
        "simulation_ground_truth",
        "derived"
      ]
    },

    "UncertaintyType": {
      "type": "string",
      "enum": ["exact", "bounded", "gaussian", "heuristic", "unknown"]
    },

    "ScalarEstimate": {
      "type": "object",
      "description": "物理标量的估计。不得用伪造 CI 表示非统计不确定性。",
      "properties": {
        "value": { "type": "number" },
        "unit": { "type": "string" },
        "uncertainty_type": { "$ref": "#/$defs/UncertaintyType" },
        "bounds": {
          "type": "array",
          "items": { "type": "number" },
          "minItems": 2,
          "maxItems": 2,
          "description": "[lower, upper]；仅 bounded/heuristic 时通常使用"
        },
        "stddev": {
          "type": "number",
          "minimum": 0,
          "description": "仅 gaussian 时使用"
        },
        "confidence": {
          "type": "number",
          "minimum": 0,
          "maximum": 1,
          "description": "启发式可信度，不等同于统计置信区间"
        },
        "source": { "$ref": "#/$defs/EstimateSource" },
        "timestamp": { "type": "number", "description": "Unix 秒" }
      },
      "required": ["unit", "uncertainty_type", "source"],
      "additionalProperties": false
    },

    "Vec3Estimate": {
      "type": "object",
      "properties": {
        "value": { "$ref": "#/$defs/Vec3" },
        "unit": { "type": "string" },
        "uncertainty_type": { "$ref": "#/$defs/UncertaintyType" },
        "radius_bound": { "type": "number", "minimum": 0 },
        "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
        "source": { "$ref": "#/$defs/EstimateSource" }
      },
      "required": ["unit", "uncertainty_type", "source"],
      "additionalProperties": false
    },

    "OppositionType": {
      "type": "string",
      "enum": ["PALM", "PAD", "SIDE"]
    },

    "GraspClass": {
      "type": "string",
      "enum": ["POWER", "PRECISION", "INTERMEDIATE", "HOOK"]
    },

    "VirtualContactRole": {
      "type": "string",
      "enum": ["opposition", "support", "stabilization", "manipulation", "actuation"]
    },

    "TargetRegion": {
      "type": "object",
      "properties": {
        "object_id": { "type": "string" },
        "region_id": { "type": "string" },
        "center": { "$ref": "#/$defs/Vec3" },
        "normal": { "$ref": "#/$defs/Vec3" },
        "radius": { "type": "number", "minimum": 0 },
        "feature_type": {
          "type": "string",
          "enum": ["surface", "edge", "vertex", "handle", "fixture", "unknown"]
        }
      },
      "required": ["object_id"],
      "additionalProperties": false
    },

    "VirtualContactGroup": {
      "type": "object",
      "description": "跨 embodiment 的功能接触组。数量不固定，Adapter 映射到具体 fingers/links。",
      "properties": {
        "group_id": { "type": "string" },
        "role": { "$ref": "#/$defs/VirtualContactRole" },
        "target_region": { "$ref": "#/$defs/TargetRegion" },
        "required": { "type": "boolean", "default": true },
        "min_contact_count": { "type": "integer", "minimum": 1, "default": 1 }
      },
      "required": ["group_id", "role"],
      "additionalProperties": false
    },

    "ContactGeometry": {
      "type": "string",
      "enum": ["point", "line", "patch"]
    },

    "ContactMotionMode": {
      "type": "string",
      "enum": ["unknown", "stick", "slide", "roll", "separating"]
    },

    "ClosureClass": {
      "type": "string",
      "enum": ["none", "force_closure", "form_closure", "unknown"]
    },

    "ContactObservation": {
      "type": "object",
      "properties": {
        "contact_id": { "type": "string" },
        "actor_group_id": { "type": "string" },
        "counterpart_id": { "type": "string" },
        "target_region": { "$ref": "#/$defs/TargetRegion" },
        "geometry": { "$ref": "#/$defs/ContactGeometry" },
        "motion_mode": { "$ref": "#/$defs/ContactMotionMode" },
        "position": { "$ref": "#/$defs/Vec3" },
        "normal": { "$ref": "#/$defs/Vec3" },
        "normal_force_n": { "type": "number" },
        "slip_indicator": { "type": "number", "minimum": 0, "maximum": 1 },
        "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
        "adapter_link": {
          "type": "string",
          "description": "仅调试使用。Agent 不得据此做跨手控制决策。"
        }
      },
      "required": ["contact_id", "confidence"],
      "additionalProperties": false
    },

    "TaskStability": {
      "type": "object",
      "description": "跨手统一的 task-wrench 稳定性摘要。margin >= 1 表示在当前 belief、安全与执行器约束下可覆盖 required wrench set。",
      "properties": {
        "task_wrench_margin": { "type": "number", "minimum": 0 },
        "required_wrench_set_id": { "type": "string" },
        "feasible": { "type": "boolean" },
        "metric_version": { "type": "string", "default": "task_wrench_ratio_v1" }
      },
      "required": ["feasible", "metric_version"],
      "additionalProperties": false
    },

    "ContactState": {
      "type": "object",
      "properties": {
        "contacts": {
          "type": "array",
          "items": { "$ref": "#/$defs/ContactObservation" }
        },
        "closure_class": { "$ref": "#/$defs/ClosureClass" },
        "task_stability": { "$ref": "#/$defs/TaskStability" }
      },
      "required": ["contacts", "closure_class"],
      "additionalProperties": false
    },

    "TopologyEffect": {
      "type": "string",
      "enum": ["preserve", "add", "remove", "replace", "task_defined"]
    },

    "ContactPredicate": {
      "type": "object",
      "properties": {
        "min_contacts": { "type": "integer", "minimum": 0 },
        "max_contacts": { "type": "integer", "minimum": 0 },
        "required_group_ids": {
          "type": "array",
          "items": { "type": "string" }
        },
        "allowed_motion_modes": {
          "type": "array",
          "items": { "$ref": "#/$defs/ContactMotionMode" }
        },
        "closure_any_of": {
          "type": "array",
          "items": { "$ref": "#/$defs/ClosureClass" }
        }
      },
      "additionalProperties": false
    },

    "MobilityType": {
      "type": "string",
      "enum": ["free_6d", "planar", "axial", "prismatic", "revolute", "fixed", "custom"]
    },

    "MobilityModel": {
      "type": "object",
      "properties": {
        "type": { "$ref": "#/$defs/MobilityType" },
        "frame": { "$ref": "#/$defs/Frame" },
        "dof": { "type": "integer", "minimum": 0, "maximum": 6 },
        "axis_origin": { "$ref": "#/$defs/Vec3" },
        "axis_direction": { "$ref": "#/$defs/Vec3" },
        "confidence": { "type": "number", "minimum": 0, "maximum": 1 }
      },
      "required": ["type"],
      "additionalProperties": false
    },

    "ConstraintRole": {
      "type": "string",
      "enum": ["support", "constrain", "actuate", "stabilize"]
    },

    "ConstraintAllocation": {
      "type": "object",
      "properties": {
        "mobility": { "$ref": "#/$defs/MobilityModel" },
        "hand_roles": {
          "type": "array",
          "items": { "$ref": "#/$defs/ConstraintRole" },
          "uniqueItems": true
        },
        "environment_roles": {
          "type": "array",
          "items": { "$ref": "#/$defs/ConstraintRole" },
          "uniqueItems": true
        }
      },
      "required": ["mobility", "hand_roles", "environment_roles"],
      "additionalProperties": false
    },

    "ConstraintDescriptor": {
      "description": "Skill 若允许多种 constraint allocation，descriptor 必须显式标记 parameterized，而不是伪造一个固定 S。",
      "oneOf": [
        { "$ref": "#/$defs/ConstraintAllocation" },
        {
          "type": "object",
          "properties": {
            "parameterized": { "const": true },
            "allowed_mobility_types": {
              "type": "array",
              "items": { "$ref": "#/$defs/MobilityType" },
              "minItems": 1,
              "uniqueItems": true
            }
          },
          "required": ["parameterized", "allowed_mobility_types"],
          "additionalProperties": false
        }
      ]
    },

    "ControlledVariable": {
      "type": "string",
      "enum": [
        "hand_configuration",
        "palm_pose",
        "object_pose",
        "contact_force",
        "interaction_wrench",
        "contact_motion"
      ]
    },

    "ControlLaw": {
      "type": "string",
      "enum": [
        "position",
        "velocity",
        "force",
        "impedance",
        "admittance",
        "hybrid_force_position",
        "policy"
      ]
    },

    "TerminationSemantics": {
      "type": "string",
      "enum": ["goal", "event_guarded", "duration", "continuous"]
    },

    "SkillDescriptor": {
      "type": "object",
      "description": "Skill 的四轴 type descriptor，不是 Skill 唯一身份。",
      "properties": {
        "name": { "type": "string" },
        "contact_pre": { "$ref": "#/$defs/ContactPredicate" },
        "contact_post": { "$ref": "#/$defs/ContactPredicate" },
        "topology_effect": { "$ref": "#/$defs/TopologyEffect" },
        "constraint_allocation": { "$ref": "#/$defs/ConstraintDescriptor" },
        "controlled_variables": {
          "type": "array",
          "items": { "$ref": "#/$defs/ControlledVariable" },
          "minItems": 1,
          "uniqueItems": true
        },
        "control_laws": {
          "type": "array",
          "items": { "$ref": "#/$defs/ControlLaw" },
          "minItems": 1,
          "uniqueItems": true
        },
        "termination": {
          "type": "array",
          "items": { "$ref": "#/$defs/TerminationSemantics" },
          "minItems": 1,
          "uniqueItems": true
        },
        "contract_note": {
          "type": "string",
          "description": "若与其他 Skill 四轴 descriptor 相同，说明 execution-contract 差异。"
        }
      },
      "required": [
        "name",
        "contact_pre",
        "contact_post",
        "topology_effect",
        "constraint_allocation",
        "controlled_variables",
        "control_laws",
        "termination"
      ],
      "additionalProperties": false
    },

    "ObjectBelief": {
      "type": "object",
      "description": "仅包含对象自身属性，不包含依赖接触对的 friction/compliance。",
      "properties": {
        "object_id": { "type": "string" },
        "label": {
          "type": "string",
          "description": "仅日志/人类可读。禁止以语义标签直接驱动低层控制分支。"
        },
        "geometry": {
          "type": "object",
          "properties": {
            "primitive": {
              "type": "string",
              "enum": ["box", "cylinder", "sphere", "cone", "mesh", "unknown"]
            },
            "dimensions_m": { "$ref": "#/$defs/Vec3" },
            "pose": { "$ref": "#/$defs/Pose" },
            "mesh_id": { "type": "string" }
          },
          "required": ["primitive"],
          "additionalProperties": false
        },
        "mass": { "$ref": "#/$defs/ScalarEstimate" },
        "com_offset": { "$ref": "#/$defs/Vec3Estimate" },
        "inertia_diag": { "$ref": "#/$defs/Vec3Estimate" },
        "contents": {
          "type": "object",
          "properties": {
            "has_liquid": { "type": "boolean", "default": false },
            "fill_ratio": { "type": "number", "minimum": 0, "maximum": 1 },
            "keep_upright_required": { "type": "boolean", "default": false },
            "max_tilt_rad": { "type": "number", "minimum": 0 }
          },
          "additionalProperties": false
        }
      },
      "required": ["object_id", "geometry"],
      "additionalProperties": false
    },

    "ContactPairBelief": {
      "type": "object",
      "description": "接触属性属于 object region × counterpart surface 的 pair，不属于物体单体。",
      "properties": {
        "pair_id": { "type": "string" },
        "object_id": { "type": "string" },
        "object_region_id": { "type": "string" },
        "counterpart_surface_class": {
          "type": "string",
          "description": "如 fingertip_pad / finger_side / palm / table_surface；具体材料映射由 Adapter 提供。"
        },
        "mu_static": { "$ref": "#/$defs/ScalarEstimate" },
        "mu_dynamic": { "$ref": "#/$defs/ScalarEstimate" },
        "normal_compliance_m_per_n": { "$ref": "#/$defs/ScalarEstimate" },
        "max_pressure_pa": { "$ref": "#/$defs/ScalarEstimate" }
      },
      "required": ["pair_id", "object_id", "counterpart_surface_class"],
      "additionalProperties": false
    },

    "RequiredWrenchSet": {
      "type": "object",
      "properties": {
        "set_id": { "type": "string" },
        "vertices": {
          "type": "array",
          "items": { "$ref": "#/$defs/Wrench" },
          "minItems": 1
        },
        "description": { "type": "string" }
      },
      "required": ["set_id", "vertices"],
      "additionalProperties": false
    },

    "ContactForceTarget": {
      "type": "object",
      "properties": {
        "group_id": { "type": "string" },
        "normal_force_n": { "type": "number", "minimum": 0 },
        "min_normal_force_n": { "type": "number", "minimum": 0 },
        "max_normal_force_n": { "type": "number", "minimum": 0 }
      },
      "required": ["group_id", "normal_force_n"],
      "additionalProperties": false
    },

    "GraspFeasibility": {
      "type": "object",
      "description": "基于当前 contact plan、belief、执行器限制和 required wrench set 的任务抓取可行性。",
      "properties": {
        "feasible": { "type": "boolean" },
        "required_wrench_set_id": { "type": "string" },
        "task_wrench_margin": {
          "type": "number",
          "minimum": 0,
          "description": ">=1 表示覆盖 required wrench set；越大裕度越高。"
        },
        "contact_force_targets": {
          "type": "array",
          "items": { "$ref": "#/$defs/ContactForceTarget" }
        },
        "limiting_constraints": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": [
              "friction",
              "pressure",
              "actuator",
              "geometry",
              "reachability",
              "external_wrench",
              "uncertainty"
            ]
          },
          "uniqueItems": true
        },
        "summary_force_window_n": {
          "type": "array",
          "items": { "type": "number" },
          "minItems": 2,
          "maxItems": 2,
          "description": "仅作简单 pinch 的人类可读 summary，不作为通用 grasp 物理模型。"
        }
      },
      "required": ["feasible", "required_wrench_set_id"],
      "additionalProperties": false
    },

    "BeliefUpdate": {
      "type": "object",
      "description": "Skill/Mode 同时承担估计信息回传。",
      "properties": {
        "target_kind": {
          "type": "string",
          "enum": ["object", "contact_pair", "constraint"]
        },
        "target_id": { "type": "string" },
        "field": { "type": "string" },
        "scalar_estimate": { "$ref": "#/$defs/ScalarEstimate" },
        "vector_estimate": { "$ref": "#/$defs/Vec3Estimate" },
        "rationale": { "type": "string" }
      },
      "required": ["target_kind", "target_id", "field"],
      "oneOf": [
        { "required": ["scalar_estimate"] },
        { "required": ["vector_estimate"] }
      ],
      "additionalProperties": false
    },

    "FailureClass": {
      "type": "string",
      "enum": [
        "PRECONDITION_FAILED",
        "NOT_SUPPORTED",
        "INFEASIBLE_INTERACTION",
        "INFEASIBLE_GRASP",
        "UNREACHABLE",
        "APERTURE_EXCEEDED",
        "NO_CONTACT_FOUND",
        "PREMATURE_CONTACT",
        "INCOMPLETE_CONTACT_SET",
        "UNEXPECTED_CONTACT_MODE",
        "OBJECT_DISPLACED",
        "CONTACT_LOST",
        "SLIP_UNRECOVERABLE",
        "OBJECT_DROPPED",
        "OBJECT_EJECTED",
        "DEFORMATION_LIMIT",
        "PRESSURE_LIMIT",
        "INSUFFICIENT_TASK_MARGIN",
        "INSUFFICIENT_REMAINING_STABILITY",
        "JAMMED",
        "CONSTRAINT_ESTIMATE_ERROR",
        "POSE_ERROR_EXCEEDED",
        "WRENCH_LIMIT_EXCEEDED",
        "TIMEOUT",
        "COLLISION",
        "ACTUATOR_LIMIT",
        "SENSOR_UNAVAILABLE",
        "LOCAL_RECOVERY_EXHAUSTED",
        "ABORTED_BY_SUPERVISOR"
      ]
    },

    "RecoveryHint": {
      "type": "object",
      "properties": {
        "action": {
          "type": "string",
          "enum": [
            "retry_same_params",
            "retry_with_larger_aperture",
            "retry_with_lower_speed",
            "retry_with_higher_force_margin",
            "reobserve_object_pose",
            "probe_contact_property",
            "switch_opposition_type",
            "switch_grasp_class",
            "increase_contact_area",
            "change_contact_plan",
            "use_environment_support",
            "use_two_hands",
            "regrasp",
            "request_human_assistance",
            "abort_task"
          ]
        },
        "param_overrides": { "type": "object", "additionalProperties": true },
        "confidence": { "type": "number", "minimum": 0, "maximum": 1 }
      },
      "required": ["action"],
      "additionalProperties": false
    },

    "SkillOutcome": {
      "type": "object",
      "properties": {
        "status": {
          "type": "string",
          "enum": ["SUCCESS", "FAILED", "ABORTED", "NOT_SUPPORTED", "INFEASIBLE"]
        },
        "skill": { "type": "string" },
        "achieved": {
          "type": "object",
          "properties": {
            "contact_state": { "$ref": "#/$defs/ContactState" },
            "object_pose_est": { "$ref": "#/$defs/Pose" },
            "hand_pose": { "$ref": "#/$defs/Pose" },
            "task_stability": { "$ref": "#/$defs/TaskStability" },
            "duration_s": { "type": "number" }
          },
          "additionalProperties": false
        },
        "belief_updates": {
          "type": "array",
          "items": { "$ref": "#/$defs/BeliefUpdate" }
        },
        "residual_uncertainty": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "field": { "type": "string" },
              "note": { "type": "string" }
            },
            "required": ["field"],
            "additionalProperties": false
          }
        },
        "local_recovery_applied": {
          "type": "array",
          "items": { "type": "string" },
          "description": "本地控制器已自主执行的 bounded recovery。"
        },
        "failure_class": { "$ref": "#/$defs/FailureClass" },
        "failure_detail": { "type": "string" },
        "suggested_recovery": {
          "type": "array",
          "items": { "$ref": "#/$defs/RecoveryHint" }
        },
        "adapter_diagnostics": {
          "type": "object",
          "description": "仅调试。Agent 不得依赖该字段形成跨 embodiment 控制逻辑。",
          "additionalProperties": true
        }
      },
      "required": ["status", "skill"],
      "allOf": [
        {
          "if": { "properties": { "status": { "const": "FAILED" } } },
          "then": { "required": ["failure_class"] }
        },
        {
          "if": { "properties": { "status": { "const": "INFEASIBLE" } } },
          "then": { "required": ["failure_class", "suggested_recovery"] }
        },
        {
          "if": { "properties": { "status": { "const": "NOT_SUPPORTED" } } },
          "then": { "required": ["failure_detail"] }
        }
      ],
      "additionalProperties": false
    },

    "HandCapabilityModel": {
      "type": "object",
      "description": "Adapter 启动时声明。能力不足必须显式 NOT_SUPPORTED，禁止静默降级。",
      "properties": {
        "hand_id": { "type": "string" },
        "backend": { "type": "string", "enum": ["hardware", "simulation"] },
        "dof": { "type": "integer", "minimum": 1 },
        "n_fingers": { "type": "integer", "minimum": 1 },
        "semantic_postures": {
          "type": "array",
          "items": { "type": "string" }
        },
        "opposition_types": {
          "type": "array",
          "items": { "$ref": "#/$defs/OppositionType" }
        },
        "grasp_classes": {
          "type": "array",
          "items": { "$ref": "#/$defs/GraspClass" }
        },
        "aperture_range_m": {
          "type": "array",
          "items": { "type": "number" },
          "minItems": 2,
          "maxItems": 2
        },
        "surface_classes": {
          "type": "array",
          "items": { "type": "string" },
          "description": "如 fingertip_pad / finger_side / palm，用于 ContactPairBelief。"
        },
        "sensing": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": [
              "joint_position",
              "joint_velocity",
              "joint_current",
              "joint_torque",
              "fingertip_force",
              "tactile_array",
              "contact_binary",
              "vision_object_pose",
              "sim_contact_truth"
            ]
          },
          "uniqueItems": true
        },
        "control_interfaces": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": [
              "joint_position",
              "joint_velocity",
              "joint_effort",
              "task_impedance",
              "task_admittance",
              "contact_force"
            ]
          },
          "uniqueItems": true
        },
        "supported_contact_motion_modes": {
          "type": "array",
          "items": { "$ref": "#/$defs/ContactMotionMode" },
          "uniqueItems": true
        },
        "independent_contact_group_control": { "type": "boolean" },
        "supported_mobility_types": {
          "type": "array",
          "items": { "$ref": "#/$defs/MobilityType" },
          "uniqueItems": true
        },
        "supported_skills": {
          "type": "array",
          "items": { "type": "string" },
          "uniqueItems": true
        },
        "supported_modes": {
          "type": "array",
          "items": { "type": "string" },
          "uniqueItems": true
        },
        "local_recovery": {
          "type": "array",
          "items": { "type": "string" },
          "description": "例如 increase_grip_within_limit / reduce_speed / retreat_small_distance。"
        },
        "control_rate_hz": { "type": "number", "minimum": 1 }
      },
      "required": [
        "hand_id",
        "backend",
        "dof",
        "n_fingers",
        "opposition_types",
        "aperture_range_m",
        "sensing",
        "control_interfaces",
        "supported_skills",
        "supported_modes"
      ],
      "additionalProperties": false
    }
  }
}
```

---

# 4. L2 Interaction Skill 接口

命名空间：`robot.skill.*`。除 persistent mode 外，所有 L2 Skill 返回 `SkillOutcome`。

## 4.1 `robot.skill.shape_hand`

### 物理定义

在**没有任务相关接触**的条件下改变手部构形。`posture` 与 `preshape` 共享底层 hand-shape control，但 goal generator 与 success predicate 不同。

### 四轴 descriptor

```text
C: no-task-contact → no-task-contact, topology=preserve
S: mobility=free_6d, hand=[actuate], environment=[]
Y: hand_configuration, position/policy
T: goal
```

### Input Schema

```json
{
  "name": "robot.skill.shape_hand",
  "inputSchema": {
    "type": "object",
    "properties": {
      "goal": {
        "oneOf": [
          {
            "type": "object",
            "properties": {
              "type": { "const": "posture" },
              "semantic": {
                "type": "string",
                "description": "必须出现在 HandCapabilityModel.semantic_postures 中。"
              },
              "adapter_posture_id": {
                "type": "string",
                "description": "非可移植逃生口；使用后 Agent 必须标记 portability=false。"
              }
            },
            "required": ["type"],
            "oneOf": [
              { "required": ["semantic"] },
              { "required": ["adapter_posture_id"] }
            ],
            "additionalProperties": false
          },
          {
            "type": "object",
            "properties": {
              "type": { "const": "preshape" },
              "object_id": { "type": "string" },
              "opposition_type": { "$ref": "#/$defs/OppositionType" },
              "grasp_class": { "$ref": "#/$defs/GraspClass" },
              "contact_groups": {
                "type": "array",
                "items": { "$ref": "#/$defs/VirtualContactGroup" },
                "minItems": 2
              },
              "aperture_m": { "type": "number", "minimum": 0 },
              "clearance_m": { "type": "number", "minimum": 0, "default": 0.01 }
            },
            "required": ["type", "object_id", "opposition_type", "contact_groups"],
            "additionalProperties": false
          }
        ]
      },
      "speed_scale": { "type": "number", "minimum": 0.01, "maximum": 1.0, "default": 0.5 },
      "abort_on_contact": { "type": "boolean", "default": true },
      "timeout_s": { "type": "number", "default": 8.0 }
    },
    "required": ["goal"],
    "additionalProperties": false
  }
}
```

### 前置条件

- 当前不存在该动作未授权的 task contact；
- 目标构形可达、无自碰撞；
- `preshape` 时 object pose 与目标 region belief 可用；
- `aperture_m` 若给出，必须处于 capability range。

### 成功判据

- `posture`：手部构形达到 semantic posture 的 Adapter 映射容差；
- `preshape`：各 required contact group 的预测接触几何满足 clearance / alignment 约束；
- 全程未发生未授权接触。

### 典型失败

`UNREACHABLE`、`APERTURE_EXCEEDED`、`COLLISION`、`PREMATURE_CONTACT`、`NOT_SUPPORTED`、`TIMEOUT`。

### 跨手共享

`SHARED_GATED`：contract 完全共享；精确 hand configuration、IK 与 posture library 由 Adapter 实现。

---

## 4.2 `robot.skill.make_contact`

### 物理定义

执行 guarded motion，使指定 `VirtualContactGroup` 从无接触进入接触。它只负责 **建立接触**，不负责达到稳定抓取，也不负责后续施加任务 wrench。

### 四轴 descriptor

```text
C: required contacts absent → required contacts present, topology=add
S: task-defined
Y: hand_configuration + contact_force, position/impedance/hybrid
T: event_guarded
```

### Input Schema

```json
{
  "name": "robot.skill.make_contact",
  "inputSchema": {
    "type": "object",
    "properties": {
      "object_id": { "type": "string" },
      "contact_groups": {
        "type": "array",
        "items": { "$ref": "#/$defs/VirtualContactGroup" },
        "minItems": 1
      },
      "approach": {
        "type": "object",
        "properties": {
          "frame": { "$ref": "#/$defs/Frame" },
          "direction": { "$ref": "#/$defs/Vec3" },
          "max_displacement_m": { "type": "number", "minimum": 0, "default": 0.05 },
          "speed_m_s": { "type": "number", "minimum": 0, "default": 0.02 }
        },
        "additionalProperties": false
      },
      "contact_force_limit_n": { "type": "number", "minimum": 0, "default": 1.0 },
      "require_all_required_groups": { "type": "boolean", "default": true },
      "stop_on_first_contact": { "type": "boolean", "default": false },
      "timeout_s": { "type": "number", "default": 10.0 }
    },
    "required": ["object_id", "contact_groups"],
    "additionalProperties": false
  }
}
```

### 前置条件

- required contact groups 当前未全部建立；
- Adapter 至少有一种可用接触估计通道；
- 目标 region 与 approach 信息足够生成 guarded motion；
- 不要求所有手具有触觉，允许由电流、位置误差、力矩、视觉或仿真 contact truth 估计。

### 成功判据

- required groups 满足 contact predicate；
- 接触置信度高于运行时阈值；
- 未超过 contact force limit；
- 无未授权对象位移。

### 典型失败

`NO_CONTACT_FOUND`、`PREMATURE_CONTACT`、`INCOMPLETE_CONTACT_SET`、`OBJECT_DISPLACED`、`SENSOR_UNAVAILABLE`、`WRENCH_LIMIT_EXCEEDED`、`TIMEOUT`。

### 跨手共享

`SHARED`：接触语义共享；contact estimator 与低层 guarded motion 实现可不同。

---

## 4.3 `robot.skill.establish_grasp`

### 物理定义

从已有部分接触进入**满足任务 required wrench set 的稳定抓取区域**。

它不把“force closure”作为唯一成功定义。某些任务可能只需要 task-specific stability；`closure_class` 仅作为描述信息。

### 四轴 descriptor

```text
C: partial contact → stable grasp contact set, topology=preserve/add
S: mobility=free_6d, hand=[support, constrain, actuate]
Y: contact_force + task stability, force/impedance/policy
T: goal
```

### Input Schema

```json
{
  "name": "robot.skill.establish_grasp",
  "inputSchema": {
    "type": "object",
    "properties": {
      "object_id": { "type": "string" },
      "required_wrench_set": { "$ref": "#/$defs/RequiredWrenchSet" },
      "contact_groups": {
        "type": "array",
        "items": { "$ref": "#/$defs/VirtualContactGroup" },
        "minItems": 2
      },
      "opposition_type": { "$ref": "#/$defs/OppositionType" },
      "grasp_class": { "$ref": "#/$defs/GraspClass" },
      "min_task_wrench_margin": {
        "type": "number",
        "minimum": 1.0,
        "default": 1.2
      },
      "force_ramp_s": { "type": "number", "minimum": 0, "default": 1.0 },
      "auto_enter_maintain_grasp": { "type": "boolean", "default": true },
      "timeout_s": { "type": "number", "default": 10.0 }
    },
    "required": ["object_id", "required_wrench_set", "contact_groups"],
    "additionalProperties": false
  }
}
```

### 前置条件

- 至少存在可形成目标 contact plan 的部分接触；
- `robot.grasp.evaluate_feasibility` 结果为 feasible，或 Skill 内部能够完成等价评估；
- 接触对 belief 与 actuator limit 足以形成保守可行性判断；
- 若不确定性过大，允许直接返回 `INFEASIBLE_GRASP` + `probe_contact_property` recovery hint，而不是盲目加力。

### 成功判据

- `task_wrench_margin >= min_task_wrench_margin`；
- 所有 contact force / pressure / actuator 约束满足；
- required contact groups 未丢失；
- 若设置 `auto_enter_maintain_grasp`，成功后已进入 `MAINTAIN_GRASP`。

### 典型失败

`INFEASIBLE_GRASP`、`CONTACT_LOST`、`OBJECT_EJECTED`、`PRESSURE_LIMIT`、`DEFORMATION_LIMIT`、`ACTUATOR_LIMIT`、`INSUFFICIENT_TASK_MARGIN`。

### 跨手共享

`SHARED`：task wrench contract、success/failure 完全共享；grasp matrix、force allocation、contact mapping 由 Adapter / shared solver 实现。

---

## 4.4 `robot.skill.manipulate_in_contact`

### 物理定义

在**不发生未授权 contact topology change**的前提下改变物体相对手、环境或两者的位姿。

它统一覆盖：

- in-hand translation / rotation；
- fingertip rolling；
- controlled sliding；
- pivoting；
- surface-assisted / edge-assisted extrinsic dexterity；
- non-prehensile planar push（当 constraint allocation 为 environment-supported）。

几何目标是参数，`stick/roll/slide` 是允许的 contact kinematics 约束，而不是单独按“旋转/平移”拆 Skill。

### 四轴 descriptor

```text
C: contact set preserved, topology=preserve
S: task-defined ConstraintAllocation
Y: object_pose + contact_force + contact_motion
T: goal
```

### Input Schema

```json
{
  "name": "robot.skill.manipulate_in_contact",
  "inputSchema": {
    "type": "object",
    "properties": {
      "object_id": { "type": "string" },
      "target": {
        "oneOf": [
          {
            "type": "object",
            "properties": {
              "delta_pose": {
                "type": "object",
                "properties": {
                  "translation": { "$ref": "#/$defs/Vec3" },
                  "rotation": { "$ref": "#/$defs/Quat" }
                },
                "additionalProperties": false
              }
            },
            "required": ["delta_pose"],
            "additionalProperties": false
          },
          {
            "type": "object",
            "properties": {
              "target_pose": { "$ref": "#/$defs/Pose" }
            },
            "required": ["target_pose"],
            "additionalProperties": false
          }
        ]
      },
      "constraint_allocation": { "$ref": "#/$defs/ConstraintAllocation" },
      "environment_resource": {
        "type": "object",
        "properties": {
          "resource_id": { "type": "string" },
          "resource_type": {
            "type": "string",
            "enum": ["support_surface", "wall", "edge", "fixture", "gravity"]
          },
          "pose": { "$ref": "#/$defs/Pose" }
        },
        "required": ["resource_type"],
        "additionalProperties": false
      },
      "contact_motion_policy": {
        "type": "object",
        "properties": {
          "allowed": {
            "type": "array",
            "items": { "$ref": "#/$defs/ContactMotionMode" },
            "minItems": 1,
            "uniqueItems": true
          },
          "preferred": { "$ref": "#/$defs/ContactMotionMode" },
          "forbidden": {
            "type": "array",
            "items": { "$ref": "#/$defs/ContactMotionMode" },
            "uniqueItems": true
          }
        },
        "required": ["allowed"],
        "additionalProperties": false
      },
      "preserve_group_ids": {
        "type": "array",
        "items": { "type": "string" }
      },
      "min_task_wrench_margin": { "type": "number", "minimum": 0, "default": 0.8 },
      "position_tolerance_m": { "type": "number", "minimum": 0, "default": 0.003 },
      "orientation_tolerance_rad": { "type": "number", "minimum": 0, "default": 0.05 },
      "restore_task_margin_after": { "type": "boolean", "default": true },
      "timeout_s": { "type": "number", "default": 15.0 }
    },
    "required": ["object_id", "target", "constraint_allocation", "contact_motion_policy"],
    "additionalProperties": false
  }
}
```

### 前置条件

- 当前至少存在一个任务相关 contact；
- 当前 contact topology 与目标 movement compatible；
- Adapter 支持 `contact_motion_policy.allowed` 中至少一种模式；
- 若要求环境资源，资源 pose/confidence 可用。

### 成功判据

- 目标 object pose 达到容差；
- 未发生 forbidden contact motion；
- `preserve_group_ids` 未丢失；
- task stability 不低于允许运行下限；
- 若要求恢复，最终 task margin 回到指定水平。

### 典型失败

`NOT_SUPPORTED`、`UNEXPECTED_CONTACT_MODE`、`OBJECT_DROPPED`、`CONTACT_LOST`、`JAMMED`、`POSE_ERROR_EXCEEDED`、`SLIP_UNRECOVERABLE`、`TIMEOUT`。

### 跨手共享

`SHARED_GATED`：语义、约束与判据共享；可达 contact-motion policy 的集合由 capability 决定。

---

## 4.5 `robot.skill.change_contacts`

### 物理定义

主动改变 contact graph，同时保持物体在允许的 stability envelope 内。包括 finger gaiting、换接触区域、增加/移除 stabilizing contact。

释放后完全脱手再重新抓属于 `robot.macro.regrasp`，不属于本 Skill。

### 四轴 descriptor

```text
C: contact graph A → contact graph B, topology=replace/add/remove
S: task-defined
Y: hand_configuration + contact_force
T: goal
```

### Input Schema

```json
{
  "name": "robot.skill.change_contacts",
  "inputSchema": {
    "type": "object",
    "properties": {
      "object_id": { "type": "string" },
      "transitions": {
        "type": "array",
        "minItems": 1,
        "items": {
          "type": "object",
          "properties": {
            "group_id": { "type": "string" },
            "action": {
              "type": "string",
              "enum": ["release_and_replace", "slide_to", "add", "remove"]
            },
            "new_target_region": { "$ref": "#/$defs/TargetRegion" },
            "allowed_contact_motion": {
              "type": "array",
              "items": { "$ref": "#/$defs/ContactMotionMode" }
            }
          },
          "required": ["group_id", "action"],
          "additionalProperties": false
        }
      },
      "min_remaining_task_margin": { "type": "number", "minimum": 0, "default": 0.8 },
      "max_object_drift_m": { "type": "number", "minimum": 0, "default": 0.005 },
      "allow_environment_support": { "type": "boolean", "default": false },
      "timeout_s": { "type": "number", "default": 20.0 }
    },
    "required": ["object_id", "transitions"],
    "additionalProperties": false
  }
}
```

### 前置条件

- 当前 object 已被稳定持有或有环境支撑；
- 执行前必须预测过渡期间的最小 task margin；
- capability 支持独立 contact group control；
- 若预测 `task_wrench_margin` 会低于下限，应在执行前拒绝。

### 成功判据

- 目标 contact graph 达成；
- 物体 drift 在容差内；
- 最终 task margin 恢复到目标水平；
- 无未授权 topology change。

### 典型失败

`INSUFFICIENT_REMAINING_STABILITY`、`CONTACT_LOST`、`OBJECT_DROPPED`、`UNEXPECTED_CONTACT_MODE`、`NOT_SUPPORTED`、`TIMEOUT`。

### 跨手共享

`SHARED_GATED`。

---

## 4.6 `robot.skill.apply_wrench`

### 物理定义

在**已有接触**的前提下，对目标建立规定 interaction wrench。它不负责建立接触，因此 `PRESS_BUTTON` 必须先调用 `MAKE_CONTACT`。

可由：

- 手指/掌直接对环境施力；
- 已握持物体作为工具对环境施力。

### 四轴 descriptor

```text
C: contact set preserved, topology=preserve
S: task-defined
Y: interaction_wrench (+ optional motion)
T: goal | event_guarded | duration
```

### Input Schema

```json
{
  "name": "robot.skill.apply_wrench",
  "inputSchema": {
    "type": "object",
    "properties": {
      "actor": {
        "type": "object",
        "properties": {
          "type": { "type": "string", "enum": ["hand_contact_group", "held_object"] },
          "group_id": { "type": "string" },
          "object_id": { "type": "string" },
          "tool_point_offset": { "$ref": "#/$defs/Vec3" }
        },
        "required": ["type"],
        "additionalProperties": false
      },
      "target_wrench": { "$ref": "#/$defs/Wrench" },
      "motion": {
        "type": "object",
        "properties": {
          "path_type": { "type": "string", "enum": ["none", "linear", "circular", "raster"] },
          "extent_m": { "type": "number", "minimum": 0 },
          "speed_m_s": { "type": "number", "minimum": 0 }
        },
        "additionalProperties": false
      },
      "termination": {
        "oneOf": [
          {
            "type": "object",
            "properties": { "target_reached": { "const": true } },
            "required": ["target_reached"],
            "additionalProperties": false
          },
          {
            "type": "object",
            "properties": { "duration_s": { "type": "number", "minimum": 0 } },
            "required": ["duration_s"],
            "additionalProperties": false
          },
          {
            "type": "object",
            "properties": {
              "until_force_drop": {
                "type": "object",
                "properties": { "drop_ratio": { "type": "number", "minimum": 0, "maximum": 1 } },
                "required": ["drop_ratio"],
                "additionalProperties": false
              }
            },
            "required": ["until_force_drop"],
            "additionalProperties": false
          },
          {
            "type": "object",
            "properties": {
              "until_force_rise": {
                "type": "object",
                "properties": { "rise_n": { "type": "number", "minimum": 0 } },
                "required": ["rise_n"],
                "additionalProperties": false
              }
            },
            "required": ["until_force_rise"],
            "additionalProperties": false
          }
        ]
      },
      "max_wrench": { "$ref": "#/$defs/Wrench" },
      "timeout_s": { "type": "number", "default": 20.0 }
    },
    "required": ["actor", "target_wrench", "termination", "max_wrench"],
    "additionalProperties": false
  }
}
```

### 前置条件

- 目标作用接触已建立；
- `actor=held_object` 时 `MAINTAIN_GRASP` 必须活跃；
- 若 external wrench 会降低 grasp margin，运行时必须先更新 grasp load budget；
- 更新后若 task margin 不足，执行前返回 `INFEASIBLE_INTERACTION`。

### 成功判据

- termination 条件达成；
- wrench 未超 `max_wrench`；
- 持物施力时 object-in-hand slip 未超限；
- 直接 hand contact 时 contact 未丢失。

### 典型失败

`WRENCH_LIMIT_EXCEEDED`、`INFEASIBLE_INTERACTION`、`SLIP_UNRECOVERABLE`、`CONTACT_LOST`、`JAMMED`、`ACTUATOR_LIMIT`、`TIMEOUT`。

### 跨手共享

`SHARED_GATED`。

---

## 4.7 `robot.skill.follow_constraint`

### 物理定义

沿环境或机构规定的 mobility manifold 运动，同时在正交约束方向保持柔顺/限制 interaction wrench。

覆盖：

- revolute：旋钮、门把手、门；
- prismatic：抽屉、滑轨；
- axial：插入/拔出；
- custom：在线估计的低维约束流形。

### 四轴 descriptor

```text
C: contact set preserved
S: environment constrains mobility, hand actuates/stabilizes
Y: pose along manifold + off-manifold wrench
T: goal
```

### Input Schema

```json
{
  "name": "robot.skill.follow_constraint",
  "inputSchema": {
    "type": "object",
    "properties": {
      "object_id": { "type": "string" },
      "mobility": { "$ref": "#/$defs/MobilityModel" },
      "target_displacement": {
        "type": "number",
        "description": "revolute 用 rad；prismatic/axial 用 m；custom 由 model 定义。"
      },
      "identify_constraint_online": { "type": "boolean", "default": true },
      "max_off_manifold_wrench": { "$ref": "#/$defs/Wrench" },
      "speed": { "type": "number", "minimum": 0 },
      "timeout_s": { "type": "number", "default": 20.0 }
    },
    "required": ["mobility", "target_displacement", "max_off_manifold_wrench"],
    "additionalProperties": false
  }
}
```

### 前置条件

- 与约束对象已有足以传递动作的接触；
- mobility model 可用，或允许在线辨识；
- 必须配置 off-manifold wrench 限制；
- 若 grasp required，`MAINTAIN_GRASP` 活跃。

### 成功判据

- 沿 mobility manifold 的进度达到目标；
- off-manifold wrench 未超限；
- 接触与 grasp stability 未失效。

### 典型失败

`CONSTRAINT_ESTIMATE_ERROR`、`JAMMED`、`WRENCH_LIMIT_EXCEEDED`、`SLIP_UNRECOVERABLE`、`ACTUATOR_LIMIT`、`TIMEOUT`。

### 跨手共享

`SHARED_GATED`。

---

## 4.8 `robot.skill.break_contact`

### 物理定义

受控解除指定 contact。若解除的是承载物体的 grasp contact，则必须先证明物体已有安全支撑，或显式授权 drop。

### 四轴 descriptor

```text
C: target contacts present → target contacts absent, topology=remove
S: may transition from hand-supported to environment-supported
Y: contact_force + hand_configuration
T: goal
```

### Input Schema

```json
{
  "name": "robot.skill.break_contact",
  "inputSchema": {
    "type": "object",
    "properties": {
      "object_id": { "type": "string" },
      "target_group_ids": {
        "type": "array",
        "items": { "type": "string" },
        "description": "省略表示解除该 object 的全部 hand contacts。"
      },
      "support": {
        "type": "object",
        "properties": {
          "state": {
            "type": "string",
            "enum": ["surface", "other_hand", "fixture", "self_stable", "none"]
          },
          "support_id": { "type": "string" },
          "confidence": { "type": "number", "minimum": 0, "maximum": 1 }
        },
        "required": ["state"],
        "additionalProperties": false
      },
      "allow_drop": { "type": "boolean", "default": false },
      "release_mode": {
        "type": "string",
        "enum": ["simultaneous", "sequential"],
        "default": "sequential"
      },
      "group_order": {
        "type": "array",
        "items": { "type": "string" }
      },
      "force_ramp_down_s": { "type": "number", "minimum": 0, "default": 0.8 },
      "max_object_drift_m": { "type": "number", "minimum": 0, "default": 0.005 },
      "retreat_distance_m": { "type": "number", "minimum": 0, "default": 0.03 },
      "timeout_s": { "type": "number", "default": 8.0 }
    },
    "required": ["object_id", "support"],
    "additionalProperties": false
  }
}
```

### 前置条件

- 目标 contact 当前存在；
- 若解除会使 object 失去主要支撑，则必须 `support.state != none` 或 `allow_drop=true`；
- support confidence 低时不得静默假设环境已接管负载。

### 成功判据

- 目标 contacts 已解除；
- 若不允许 drop，物体保持在允许 drift 内；
- 手完成安全 retreat；
- 相关 persistent mode 已同步退出或更新。

### 典型失败

`PRECONDITION_FAILED`、`OBJECT_DISPLACED`、`OBJECT_EJECTED`、`OBJECT_DROPPED`、`CONTACT_LOST`（粘连/回弹）、`TIMEOUT`。

### 跨手共享

`SHARED`。

---

## 4.9 `robot.skill.probe_interaction`

### 物理定义

通过受限的小幅激励主动降低物性或约束模型不确定性。其成功判据不是完成一个 manipulation goal，而是获得足以改善后续决策的 belief update。

### 四轴 descriptor

```text
C: task-defined, may temporarily establish/preserve contact
S: task-defined
Y: excitation + observation
T: goal
```

### Input Schema

```json
{
  "name": "robot.skill.probe_interaction",
  "inputSchema": {
    "type": "object",
    "properties": {
      "target": {
        "type": "string",
        "enum": [
          "contact_normal",
          "friction_lower_bound",
          "normal_compliance",
          "constraint_axis",
          "contact_location"
        ]
      },
      "object_id": { "type": "string" },
      "pair_id": { "type": "string" },
      "max_probe_force_n": { "type": "number", "minimum": 0, "default": 1.0 },
      "max_probe_displacement_m": { "type": "number", "minimum": 0, "default": 0.005 },
      "min_information_gain": { "type": "number", "minimum": 0, "default": 0.0 },
      "retreat_after": { "type": "boolean", "default": true },
      "timeout_s": { "type": "number", "default": 10.0 }
    },
    "required": ["target"],
    "additionalProperties": false
  }
}
```

### 前置条件

- 激励在安全 bounds 内；
- 至少一种相关 observation modality 可用；
- 对脆弱对象必须有 conservative pressure/force cap。

### 成功判据

- 产生目标 field 的有效 `BeliefUpdate`；
- 新 estimate 比原 belief 更窄、更高 confidence，或满足调用方给定的 uncertainty target；
- 未触发安全约束。

### 典型失败

`SENSOR_UNAVAILABLE`、`INFEASIBLE_INTERACTION`、`WRENCH_LIMIT_EXCEEDED`、`OBJECT_DISPLACED`、`TIMEOUT`。

### 跨手共享

`SHARED_GATED`。

---

# 5. 非 Skill 接口

## 5.1 能力协商

```json
{
  "name": "robot.describe_capabilities",
  "description": "返回当前绑定 Adapter 的 capability model。Agent 在会话开始或 Adapter 切换后调用。",
  "inputSchema": {
    "type": "object",
    "properties": {},
    "additionalProperties": false
  },
  "outputSchema": { "$ref": "#/$defs/HandCapabilityModel" }
}
```

## 5.2 Skill 自省

```json
{
  "name": "robot.describe_skills",
  "description": "返回已注册 Skill descriptor。四轴用于规划过滤，不作为唯一 ID。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "filter_by_current_state": { "type": "boolean", "default": false }
    },
    "additionalProperties": false
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "skills": {
        "type": "array",
        "items": { "$ref": "#/$defs/SkillDescriptor" }
      }
    },
    "required": ["skills"],
    "additionalProperties": false
  }
}
```

## 5.3 状态查询

```json
{
  "name": "robot.get_state",
  "inputSchema": {
    "type": "object",
    "properties": {
      "include_object_beliefs": { "type": "boolean", "default": true },
      "include_contact_pair_beliefs": { "type": "boolean", "default": false }
    },
    "additionalProperties": false
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "contact_state": { "$ref": "#/$defs/ContactState" },
      "active_modes": {
        "type": "array",
        "items": { "type": "string" }
      },
      "hand_pose": { "$ref": "#/$defs/Pose" },
      "object_beliefs": {
        "type": "array",
        "items": { "$ref": "#/$defs/ObjectBelief" }
      },
      "contact_pair_beliefs": {
        "type": "array",
        "items": { "$ref": "#/$defs/ContactPairBelief" }
      },
      "timestamp": { "type": "number" }
    },
    "required": ["contact_state", "active_modes", "timestamp"],
    "additionalProperties": false
  }
}
```

## 5.4 Belief 管理

### Object belief

```json
{
  "name": "robot.object.upsert_belief",
  "inputSchema": { "$ref": "#/$defs/ObjectBelief" }
}
```

### Contact pair belief

```json
{
  "name": "robot.contact_pair.upsert_belief",
  "inputSchema": { "$ref": "#/$defs/ContactPairBelief" }
}
```

### Grasp feasibility

```json
{
  "name": "robot.grasp.evaluate_feasibility",
  "description": "在执行 establish_grasp 前评估 contact plan 对 required wrench set 是否可行。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "object_id": { "type": "string" },
      "contact_groups": {
        "type": "array",
        "items": { "$ref": "#/$defs/VirtualContactGroup" },
        "minItems": 2
      },
      "required_wrench_set": { "$ref": "#/$defs/RequiredWrenchSet" },
      "opposition_type": { "$ref": "#/$defs/OppositionType" },
      "grasp_class": { "$ref": "#/$defs/GraspClass" },
      "safety_factor": { "type": "number", "minimum": 1.0, "default": 1.2 },
      "use_conservative_bounds": { "type": "boolean", "default": true }
    },
    "required": ["object_id", "contact_groups", "required_wrench_set"],
    "additionalProperties": false
  },
  "outputSchema": { "$ref": "#/$defs/GraspFeasibility" }
}
```

---

## 5.5 Persistent Modes

### 核心原则

`MAINTAIN_GRASP` 与 `SUPPORT` 是本地闭环模式。

Agent 只能：

```text
enter
update task-level constraints
query health occasionally
exit
```

Agent **不能**负责：

```text
检测 slip → 决定下一个毫秒的夹持力 → 再 update
```

以下情况必须由 local mode 自主执行 bounded recovery：

- incipient slip；
- contact force drift；
- 小幅 contact loss；
- task load 上升但仍在允许 safety envelope 内。

若 bounded recovery 失败，mode 应进入 safe state 并异步记录 critical event；随后 Agent 再决定重抓/放置/求助。

### `robot.mode.enter`

```json
{
  "name": "robot.mode.enter",
  "inputSchema": {
    "type": "object",
    "properties": {
      "mode": {
        "type": "string",
        "enum": ["MAINTAIN_GRASP", "SUPPORT"]
      },
      "params": {
        "type": "object",
        "properties": {
          "object_id": { "type": "string" },
          "required_wrench_set": { "$ref": "#/$defs/RequiredWrenchSet" },
          "min_task_wrench_margin": { "type": "number", "minimum": 1.0, "default": 1.2 },
          "keep_upright": { "type": "boolean", "default": false },
          "max_tilt_rad": { "type": "number", "minimum": 0 },
          "deformation_limit_m": { "type": "number", "minimum": 0 }
        },
        "required": ["object_id"],
        "additionalProperties": false
      }
    },
    "required": ["mode", "params"],
    "additionalProperties": false
  }
}
```

### `robot.mode.update`

```json
{
  "name": "robot.mode.update",
  "description": "仅更新 task-level load/constraint，不用于实时 servo。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "mode": { "type": "string", "enum": ["MAINTAIN_GRASP", "SUPPORT"] },
      "params": {
        "type": "object",
        "properties": {
          "required_wrench_set": { "$ref": "#/$defs/RequiredWrenchSet" },
          "min_task_wrench_margin": { "type": "number", "minimum": 1.0 },
          "keep_upright": { "type": "boolean" },
          "max_tilt_rad": { "type": "number", "minimum": 0 }
        },
        "additionalProperties": false
      }
    },
    "required": ["mode", "params"],
    "additionalProperties": false
  }
}
```

### `robot.mode.query_health`

```json
{
  "name": "robot.mode.query_health",
  "inputSchema": {
    "type": "object",
    "properties": {
      "mode": { "type": "string", "enum": ["MAINTAIN_GRASP", "SUPPORT"] }
    },
    "required": ["mode"],
    "additionalProperties": false
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "active": { "type": "boolean" },
      "task_stability": { "$ref": "#/$defs/TaskStability" },
      "accumulated_slip_m": { "type": "number", "minimum": 0 },
      "contact_loss_count": { "type": "integer", "minimum": 0 },
      "health": {
        "type": "string",
        "enum": ["NOMINAL", "DEGRADED", "CRITICAL"]
      },
      "local_recovery_applied": {
        "type": "array",
        "items": { "type": "string" }
      },
      "recommended_action": { "$ref": "#/$defs/RecoveryHint" }
    },
    "required": ["active", "health"],
    "additionalProperties": false
  }
}
```

### `robot.mode.exit`

```json
{
  "name": "robot.mode.exit",
  "inputSchema": {
    "type": "object",
    "properties": {
      "mode": { "type": "string", "enum": ["MAINTAIN_GRASP", "SUPPORT"] }
    },
    "required": ["mode"],
    "additionalProperties": false
  }
}
```

---

## 5.6 L3 任务宏

宏是 Agent 的推荐入口；失败时通过 `failed_at_skill` 与 `sub_outcomes` 暴露细粒度恢复信息。

### `robot.macro.pick_and_hold`

```text
SHAPE_HAND(goal=preshape)
→ MAKE_CONTACT
→ ESTABLISH_GRASP(auto_enter_maintain_grasp=true)
→ [optional VERIFY_GRASP]
```

### `robot.macro.press_button`

```text
SHAPE_HAND(goal=posture/POINT)
→ MAKE_CONTACT
→ APPLY_WRENCH(actor=hand_contact_group, termination=click/force/displacement)
→ BREAK_CONTACT
```

> 注意：`APPLY_WRENCH` 的前置状态已经是 contact present，因此不存在 v0.1 中 `SEEK_CONTACT` 后 `PRESS` 仍要求 `free` 的状态冲突。

### `robot.macro.push_object`

```text
SHAPE_HAND(optional)
→ MAKE_CONTACT
→ MANIPULATE_IN_CONTACT(
      constraint_allocation.mobility=planar,
      environment_roles=[support, constrain],
      hand_roles=[actuate]
  )
→ BREAK_CONTACT
```

### `robot.macro.turn_constrained`

```text
MAKE_CONTACT or PICK/GRASP HANDLE
→ FOLLOW_CONSTRAINT(mobility=revolute/prismatic/axial)
→ optional BREAK_CONTACT
```

### `robot.macro.regrasp`

```text
establish safe environment support
→ BREAK_CONTACT
→ SHAPE_HAND(goal=preshape)
→ MAKE_CONTACT
→ ESTABLISH_GRASP
```

### `robot.macro.verify_grasp`

验证抓取通常需要 arm / wrist 扰动，因此默认放在 L3，而不是假装它只是 hand-only Skill。

```text
MAINTAIN_GRASP active
+ small robot perturbation (lift / tilt / shake)
+ observe object pose/contact response
→ update ObjectBelief / ContactPairBelief
→ return verified task_wrench_margin
```

若 MCP 当前只管理手、不管理机械臂，则该宏应 capability-gated；手侧仅提供 `MAINTAIN_GRASP` 与 stability monitor。

### `robot.macro.probe_object`

```text
SHAPE_HAND
→ MAKE_CONTACT (if needed)
→ PROBE_INTERACTION
→ optional BREAK_CONTACT
```

---

# 6. Adapter 实现契约

## 6.1 分层归属

| 层 | 归属 | 说明 |
|---|---|---|
| Skill 语义、schema、前置条件、success/failure、outcome | **共享** | Adapter 不得重定义语义 |
| VirtualContactGroup / target region → embodiment contact assignment | **共享 contract + Adapter mapping** | 允许不同手使用不同具体 fingers/links |
| contact plan → grasp matrix / force allocation | **共享算法优先，手特定模型参数** | 可由共享 QP/优化器调用 Adapter kinematics |
| 目标 contact/pose → joint target | **Adapter** | IK / learned inverse model / hand-specific planner |
| 低层 servo、gain、current-force calibration | **Adapter** | 不暴露给 Agent |
| contact estimator | **Adapter** | tactile / current / torque / visual / sim truth 可不同，但输出语义统一 |
| bounded local recovery | **Adapter / local controller** | 必须在 safety envelope 内自主执行 |

## 6.2 强制规则

1. **Skill 参数不得依赖具体 joint index / link name。** `adapter_diagnostics` 可出现，但 Agent 不得据此形成跨手逻辑。
2. **禁止静默降级。** 不满足 capability 必须 `NOT_SUPPORTED`。
3. **禁止返回泛化 failed。** `FAILED` 必须带 `failure_class`。
4. **执行中获得的新物理信息必须回传 belief update。**
5. **所有 pose / direction / wrench 必须显式 frame。**
6. **friction/compliance 按 contact pair 管理。** 不得把同一个 object 的 μ 无条件跨 Wuji / Sharpa 复用。
7. **task_wrench_margin 必须采用统一 metric 版本。** 不得由两个 Adapter 各自定义一个“0~1 stability score”后假装可比较。
8. **持续 mode 的安全闭环必须本地化。** MCP/LLM latency 不得进入安全关键 servo loop。
9. **同一 Agent-visible Skill 可以有不同内部 phase decomposition。** 只要 contract、pre/post semantics、success/failure 一致，就不构成抽象泄漏。
10. **Adapter 不得用隐藏脚本伪造未支持能力。** 若 `MANIPULATE_IN_CONTACT` 的某 contact motion policy 真实不可达，应 `NOT_SUPPORTED`。

## 6.3 跨 embodiment 合规标准

v0.2 不再要求：

```text
Wuji internal skill trace == Sharpa internal skill trace
```

要求的是：

```text
同一 Agent-visible goal
+ 同一 object-centric / interaction-centric constraints
+ capability 均声明支持
=> 不需要修改 Agent 侧任务逻辑即可执行
```

允许：

- Wuji 内部先闭合 thumb 再 index；
- Sharpa 内部并行接近；
- 一个 Adapter 用 current-based contact estimator；
- 另一个用 tactile/sim contact；
- 两者使用不同 IK、增益、学习策略、phase 数量。

不允许：

- Agent 必须因为 hand_id 是 Wuji 而调用一套 Skill sequence；Sharpa 再调用另一套；
- Agent 读取 `adapter_link` 后硬编码 fingers；
- 一个 Adapter 将“不支持 roll”静默改成大幅 slide；
- 同一 `task_wrench_margin` 在两只手上采用不同未声明 metric。

## 6.4 合规检查清单

- [ ] `describe_capabilities.supported_skills` 与实际注册一致。
- [ ] `NOT_SUPPORTED` 对真实能力差异显式返回。
- [ ] `SHAPE_HAND(preshape)` 不接收 joint angle。
- [ ] `MAKE_CONTACT` 在不同 sensing modality 下输出统一 ContactObservation 语义。
- [ ] `ESTABLISH_GRASP` 以 task wrench feasibility 为成功核心，不仅检查 joint/closure angle。
- [ ] `ContactPairBelief` 在 Wuji / Sharpa 使用各自 counterpart surface class。
- [ ] `MANIPULATE_IN_CONTACT` 对 forbidden slide/roll 等约束严格执行。
- [ ] `CHANGE_CONTACTS` 在预计 remaining task margin 不足时执行前拒绝。
- [ ] `APPLY_WRENCH(actor=held_object)` 自动影响 `MAINTAIN_GRASP` load budget。
- [ ] `BREAK_CONTACT(support=none, allow_drop=false)` 必须拒绝。
- [ ] local mode 在 slip/force drift 时能在不询问 Agent 的情况下完成 bounded recovery 或进入 safe state。
- [ ] 两个 Adapter 在相同 L3 macro / L2 contract 下可运行，无需 `if hand_id == ...` 的 Agent 分支。
- [ ] 全部 `SkillOutcome` 通过 schema 校验。

## 6.5 抽象泄漏定位

若跨手迁移失败，按以下顺序定位：

1. **真实 capability gap？**
   - 是：正确返回 `NOT_SUPPORTED`。
2. **object/contact belief 是否错误地跨 embodiment 共享？**
   - 特别检查 friction/compliance pair。
3. **Agent 参数是否泄漏 hand-specific 概念？**
   - joint id、link name、固定 finger 名等。
4. **Skill contract 是否过度承诺？**
   - 例如要求所有手都能纯 roll。
5. **Skill 划分是否把不同 estimator/control/recovery skeleton 错合并？**
6. **是否只是 Adapter 内部 phase 不同？**
   - 若只是内部 phase 不同，不应判定为抽象泄漏。

---

# 7. 第一阶段实现范围

## 7.1 P0：最小可运行集合

建议第一阶段实现：

```text
robot.skill.shape_hand
robot.skill.make_contact
robot.skill.establish_grasp
robot.skill.apply_wrench
robot.skill.break_contact

robot.mode.*   # MAINTAIN_GRASP only

robot.macro.pick_and_hold
robot.macro.press_button

robot.describe_capabilities
robot.describe_skills
robot.get_state
robot.object.upsert_belief
robot.contact_pair.upsert_belief
robot.grasp.evaluate_feasibility
```

### 为什么 P0 就加入 APPLY_WRENCH / PRESS_BUTTON？

如果第一阶段只实现：

```text
preshape → contact → grasp → hold → release
```

只能证明接口适用于 prehensile grasp pipeline，不能证明 `ConstraintAllocation` 对 non-prehensile interaction 有效。

`PRESS_BUTTON` 实现成本较低，却可以立即验证：

- environment-constrained interaction；
- contact → wrench → release 的组合；
- `MAKE_CONTACT` 与 `APPLY_WRENCH` 边界；
- Wuji real / Sharpa sim 的 sensing 与 force proxy 是否能在同一 contract 下工作。

## 7.2 P1：验证“dexterous”能力

第二阶段优先：

```text
robot.skill.probe_interaction
robot.macro.verify_grasp
robot.skill.manipulate_in_contact
robot.skill.change_contacts
```

顺序建议：

1. `PROBE_INTERACTION`：先把未知 friction/compliance 的闭环打通；
2. `VERIFY_GRASP`：验证 belief + perturbation + maintain mode；
3. `MANIPULATE_IN_CONTACT`：先做 fixed-topology rotation / sliding；
4. `CHANGE_CONTACTS`：先做 release-one-group → recontact。

## 7.3 P2：环境约束与工具交互

```text
robot.skill.follow_constraint
MANIPULATE_IN_CONTACT + environment_resource
APPLY_WRENCH(actor=held_object)
SUPPORT mode
```

覆盖：

- drawer；
- knob / valve；
- insertion；
- surface-assisted pivot；
- writing / wiping / pressing with held object。

---

# 8. 最小跨手验证实验

目标不是证明两个手轨迹相同，而是证明：

```text
Agent-visible contract 相同
Adapter implementation 可不同
任务仍可成功
```

## 8.1 实验对象

优先选择形状简单、可控参数明确的对象：

```text
small cylinder
medium cylinder
large cylinder
```

接触条件至少覆盖：

```text
high-friction rigid
low-friction rigid
compliant / pressure-limited
```

平台：

```text
Wuji sim
Wuji real
Sharpa sim
```

## 8.2 Task A：Pick + Hold + Release

```text
SHAPE_HAND(preshape)
→ MAKE_CONTACT
→ ESTABLISH_GRASP
→ MAINTAIN_GRASP
→ BREAK_CONTACT
```

验证：

- aperture / geometry parameterization；
- contact detection fallback；
- task_wrench_margin；
- contact-pair friction difference；
- mode autonomy。

## 8.3 Task B：Press Button

```text
SHAPE_HAND(POINT)
→ MAKE_CONTACT
→ APPLY_WRENCH
→ BREAK_CONTACT
```

验证：

- non-prehensile interaction；
- environment constraint；
- event-guarded termination；
- Wuji 与 Sharpa 不同 sensing 的统一 contact/wrench semantics。

## 8.4 Task C：In-contact Reorientation

```text
ESTABLISH_GRASP / existing contact
→ MANIPULATE_IN_CONTACT
```

至少测：

```text
allowed=[stick, roll]
allowed=[stick, slide]
forbidden=[slide]
```

验证 Adapter 是否会诚实返回 `NOT_SUPPORTED`，而不是静默违反 contact-motion contract。

## 8.5 Task D：Change Contacts

```text
stable grasp
→ release one contact group
→ recontact new region
→ restore task margin
```

验证：

- contact topology transition；
- remaining task stability prediction；
- Wuji / Sharpa embodiment mapping 差异。

## 8.6 记录指标

```text
task_success
skill_success
failure_class_distribution
number_of_retries
local_recovery_count
belief_update_count
contact_transition_log
task_wrench_margin_min
object_pose_error
peak_force_or_effort
execution_time
NOT_SUPPORTED_rate
agent_side_hand_specific_branch_count
shared_contract_coverage
```

最重要的跨手指标之一：

```text
agent_side_hand_specific_branch_count == 0
```

对所有 capability 均声明支持的任务，应尽量成立。

---

# 9. “端不同大小和材质杯子”的完整分解

假设 Agent 目标：

> 把杯子拿起并运输到目标位置。杯子尺寸、材料、质量、摩擦与是否装液体可能不完全已知。

## 9.1 建立 belief

```text
ObjectBelief:
    geometry / pose
    mass estimate
    COM estimate
    liquid / tilt constraints

ContactPairBelief:
    cup region × current hand surface class
    mu_static / mu_dynamic
    compliance
    max_pressure
```

注意：同一杯子在 Wuji 与 Sharpa 上可以共享 geometry / mass / COM，但**不能默认共享 friction pair**。

## 9.2 SHAPE_HAND(preshape)

尺寸变化只改变：

```text
aperture
contact region
contact-group layout
```

不生成新的“large-cup skill / small-cup skill”。

## 9.3 MAKE_CONTACT

低速建立 required contact groups。

若 contact pair 不确定且对象可能脆弱：

```text
低 force limit
+ conservative speed
```

## 9.4 可选 PROBE_INTERACTION

当 friction/compliance uncertainty 过大，以安全小激励估计：

```text
friction lower bound
normal compliance
contact normal
```

更新 `ContactPairBelief`。

## 9.5 Evaluate Grasp Feasibility

由：

```text
mass / COM
required transport wrench
contact geometry
contact-pair friction
pressure limit
actuator limit
```

求 `GraspFeasibility`。

若 `feasible=false`：

```text
change contact plan
switch opposition/grasp class
increase contact area
use environment support
request two-hand strategy
```

而不是无限增大夹持力。

## 9.6 ESTABLISH_GRASP

进入：

```text
task_wrench_margin >= threshold
```

并自动进入 `MAINTAIN_GRASP`。

## 9.7 运输期间 MAINTAIN_GRASP

机械臂运输由上层 robot motion service 负责；手的 mode 在本地持续：

```text
anti-slip
pressure limit
task_wrench_margin
keep-upright / max-tilt constraint
```

机械臂若即将加速，只需高层 update 新的 required wrench set；具体夹持力 adjustment 本地完成。

## 9.8 放置与 BREAK_CONTACT

物体与桌面建立稳定支撑后：

```text
BREAK_CONTACT(support=surface)
```

逐步卸力，确认 environment 已接管负载，再 retreat。

### 不同杯子只改变参数

| 差异 | 修改内容 |
|---|---|
| 直径 | aperture / target regions |
| 质量 | required wrench set |
| COM | wrench / tipping constraint |
| Wuji/Sharpa 指腹材料 | ContactPairBelief.friction |
| 纸杯/软杯 | compliance / max pressure |
| 装液体 | max tilt / transport acceleration |
| 有把手 | contact plan / grasp class |

Skill graph 本身不因为“杯子种类”而重新定义。

---

# 10. 版本演进原则

1. 新增 Skill **不要求占据空四轴 cell**。
2. 新 Skill 必须说明：为什么现有 Skill 的 execution contract 无法覆盖它。
3. 若两个 Skill 四轴 descriptor 完全相同，reviewer 应检查是否存在真实 estimator / invariant / guard / failure / recovery 差异；没有则合并。
4. `FailureClass` 尽量只增不改；重命名需版本迁移。
5. `task_wrench_margin.metric_version` 变化属于协议语义变化，应显式版本化。
6. contact geometry / motion mode enum 可向后扩展，但已有语义不得静默改变。
7. capability model 是 portability 的一等公民；新增能力不得靠 hand_id 分支替代。
8. 所有学习策略都必须置于明确 Skill contract 内，不能以“policy 自己会学”为由绕开 precondition / safety / success / failure 定义。

---

# 11. v0.2 的核心原则摘要

```text
1. Agent 说“想完成什么物理交互”，不说“第几个关节转多少度”。
2. Skill 由闭环交互 contract 定义，而不是由物体类别或动作名字定义。
3. (C,S,Y,T) 是 type descriptor，不是 Skill 唯一主键。
4. Contact 是一个 set/graph；stick/slide/roll 是 per-contact kinematics。
5. Constraint 是方向性的 allocation / mobility，而不是单一 source 标签。
6. 物体属性与 contact-pair 属性必须分离。
7. 抓取成功以 task wrench feasibility 为核心，不以固定关节角或模糊 closure score 为核心。
8. Agent 定约束，Adapter 定 realization；Adapter 不得静默违反约束。
9. 持续安全闭环必须本地化，LLM 不进 servo loop。
10. 跨 embodiment 复用要求 Agent-visible contract 相同，不要求内部 phase/trajectory 相同。
```
