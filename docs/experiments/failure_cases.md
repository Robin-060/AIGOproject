# Trust Layer 失败案例与反例（复赛冻结口径）

> 数字源：`results/failure_raw.csv`、`results/policy_diagnosis.json`、
> `results/exp17_summary_A.json` 和 `results/paired_bootstrap_A.json`。

## 1. 为什么必须报告失败

Trust Layer 的目标不是隐藏错误，而是使错误、拒答、自动覆盖和人工复核代价可测量。
所有案例分析都服从同一条边界：真值只能用于事后评价与诊断，不能进入当前样本的 routing rule。

## 2. v1.5.1 冻结失败全景

| 类别 | 数量 | 含义 |
|---|---:|---|
| Primary phase units | 1306 | 统一评价分母 |
| 错误全集 | 746 | 710 no-pick + 36 wrong |
| wrong 输出中至少一个单模型正确 | 15 | 路由/融合可能覆盖正确候选 |
| 误差超过 30 s | 7 | 全部为 S 相，提示 S 相长尾风险 |

v1.5.1 在自身最大 Coverage 处的 S 相补充比较显著差于 Voting：
ΔUnsafe = +3.39pp，95% CI [+0.90,+5.96]。这是冻结负结果，不被 EXP17 覆盖。

## 3. 共识不等于正确：典型 shared-error 反例

| 字段 | 值 |
|---|---|
| sample | `XO.LT04..HH.2018.07.12.08.32.02` |
| phase | S |
| truth | 44.99 s |
| FUSE | 142.61 s（错误） |
| EQTransformer | 44.84 s（正确） |

该案例表明：多数模型的一致输出仍可能是 shared error，并且可以覆盖少数正确模型。
因此 EXP17-A Consensus Route 仍必须服从 Safety Gate；“一致”只是候选证据，不是安全保证。

## 4. Policy ceiling 与真值使用边界

703 个未自动输出单元的分解为 487 / 112 / 99 / 5。事后诊断发现，487 个第 5 步案例中
有 312 个全部模型拾取正确；112 个第 4.5 步案例中有 89 个全部模型拾取正确。
这些数字说明保守准入是 Coverage ceiling 的重要来源，但它们只是事后诊断证据：

- 允许：用于提出 RQ2、定位流程阶段、设计 truth-blind 候选规则；
- 禁止：根据某样本是否正确决定是否放行，或直接根据 312/487、89/112 反推最终规则。

## 5. EXP17 中的失败候选

| 干预 | Coverage | Safety / Review | 处置 |
|---|---:|---|---|
| A Consensus Route | 54.13% | c2 上界 +2.24pp > +2.0pp | 保留为最佳候选；非劣未确认 |
| B only-usable-survivor | 81.62% | c2 +4.87pp；c3 64.55% | 双败，弃用 |
| A+B | 90.12% | c2 +4.0pp | 弃用组合，留档 |
| C floor sweep | 最高 53.22% | 各档 c2 均未通过 | 不升级 |

这些反例是开放探索中的有效信号：Coverage 可以很容易被放大，但 Coverage 更高不等于
安全或排序价值更高。

## 6. 当前裁决

EXP17-A 的点估计为 ΔUnsafe +0.92pp，但配对 station-cluster bootstrap 单侧 95% 上界为
+2.24pp，高于 +2.0pp 界。因此只能表述为：

> **Coverage recovery supported; safety non-inferiority inconclusive.**

该结论既不将 c2 未通过误写成“算法已证明劣化”，也不将点估计接近误写成
“持平”或“已经通过”。
