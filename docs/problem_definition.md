# OBS Trust Layer：最终科研问题定义

> GOAI 2026 · 赛道三 AI for Research · 复赛最终口径
> 证据基线：`semifinal_v1.5.1-bugfix` + EXP16 + EXP17 最终裁决协议。

## 1. 科研问题

海底地震仪（OBS）波形中的 P/S 相拾取是事件关联、定位和地震目录构建的上游环节。
多个深度学习模型可以给出拾取结果，但真实科研流程中的核心问题不是“模型总体准不准”，而是：

> 哪些 AI 输出可以自动进入后续地震科研流程，哪些必须交给专家复核？

### RQ1

如何综合数据质量、多模型分歧及流程一致性证据，对 AI 拾取结果的错误风险进行评估，
并在自动处理覆盖率与不安全输出风险之间形成可验证的选择性决策机制？

### RQ2（由 policy ceiling 派生）

当严格的选择性决策导致自动覆盖率受限时，能否利用推理时可见证据，
在不显著恶化 Unsafe 的前提下恢复部分自动处理能力，同时保持对有限人工复核资源的有效排序？

RQ2 不是为跨过 50% Coverage 而事后设定的工程目标，而是 v1.5.1 冻结负结果
暴露 policy ceiling 后形成的派生研究问题。

## 2. 最小可验证参考框架

| 层级 | 固定对象 | 可检查输出 |
|---|---|---|
| 数据 | 公开 OBS 数据，895 records，1306 Primary phase units | manifest、真值、质量清单与 SHA-256 |
| 模型 | 四套 checkpoint：PhaseNet geofon / PhaseNet obs / OBSTransformer / EQTransformer | model registry、冻结预测与身份指纹 |
| 基线 | Random、ModelConf、Disagreement、Voting 等 | 同一评价单元下的基线结果 |
| 选择性评价 | Coverage + Unsafe 成对报告 | Equal-Coverage、NOT_EVALUABLE 与 cluster bootstrap |
| 人工复核评价 | Review Burden + Error Interception 成对报告 | 全预算曲线、holdout 方向一致性佐证 |

评价协议固定 P/S 正确性容差、相位级分母、错误定义和台站聚类 bootstrap。
holdout Primary 为 260 个相位单元；358 是原始 manifest 全部 holdout 行数。holdout 仅用于
方向一致性佐证，不是独立 locked test。

## 3. 探索环境：Fixed / Searchable / Feedback

| 类型 | 本项目定义 | 复赛中的边界 |
|---|---|---|
| Fixed | 数据身份、模型预测、评价单元、错误定义、参照系 | 修订必须版本化，不覆盖历史冻结产物 |
| Searchable | 准入证据、routing 逻辑、参数、候选 refinement | 只允许使用推理时可见证据，禁止 evaluation truth |
| Feedback | Coverage/Unsafe、Review/Interception、CI、失败分解 | 负结果必须留档；不可达点不填充数值 |

Demo 将这一研究环境映射为可交互的波形、模型拾取、证据分解、固定反馈与案例浏览器；
前端不独立重算或伪造科研指标。

## 4. 主要发现

### 4.1 Review prioritization（EXP16）

在固定人工复核预算下，Trust 风险排序更早截获错误。50% 复核预算时，
全量错误截获率为 83.6%，Random 为 50.0%；Trust−Random = +33.6pp，station-cluster bootstrap
95% CI 为 [+19.0,+35.65]。holdout Primary 为 80.1%，方向与全量一致。

该结果支持“提高单位人工复核预算的错误截获效率”，不支持“真实人工成本下降 X%”；
本项目未做专家用时或成本实验。

### 4.2 Policy ceiling diagnosis（v1.5.1）

v1.5.1 真实 selected-pick Coverage 为 596/1306 = 45.64%。703 个未自动输出单元中，
487 个停在 `INSUFFICIENT_EVIDENCE_FOR_SELECTION`，112 个具有共识但无法 FUSE；距离 50%
Coverage 仅差 57 个真实 selected pick。

事后诊断发现，487 个单元中 312 个所有模型拾取均正确，112 个单元中有 89 个所有模型
拾取均正确。这些真值统计只能用于事后诊断，不得作为 EXP17 routing rule 的输入或直接
反推规则。证据支持的克制结论是：

> 当前 Coverage ceiling 主要反映 policy conservatism，而不是模型普遍没有可用候选。

### 4.3 Failure-driven policy refinement（EXP17）

EXP17 为 post-hoc、failure-driven refinement，不是原始预声明实验。数据、模型、评价单元与
truth-blind 边界保持冻结；四项判据按最终裁决协议执行，c2 的 Voting@50 配对 bootstrap
口径在探索过程中完成修订并留有版本记录，不构成严格预注册确证。

| 结果 | 数值 | 裁决 |
|---|---:|---|
| c1 Coverage | 54.13%（相对 45.64% 提升约 18.6%） | PASS |
| c2 Safety | ΔUnsafe +0.92pp；单侧 95% 上界 +2.24pp | NOT ESTABLISHED（高于 +2.0pp 界） |
| c3 Review | 50% 预算截获 94.26% | PASS |
| c4 Risk bins | 4.17% → 9.14% → 28.57% | PASS |

EXP17-A 只保留为表现最佳的候选 refinement，用于报告 Coverage recovery；由于 c2 未建立，
不视为已通过安全非劣 Gate 的部署策略。EXP17-B 虽达到 81.62% Coverage，但 c2/c3 双败，
已弃用并作为负结果留档。

## 5. 最终 Scientific Claim

> 在固定 OBS 数据、冻结模型与统一相位级评价协议下，组合风险证据能够用于人工复核优先级排序，
> 并在 holdout Primary 子集中保持方向一致的错误拦截优势；v1.5.1 的严格自动决策策略存在明显
> policy ceiling，truth-blind EXP17-A 将 Coverage 恢复至 54.13%，Unsafe 为 5.51%，但在最终裁决的
> +2.0pp 界下，CI 级安全非劣尚未统计确认。

统一英文裁决：**Coverage recovery supported; safety non-inferiority inconclusive.**

## 6. 科研边界

- 不声称 EXP17 “总体通过”“与 Voting 持平”“非劣成立”或“证明安全”。
- 不将 R1 reproduction PASS 解释为 c2 或 EXP17 总体 Gate PASS。
- 不把 holdout 描述为独立 locked test，不声称跨数据集普适泛化。
- 不将 ordinal risk score 称为已校准的错误概率。
- 不将 ROUTE invalid-pick bugfix 包装成算法贡献。
- 不把 review coverage 下降直接等价为真实劳动成本下降。
- 不声称 production deployment、自主科研 Agent 或全面安全自动化。

详细证据、负结果、复现命令与许可证边界分别见 `docs/final_report.md`、
`docs/exploration_log.md`、`docs/reproduction.md` 和 `docs/data_and_model_sources.md`。
