# Robot Skill Instruction Set Architecture

机器人 Skill 接口规范、MuJoCo 参考实现，以及两次 **NON_FORMAL** Wuji CONTACT 实验的测量证据。

## 最新实验（2026-09-20）

| Metric | Skill sanity baseline | Direct single episode |
| --- | ---: | ---: |
| Outcome | SUCCESS | SUCCESS |
| Native input tokens | 7,216 | 49,173 |
| Native output tokens | 65 | 871 |
| Total tokens | 7,281 | 50,044 |
| Decision cycles | 2 | 7 |
| Control interventions | 1 | 5 |
| Robot tool calls | 1 | 6 |
| T_active (s) | 4.5775069 | 40.8632101 |
| T_physical (s) | 0.676 | 2.100 |

两者使用原生 `gpt-5.6-luna / low`、同一个 Wuji nominal CONTACT 场景和等价初始状态。Skill baseline 未重跑；只补跑一次 Direct。全部 token 来自 native runtime telemetry，不是估算。这里只构成 **preliminary single-pair evidence**，不属于正式 benchmark，不支持统计显著性或总体性能结论。

- [Skill instrumentation sanity 报告](results_instrumentation_sanity/INSTRUMENTATION_SANITY_REPORT.md) · [结果 JSON](results_instrumentation_sanity/instrumentation_sanity_result.json)
- [Direct 与配对比较报告](results_wuji_contact_direct_single/WUJI_CONTACT_DIRECT_SINGLE.md) · [结果 JSON](results_wuji_contact_direct_single/wuji_contact_direct_single.json)
- [配对比较 JSON](results_wuji_contact_direct_single/pair_comparison.json) · [可见动作 trace](results_wuji_contact_direct_single/visible_action_trace.json)
- 两个结果目录各包含 `token_usage_per_turn.json`、`decision_trace.jsonl`、`tool_trace.jsonl` 和 `physical/episode_simulation.jsonl`。

Direct 在最后一条有限时长命令结束后终止，没有单独调用 `stop`。首次接触至该命令结束相隔 0.300 仿真秒；最终 contact/load/drift/collision 满足公共 evaluator。不能把这写成首次接触时即时停止。

## 关键规范与实现

- [Skill / MCP spec v0.2](dexterous-hand-skill-mcp-spec-v0.2.md)：保留仓库已有版本；与实验工作区版本文本一致，仅换行字节不同。
- [Agent interface benchmark spec v0.2](agent-interface-benchmark-spec-v0.2.md)
- [共享 Skill、Adapter 与 MuJoCo world](dex_hand/)
- [公共 evaluator、shield 和 low-level API](pilot/interfaces.py)
- [原生 instrumentation runner](scripts/instrumentation_sanity.py) · [离线 sanity auditor](scripts/summarize_instrumentation_sanity.py)
- [Direct single runner](scripts/run_wuji_contact_direct_single.py) · [离线配对报告脚本](scripts/summarize_wuji_contact_direct_single.py)
- [原生计量单元测试](tests/test_instrumentation_sanity.py)

`scripts/contact_native_bridge.py` 是历史 runner，保留以对应报告中的诊断；其 UNAVAILABLE token、残差 T_agent 与旧 intervention 定义不可用于正式测量。

## 安全与有效性边界

1. **Common safety shield**：复用既有 joint range、effort cap、饱和、载荷、漂移和碰撞检查。公共 shield 当前没有独立 joint velocity threshold。
2. **Skill-internal guards / timeout**：MAKE_CONTACT 的接触终止和 8 秒 physical timeout 属于 Skill 实现，没有复制给 Direct。
3. **Benchmark-level episode timeout**：180 秒 wall-clock watchdog，不根据 contact 停止动作。两次均未触发。
4. Native runtime 的通用 skill catalog/permissions 仍存在；两种 prompt/schema 及反馈显示方式有差异。token 比较包含这些差异，不能直接当作纯接口 schema 节省。
5. 未增加停止后的 physical dwell 验证；终态证据限于已记录状态和现有 hold cleanup。

## 发布证据与隐私处理

这是原始工作区的**发布副本**。原始实验文件未改动，测量数值、时间戳和动作参数保持不变。

- 原生事件仅保留 usage、tool/action 和 turn 证据；删除账号/配额事件、系统上下文正文和加密 reasoning payload。
- OTel 仅保留 inference 与 tool-registry 相关原生 spans；去除无关日志及账号/环境属性。
- 本机路径替换为 `$WORKSPACE`、`$CODEX_HOME`、`$USERPROFILE`、`$WUJI_ASSET_PROJECT`；这些是公开占位符，不是可直接运行的路径。
- [PUBLICATION_MANIFEST.json](PUBLICATION_MANIFEST.json) 保存原文件与发布文件的 SHA256 及变换说明。结果 JSON 内历史 SHA256 仍指向原始工作区文件；验证发布副本请使用此 manifest。
- 不包含依赖缓存、登录凭证、完整本地 session、运行锁或原生模型目录预检。

历史 sanity 报告曾将 `merge_into_namespaces.tool_spec_count=3` 解释为语义工具数量；该字段实际对应 native transport specs。Direct 的离线审计已改用 `append_dynamic_tool_runtimes.dynamic_tool_count` 和 session registry；这里保留原报告内容并明确更正，不改动历史测量。

## 离线检查与复现条件

```sh
python scripts/verify_published_evidence.py
python -m unittest discover -s tests -p test_instrumentation_sanity.py -v
```

这两条命令不运行模型或物理 episode。

仿真依赖见 [pyproject.toml](pyproject.toml)，需要 Python 3.11+、MuJoCo、NumPy 和 jsonschema。Wuji 官方模型及 STL meshes 是外部依赖：设置 `WUJI_MJCF` 为配套 `right.xml` 的绝对路径；本仓库不打包相邻项目资产。归档的 scene.xml 中 meshdir 也是已归一化的来源路径。Sharpa 不是这次配对对象；可选资产获取脚本见 `scripts/fetch_sharpa.py`。

Native runners 还依赖本机已登录、支持所需模型的 Codex App Server（本次 runtime `0.155.0-alpha.9.2`）。原始离线报告脚本引用私有 session 路径和源文件 hashes，不能在此精简发布副本上原样运行；请用上述公开证据校验脚本核验。不要在归档结果目录中直接运行 one-shot runners；新实验必须使用独立输出目录并另行授权。
