# B/C/E/F/G/H — GPT-5.6 Luna 四手实验

更新 Unix time 1790759156；已归档 956 个原生模型 episodes，记录 4800 个 requested outcomes。

与 A POINT 同配置：GPT-5.6 Luna / low；每任务每手 requested seeds 0–99；两个独立 Agent contexts；同 seed 共享完整 checkpoint、scene、观测与公共 evaluator。全过程离线 MuJoCo。

总请求 4800 episodes；动作实现名义资格合格的预算 4200；未合格绑定跳过 600。每个随机初态另行检验，不合格不调用模型、不重采样、不计为 Agent 失败。

| Task | Wuji | Sharpa | Allegro V5 | Robotiq 2F-85 |
| --- | --- | --- | --- | --- |
| B TOUCH | QUALIFIED | QUALIFIED | QUALIFIED | QUALIFIED |
| C PRESS | QUALIFIED | QUALIFIED | QUALIFIED | QUALIFIED |
| E ADD_CONTACT | QUALIFIED | QUALIFIED | SKIP / NOT_QUALIFIED | SKIP / NOT_QUALIFIED |
| F STABILIZE | QUALIFIED | QUALIFIED | QUALIFIED | QUALIFIED |
| G RELEASE | QUALIFIED | SKIP / NOT_QUALIFIED | QUALIFIED | QUALIFIED |
| H GRASP_FORMATION | QUALIFIED | QUALIFIED | QUALIFIED | QUALIFIED |

外部 benchmark 提供有限的任务动作实现：C 的 APPLY_WRENCH 仅调节 world-Y 按钮法向载荷；E 的 CHANGE_CONTACTS 仅支持 add=index/preserve=thumb。原 DexISA 仓库、shared schema、冻结 A 执行器均未改动。

| Task | Hand / interface | 模型样本 | 成功 | 失败 | Infra/计量无效 | 初态跳过 | Native tokens | 墙钟 s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| B | wuji / SKILL_AGENT | 16 | 5 | 11 | 0 | 84 | 993,358 | 320.662 |
| B | wuji / DIRECT_AGENT | 16 | 0 | 16 | 0 | 84 | 408,572 | 394.665 |
| B | sharpa / SKILL_AGENT | 14 | 5 | 9 | 0 | 86 | 1,035,179 | 342.858 |
| B | sharpa / DIRECT_AGENT | 14 | 5 | 9 | 0 | 86 | 305,866 | 262.336 |
| B | allegro_v5 / SKILL_AGENT | 15 | 11 | 4 | 0 | 85 | 1,702,285 | 427.097 |
| B | allegro_v5 / DIRECT_AGENT | 15 | 5 | 10 | 0 | 85 | 1,064,610 | 591.438 |
| B | robotiq_2f85 / SKILL_AGENT | 28 | 17 | 11 | 0 | 72 | 1,194,638 | 624.809 |
| B | robotiq_2f85 / DIRECT_AGENT | 28 | 11 | 17 | 0 | 72 | 466,059 | 471.376 |
| C | wuji / SKILL_AGENT | 73 | 17 | 56 | 0 | 27 | 7,663,814 | 2012.003 |
| C | wuji / DIRECT_AGENT | 73 | 13 | 60 | 0 | 27 | 11,188,707 | 4062.448 |
| C | sharpa / SKILL_AGENT | 73 | 24 | 49 | 0 | 27 | 11,233,161 | 2470.145 |
| C | sharpa / DIRECT_AGENT | 73 | 0 | 73 | 0 | 27 | 1,941,662 | 1578.843 |
| C | allegro_v5 / SKILL_AGENT | 70 | 68 | 2 | 0 | 30 | 7,700,416 | 1887.481 |
| C | allegro_v5 / DIRECT_AGENT | 70 | 0 | 70 | 0 | 30 | 5,814,656 | 3664.692 |
| C | robotiq_2f85 / SKILL_AGENT | 70 | 62 | 8 | 0 | 30 | 4,429,950 | 1901.013 |
| C | robotiq_2f85 / DIRECT_AGENT | 70 | 60 | 10 | 0 | 30 | 3,179,339 | 1774.059 |
| E | wuji / SKILL_AGENT | 0 | 0 | 0 | 0 | 100 | 0 | 0.000 |
| E | wuji / DIRECT_AGENT | 0 | 0 | 0 | 0 | 100 | 0 | 0.000 |
| E | sharpa / SKILL_AGENT | 0 | 0 | 0 | 0 | 100 | 0 | 0.000 |
| E | sharpa / DIRECT_AGENT | 0 | 0 | 0 | 0 | 100 | 0 | 0.000 |
| E | allegro_v5 / SKILL_AGENT | 0 | 0 | 0 | 0 | 0 | 0 | 0.000 |
| E | allegro_v5 / DIRECT_AGENT | 0 | 0 | 0 | 0 | 0 | 0 | 0.000 |
| E | robotiq_2f85 / SKILL_AGENT | 0 | 0 | 0 | 0 | 0 | 0 | 0.000 |
| E | robotiq_2f85 / DIRECT_AGENT | 0 | 0 | 0 | 0 | 0 | 0 | 0.000 |
| F | wuji / SKILL_AGENT | 1 | 1 | 0 | 0 | 99 | 17,289 | 8.355 |
| F | wuji / DIRECT_AGENT | 1 | 1 | 0 | 0 | 99 | 31,847 | 15.781 |
| F | sharpa / SKILL_AGENT | 0 | 0 | 0 | 0 | 100 | 0 | 0.000 |
| F | sharpa / DIRECT_AGENT | 0 | 0 | 0 | 0 | 100 | 0 | 0.000 |
| F | allegro_v5 / SKILL_AGENT | 0 | 0 | 0 | 0 | 100 | 0 | 0.000 |
| F | allegro_v5 / DIRECT_AGENT | 0 | 0 | 0 | 0 | 100 | 0 | 0.000 |
| F | robotiq_2f85 / SKILL_AGENT | 19 | 19 | 0 | 0 | 81 | 249,240 | 137.751 |
| F | robotiq_2f85 / DIRECT_AGENT | 19 | 19 | 0 | 0 | 81 | 248,073 | 155.552 |
| G | wuji / SKILL_AGENT | 1 | 1 | 0 | 0 | 99 | 16,767 | 6.921 |
| G | wuji / DIRECT_AGENT | 1 | 1 | 0 | 0 | 99 | 16,968 | 8.893 |
| G | sharpa / SKILL_AGENT | 0 | 0 | 0 | 0 | 0 | 0 | 0.000 |
| G | sharpa / DIRECT_AGENT | 0 | 0 | 0 | 0 | 0 | 0 | 0.000 |
| G | allegro_v5 / SKILL_AGENT | 0 | 0 | 0 | 0 | 100 | 0 | 0.000 |
| G | allegro_v5 / DIRECT_AGENT | 0 | 0 | 0 | 0 | 100 | 0 | 0.000 |
| G | robotiq_2f85 / SKILL_AGENT | 19 | 18 | 1 | 0 | 81 | 380,636 | 175.001 |
| G | robotiq_2f85 / DIRECT_AGENT | 19 | 17 | 2 | 0 | 81 | 238,509 | 179.972 |
| H | wuji / SKILL_AGENT | 20 | 2 | 18 | 0 | 80 | 918,988 | 273.789 |
| H | wuji / DIRECT_AGENT | 20 | 0 | 20 | 0 | 80 | 468,183 | 459.637 |
| H | sharpa / SKILL_AGENT | 16 | 0 | 16 | 0 | 84 | 761,032 | 245.677 |
| H | sharpa / DIRECT_AGENT | 16 | 3 | 13 | 0 | 84 | 515,042 | 377.271 |
| H | allegro_v5 / SKILL_AGENT | 20 | 1 | 19 | 0 | 80 | 821,174 | 262.248 |
| H | allegro_v5 / DIRECT_AGENT | 20 | 0 | 20 | 0 | 80 | 963,420 | 705.168 |
| H | robotiq_2f85 / SKILL_AGENT | 23 | 19 | 4 | 0 | 77 | 924,048 | 366.507 |
| H | robotiq_2f85 / DIRECT_AGENT | 23 | 14 | 9 | 0 | 77 | 605,319 | 292.563 |

## 所有成功样本的平均成本

每个任务/手/接口分别统计全部成功且原生计量审计通过的样本，无同 seed 筛选、无等数量抽样。失败成本不包含在成功均值中；完整总成本在上表。

| Task | Hand / interface | 成功样本 | 平均 tokens | 平均墙钟 s | 平均 Agent active s | 平均仿真 s |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| B | wuji / SKILL_AGENT | 5 | 126320.600 | 33.373 | 32.724 | 2.708 |
| B | wuji / DIRECT_AGENT | 0 | — | — | — | — |
| B | sharpa / SKILL_AGENT | 5 | 119871.000 | 34.617 | 34.116 | 2.316 |
| B | sharpa / DIRECT_AGENT | 5 | 23226.200 | 18.388 | 18.346 | 0.252 |
| B | allegro_v5 / SKILL_AGENT | 11 | 134464.818 | 33.007 | 32.411 | 2.559 |
| B | allegro_v5 / DIRECT_AGENT | 5 | 61600.800 | 33.850 | 33.679 | 1.156 |
| B | robotiq_2f85 / SKILL_AGENT | 17 | 58367.235 | 28.539 | 28.037 | 1.997 |
| B | robotiq_2f85 / DIRECT_AGENT | 11 | 22445.545 | 20.262 | 20.170 | 0.671 |
| C | wuji / SKILL_AGENT | 17 | 96229.471 | 25.300 | 23.767 | 7.813 |
| C | wuji / DIRECT_AGENT | 13 | 136463.538 | 49.359 | 48.477 | 6.223 |
| C | sharpa / SKILL_AGENT | 24 | 165083.750 | 32.304 | 30.435 | 9.765 |
| C | sharpa / DIRECT_AGENT | 0 | — | — | — | — |
| C | allegro_v5 / SKILL_AGENT | 68 | 110195.794 | 27.080 | 25.122 | 9.351 |
| C | allegro_v5 / DIRECT_AGENT | 0 | — | — | — | — |
| C | robotiq_2f85 / SKILL_AGENT | 62 | 62084.306 | 26.748 | 24.708 | 8.508 |
| C | robotiq_2f85 / DIRECT_AGENT | 60 | 48800.950 | 26.393 | 25.345 | 5.399 |
| E | wuji / SKILL_AGENT | 0 | — | — | — | — |
| E | wuji / DIRECT_AGENT | 0 | — | — | — | — |
| E | sharpa / SKILL_AGENT | 0 | — | — | — | — |
| E | sharpa / DIRECT_AGENT | 0 | — | — | — | — |
| E | allegro_v5 / SKILL_AGENT | 0 | — | — | — | — |
| E | allegro_v5 / DIRECT_AGENT | 0 | — | — | — | — |
| E | robotiq_2f85 / SKILL_AGENT | 0 | — | — | — | — |
| E | robotiq_2f85 / DIRECT_AGENT | 0 | — | — | — | — |
| F | wuji / SKILL_AGENT | 1 | 17289.000 | 8.355 | 8.215 | 0.500 |
| F | wuji / DIRECT_AGENT | 1 | 31847.000 | 15.781 | 15.658 | 0.500 |
| F | sharpa / SKILL_AGENT | 0 | — | — | — | — |
| F | sharpa / DIRECT_AGENT | 0 | — | — | — | — |
| F | allegro_v5 / SKILL_AGENT | 0 | — | — | — | — |
| F | allegro_v5 / DIRECT_AGENT | 0 | — | — | — | — |
| F | robotiq_2f85 / SKILL_AGENT | 19 | 13117.895 | 7.250 | 7.096 | 0.500 |
| F | robotiq_2f85 / DIRECT_AGENT | 19 | 13056.474 | 8.187 | 8.021 | 0.500 |
| G | wuji / SKILL_AGENT | 1 | 16767.000 | 6.921 | 6.883 | 0.190 |
| G | wuji / DIRECT_AGENT | 1 | 16968.000 | 8.893 | 8.871 | 0.140 |
| G | sharpa / SKILL_AGENT | 0 | — | — | — | — |
| G | sharpa / DIRECT_AGENT | 0 | — | — | — | — |
| G | allegro_v5 / SKILL_AGENT | 0 | — | — | — | — |
| G | allegro_v5 / DIRECT_AGENT | 0 | — | — | — | — |
| G | robotiq_2f85 / SKILL_AGENT | 18 | 19966.944 | 9.037 | 8.920 | 0.328 |
| G | robotiq_2f85 / DIRECT_AGENT | 17 | 12511.353 | 9.501 | 9.464 | 0.248 |
| H | wuji / SKILL_AGENT | 2 | 78804.500 | 16.266 | 15.230 | 4.672 |
| H | wuji / DIRECT_AGENT | 0 | — | — | — | — |
| H | sharpa / SKILL_AGENT | 0 | — | — | — | — |
| H | sharpa / DIRECT_AGENT | 3 | 64012.333 | 36.885 | 36.371 | 2.006 |
| H | allegro_v5 / SKILL_AGENT | 1 | 63253.000 | 18.504 | 17.558 | 4.054 |
| H | allegro_v5 / DIRECT_AGENT | 0 | — | — | — | — |
| H | robotiq_2f85 / SKILL_AGENT | 19 | 36477.737 | 15.485 | 14.387 | 3.827 |
| H | robotiq_2f85 / DIRECT_AGENT | 14 | 13211.643 | 10.091 | 9.724 | 0.855 |

## 失败与跳过原因

| Task / Hand / Interface | 原因 | 数量 |
| --- | --- | ---: |
| B / allegro_v5 / DIRECT_AGENT | ACTUATOR_LIMIT | 1 |
| B / allegro_v5 / DIRECT_AGENT | EXCESSIVE_OBJECT_TRANSLATION | 18 |
| B / allegro_v5 / DIRECT_AGENT | EXCESSIVE_PENETRATION | 15 |
| B / allegro_v5 / DIRECT_AGENT | FORBIDDEN_CONTACT | 50 |
| B / allegro_v5 / DIRECT_AGENT | GOAL_NOT_REACHED_WITHIN_BUDGET | 2 |
| B / allegro_v5 / DIRECT_AGENT | WRENCH_LIMIT_EXCEEDED | 9 |
| B / allegro_v5 / SKILL_AGENT | EXCESSIVE_OBJECT_TRANSLATION | 18 |
| B / allegro_v5 / SKILL_AGENT | EXCESSIVE_PENETRATION | 15 |
| B / allegro_v5 / SKILL_AGENT | FORBIDDEN_CONTACT | 48 |
| B / allegro_v5 / SKILL_AGENT | WRENCH_LIMIT_EXCEEDED | 8 |
| B / robotiq_2f85 / DIRECT_AGENT | EXCESSIVE_OBJECT_TRANSLATION | 42 |
| B / robotiq_2f85 / DIRECT_AGENT | EXCESSIVE_PENETRATION | 15 |
| B / robotiq_2f85 / DIRECT_AGENT | FORBIDDEN_CONTACT | 32 |
| B / robotiq_2f85 / SKILL_AGENT | EXCESSIVE_OBJECT_TRANSLATION | 46 |
| B / robotiq_2f85 / SKILL_AGENT | EXCESSIVE_PENETRATION | 14 |
| B / robotiq_2f85 / SKILL_AGENT | FORBIDDEN_CONTACT | 23 |
| B / sharpa / DIRECT_AGENT | EXCESSIVE_OBJECT_TRANSLATION | 14 |
| B / sharpa / DIRECT_AGENT | EXCESSIVE_PENETRATION | 3 |
| B / sharpa / DIRECT_AGENT | FORBIDDEN_CONTACT | 74 |
| B / sharpa / DIRECT_AGENT | PRECONDITION_NOT_MET | 4 |
| B / sharpa / SKILL_AGENT | EXCESSIVE_OBJECT_TRANSLATION | 13 |
| B / sharpa / SKILL_AGENT | EXCESSIVE_PENETRATION | 3 |
| B / sharpa / SKILL_AGENT | FORBIDDEN_CONTACT | 74 |
| B / sharpa / SKILL_AGENT | GOAL_NOT_REACHED_WITHIN_BUDGET | 1 |
| B / sharpa / SKILL_AGENT | PRECONDITION_NOT_MET | 4 |
| B / wuji / DIRECT_AGENT | EXCESSIVE_OBJECT_TRANSLATION | 12 |
| B / wuji / DIRECT_AGENT | EXCESSIVE_PENETRATION | 5 |
| B / wuji / DIRECT_AGENT | FORBIDDEN_CONTACT | 82 |
| B / wuji / DIRECT_AGENT | PRECONDITION_NOT_MET | 1 |
| B / wuji / SKILL_AGENT | EXCESSIVE_OBJECT_TRANSLATION | 12 |
| B / wuji / SKILL_AGENT | EXCESSIVE_PENETRATION | 5 |
| B / wuji / SKILL_AGENT | FORBIDDEN_CONTACT | 77 |
| B / wuji / SKILL_AGENT | PRECONDITION_NOT_MET | 1 |
| C / allegro_v5 / DIRECT_AGENT | ACTUATOR_LIMIT | 7 |
| C / allegro_v5 / DIRECT_AGENT | EXCESSIVE_PENETRATION | 57 |
| C / allegro_v5 / DIRECT_AGENT | FORBIDDEN_CONTACT | 15 |
| C / allegro_v5 / DIRECT_AGENT | GOAL_NOT_REACHED_WITHIN_BUDGET | 1 |
| C / allegro_v5 / DIRECT_AGENT | OBSERVATION_UNAVAILABLE | 9 |
| C / allegro_v5 / DIRECT_AGENT | PRECONDITION_NOT_MET | 1 |
| C / allegro_v5 / DIRECT_AGENT | WRENCH_LIMIT_EXCEEDED | 10 |
| C / allegro_v5 / SKILL_AGENT | EXCESSIVE_PENETRATION | 26 |
| C / allegro_v5 / SKILL_AGENT | FORBIDDEN_CONTACT | 3 |
| C / allegro_v5 / SKILL_AGENT | PRECONDITION_NOT_MET | 1 |
| C / allegro_v5 / SKILL_AGENT | WRENCH_LIMIT_EXCEEDED | 2 |
| C / robotiq_2f85 / DIRECT_AGENT | EXCESSIVE_PENETRATION | 10 |
| C / robotiq_2f85 / DIRECT_AGENT | FORBIDDEN_CONTACT | 28 |
| C / robotiq_2f85 / DIRECT_AGENT | PRECONDITION_NOT_MET | 2 |
| C / robotiq_2f85 / SKILL_AGENT | EXCESSIVE_PENETRATION | 10 |
| C / robotiq_2f85 / SKILL_AGENT | FORBIDDEN_CONTACT | 26 |
| C / robotiq_2f85 / SKILL_AGENT | PRECONDITION_NOT_MET | 2 |
| C / sharpa / DIRECT_AGENT | EXCESSIVE_PENETRATION | 1 |
| C / sharpa / DIRECT_AGENT | FORBIDDEN_CONTACT | 94 |
| C / sharpa / DIRECT_AGENT | PRECONDITION_NOT_MET | 1 |
| C / sharpa / DIRECT_AGENT | WRENCH_LIMIT_EXCEEDED | 4 |
| C / sharpa / SKILL_AGENT | EXCESSIVE_PENETRATION | 1 |
| C / sharpa / SKILL_AGENT | FORBIDDEN_CONTACT | 64 |
| C / sharpa / SKILL_AGENT | GOAL_NOT_REACHED_WITHIN_BUDGET | 2 |
| C / sharpa / SKILL_AGENT | OBSERVATION_UNAVAILABLE | 2 |
| C / sharpa / SKILL_AGENT | PRECONDITION_NOT_MET | 1 |
| C / sharpa / SKILL_AGENT | WRENCH_LIMIT_EXCEEDED | 6 |
| C / wuji / DIRECT_AGENT | EXCESSIVE_PENETRATION | 11 |
| C / wuji / DIRECT_AGENT | FORBIDDEN_CONTACT | 57 |
| C / wuji / DIRECT_AGENT | OBSERVATION_UNAVAILABLE | 12 |
| C / wuji / DIRECT_AGENT | WRENCH_LIMIT_EXCEEDED | 7 |
| C / wuji / SKILL_AGENT | EXCESSIVE_PENETRATION | 11 |
| C / wuji / SKILL_AGENT | FORBIDDEN_CONTACT | 60 |
| C / wuji / SKILL_AGENT | GOAL_NOT_REACHED_WITHIN_BUDGET | 1 |
| C / wuji / SKILL_AGENT | WRENCH_LIMIT_EXCEEDED | 11 |
| E / allegro_v5 / DIRECT_AGENT | NOMINAL_BINDING_NOT_QUALIFIED | 100 |
| E / allegro_v5 / SKILL_AGENT | NOMINAL_BINDING_NOT_QUALIFIED | 100 |
| E / robotiq_2f85 / DIRECT_AGENT | NOMINAL_BINDING_NOT_QUALIFIED | 100 |
| E / robotiq_2f85 / SKILL_AGENT | NOMINAL_BINDING_NOT_QUALIFIED | 100 |
| E / sharpa / DIRECT_AGENT | CONTACT_LOST | 7 |
| E / sharpa / DIRECT_AGENT | EXCESSIVE_PENETRATION | 25 |
| E / sharpa / DIRECT_AGENT | FORBIDDEN_CONTACT | 68 |
| E / sharpa / SKILL_AGENT | CONTACT_LOST | 7 |
| E / sharpa / SKILL_AGENT | EXCESSIVE_PENETRATION | 25 |
| E / sharpa / SKILL_AGENT | FORBIDDEN_CONTACT | 68 |
| E / wuji / DIRECT_AGENT | CONTACT_LOST | 4 |
| E / wuji / DIRECT_AGENT | EXCESSIVE_PENETRATION | 28 |
| E / wuji / DIRECT_AGENT | FORBIDDEN_CONTACT | 68 |
| E / wuji / SKILL_AGENT | CONTACT_LOST | 4 |
| E / wuji / SKILL_AGENT | EXCESSIVE_PENETRATION | 28 |
| E / wuji / SKILL_AGENT | FORBIDDEN_CONTACT | 68 |
| F / allegro_v5 / DIRECT_AGENT | FORBIDDEN_CONTACT | 1 |
| F / allegro_v5 / DIRECT_AGENT | INITIAL_GRASP_WITNESS_FAILED | 99 |
| F / allegro_v5 / SKILL_AGENT | FORBIDDEN_CONTACT | 1 |
| F / allegro_v5 / SKILL_AGENT | INITIAL_GRASP_WITNESS_FAILED | 99 |
| F / robotiq_2f85 / DIRECT_AGENT | INITIAL_GRASP_WITNESS_FAILED | 80 |
| F / robotiq_2f85 / DIRECT_AGENT | PRECONDITION_NOT_MET | 1 |
| F / robotiq_2f85 / SKILL_AGENT | INITIAL_GRASP_WITNESS_FAILED | 80 |
| F / robotiq_2f85 / SKILL_AGENT | PRECONDITION_NOT_MET | 1 |
| F / sharpa / DIRECT_AGENT | INITIAL_GRASP_WITNESS_FAILED | 100 |
| F / sharpa / SKILL_AGENT | INITIAL_GRASP_WITNESS_FAILED | 100 |
| F / wuji / DIRECT_AGENT | INITIAL_GRASP_WITNESS_FAILED | 99 |
| F / wuji / SKILL_AGENT | INITIAL_GRASP_WITNESS_FAILED | 99 |
| G / allegro_v5 / DIRECT_AGENT | FORBIDDEN_CONTACT | 1 |
| G / allegro_v5 / DIRECT_AGENT | INITIAL_GRASP_WITNESS_FAILED | 99 |
| G / allegro_v5 / SKILL_AGENT | FORBIDDEN_CONTACT | 1 |
| G / allegro_v5 / SKILL_AGENT | INITIAL_GRASP_WITNESS_FAILED | 99 |
| G / robotiq_2f85 / DIRECT_AGENT | FORBIDDEN_CONTACT | 1 |
| G / robotiq_2f85 / DIRECT_AGENT | INITIAL_GRASP_WITNESS_FAILED | 80 |
| G / robotiq_2f85 / DIRECT_AGENT | OBJECT_DROP | 1 |
| G / robotiq_2f85 / DIRECT_AGENT | WRENCH_LIMIT_EXCEEDED | 1 |
| G / robotiq_2f85 / SKILL_AGENT | FORBIDDEN_CONTACT | 1 |
| G / robotiq_2f85 / SKILL_AGENT | INITIAL_GRASP_WITNESS_FAILED | 80 |
| G / robotiq_2f85 / SKILL_AGENT | OBJECT_DROP | 1 |
| G / sharpa / DIRECT_AGENT | NOMINAL_BINDING_NOT_QUALIFIED | 100 |
| G / sharpa / SKILL_AGENT | NOMINAL_BINDING_NOT_QUALIFIED | 100 |
| G / wuji / DIRECT_AGENT | INITIAL_GRASP_WITNESS_FAILED | 99 |
| G / wuji / SKILL_AGENT | INITIAL_GRASP_WITNESS_FAILED | 99 |
| H / allegro_v5 / DIRECT_AGENT | EXCESSIVE_PENETRATION | 35 |
| H / allegro_v5 / DIRECT_AGENT | FORBIDDEN_CONTACT | 53 |
| H / allegro_v5 / DIRECT_AGENT | GOAL_NOT_REACHED_WITHIN_BUDGET | 1 |
| H / allegro_v5 / DIRECT_AGENT | OBSERVATION_UNAVAILABLE | 1 |
| H / allegro_v5 / DIRECT_AGENT | WRENCH_LIMIT_EXCEEDED | 10 |
| H / allegro_v5 / SKILL_AGENT | EXCESSIVE_PENETRATION | 35 |
| H / allegro_v5 / SKILL_AGENT | FORBIDDEN_CONTACT | 56 |
| H / allegro_v5 / SKILL_AGENT | WRENCH_LIMIT_EXCEEDED | 8 |
| H / robotiq_2f85 / DIRECT_AGENT | EXCESSIVE_PENETRATION | 19 |
| H / robotiq_2f85 / DIRECT_AGENT | FORBIDDEN_CONTACT | 63 |
| H / robotiq_2f85 / DIRECT_AGENT | GOAL_NOT_REACHED_WITHIN_BUDGET | 1 |
| H / robotiq_2f85 / DIRECT_AGENT | WRENCH_LIMIT_EXCEEDED | 3 |
| H / robotiq_2f85 / SKILL_AGENT | EXCESSIVE_PENETRATION | 18 |
| H / robotiq_2f85 / SKILL_AGENT | FORBIDDEN_CONTACT | 62 |
| H / robotiq_2f85 / SKILL_AGENT | GOAL_NOT_REACHED_WITHIN_BUDGET | 1 |
| H / sharpa / DIRECT_AGENT | EXCESSIVE_PENETRATION | 13 |
| H / sharpa / DIRECT_AGENT | FORBIDDEN_CONTACT | 81 |
| H / sharpa / DIRECT_AGENT | PRECONDITION_NOT_MET | 2 |
| H / sharpa / DIRECT_AGENT | WRENCH_LIMIT_EXCEEDED | 1 |
| H / sharpa / SKILL_AGENT | EXCESSIVE_PENETRATION | 11 |
| H / sharpa / SKILL_AGENT | FORBIDDEN_CONTACT | 87 |
| H / sharpa / SKILL_AGENT | PRECONDITION_NOT_MET | 2 |
| H / wuji / DIRECT_AGENT | EXCESSIVE_PENETRATION | 19 |
| H / wuji / DIRECT_AGENT | FORBIDDEN_CONTACT | 80 |
| H / wuji / DIRECT_AGENT | PRECONDITION_NOT_MET | 1 |
| H / wuji / SKILL_AGENT | EXCESSIVE_PENETRATION | 17 |
| H / wuji / SKILL_AGENT | FORBIDDEN_CONTACT | 80 |
| H / wuji / SKILL_AGENT | PRECONDITION_NOT_MET | 1 |

## 测量与限制

- 每个原生响应 usage 按 responseId 去重后与 thread/tokenUsage 总值核对；cached input/reasoning output 是子集，不重复累加。
- 墙钟从 thread/start 前到 native turn/completed；Agent active=墙钟−工具处理时间。Runtime 进程初始化、初态准备与归档不计入 episode 墙钟；仿真时长来自 MuJoCo。
- 无中间 SHAPE target、Skill stage 或调用顺序门槛；C 的激活后退出是任务本身要求。F/H 名义版无外加扰动。
- C 保留 3 N，其余 4 N；保留原关节/effort、1 mm 穿透及全部连续时间、安全和接触区域规则。
- C 的随机旋转保留水平 world-Y 弹簧轴；所有原随机数仍按既定顺序采样，实际解析值写入 binding。自由圆柱的支撑高度由旋转后几何最低点计算。
- Native runtime、计量或额度错误停止该 worker，保留原尝试，不换模型、不自动重试。未完成批次不作最终成功率结论。

原始证据：`TASK_HAND_seedNNN/reset/` 保存资格、scene、初态与 binding；两个接口目录保存 prompt、工具 schema/calls、逐步 physics、native events/requests/usage 与最终结果。
