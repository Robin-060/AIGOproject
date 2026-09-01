# EXP16 实验说明：Review Budget–Error Interception 曲线（v1.5.1）

> 对应结果: results/review_budget_curve.csv / review_budget_summary.json /
> review_budget_ci.json / review_budget_interpolation.json /
> review_budget_summary_holdout.json 与 figures/review_budget_curve.png
> （含 *_holdout 变体）。生成脚本: src/experiments/review_budget_curve.py +
> review_budget_ci.py；复现链第 8 步自动重出。

## 1. 问题与计算口径

**问题**：人工复核预算固定时（只能送审 x% 的单元），按什么顺序送审能截获最多错误？

**单元与错误全集**：1306 个 (sample_id, phase) 相位级 Primary 单元；
错误全集 = verdict ∈ {wrong, no_pick}，共 **746 个**（与 failure_raw.csv、
主实验拦截率口径完全一致；no_pick 指真值要求该相位但无任何模型拾取）。

**送审规则**：每种策略对全部 1306 单元计算"可疑度"，按可疑度**降序**取前
k 个送审，k = round(budget% × n)（四舍五入；每个预算的 k 即 CSV 的
reviewed_n 列）。

**四种策略的可疑度定义**（全部只使用推理时可获得的冻结信号）：

| 策略 | 可疑度 | 备注 |
|---|---|---|
| Random | 无（随机顺序） | 100 个种子的平均截获率；期望 = 预算本身（对角线） |
| ModelConf | 1 − 该相位可用模型的最大置信度 | 无拾取 → 0，排最后（信号缺失不视为可疑） |
| Disagreement | 该相位可用拾取的最大差 spread（秒） | <2 个拾取 → 0 |
| TrustRisk | main_results.csv 的冻结风险分 | v1.5.1 引擎输出 |

## 2. 排序方向与 tie handling

- 方向：可疑度**降序**（最可疑最先送审）。注意 TrustRisk 的"自动接受"方向
  与此相反——Equal-Coverage 接受是风险最低者优先，而复核队列是风险最高者
  优先，两者是同一风险分的两种用法，勿混淆。
- Tie handling：`np.argsort(-suspicion, kind="stable")`——同可疑度的单元按
  原始单元顺序（build_phase_units 的 manifest 顺序）排列，确定性、可复现。
- Random 无排序：用 100 个独立种子取平均（种子 0..99），报告期望值
  （对角线），不报告单次抽样波动。

## 3. 指标定义

- 截获错误率 (%) = 送审单元中命中的错误数 ÷ 错误全集 746 × 100；
- 精确率 (%) = 送审单元中命中的错误数 ÷ 送审单元数 k × 100
  （即"审一份值不值"）。

## 4. Trust 实际运行点（89.6% 的含义）

- 运行点定义：复核负担 = 100% − Trust 覆盖率天花板 45.64% ≈ **54.36%**
  （即 v1.5.1 冻结引擎"自然状态"下会送人工复核的比例）；
- 该点截获 **85.3%** 的错误；精确率 **89.6%** 的含义：**送审单元中约九成是
  真实错误**——这是风险排序对错误的富集能力的直接度量，不是"系统正确率"。

## 5. 主要结果

- 全量：TrustRisk 在每个预算点领先（50% 预算截获 83.6% vs ModelConf 59.9% /
  Disagreement 56.3% / Random 50.0%）。
- holdout 一致性佐证（260 单元）：Trust 80.1% / Disagreement 59.0% /
  ModelConf 56.5% / Random 49.9%。
- 统计背书（cluster bootstrap，60 台站 × 1000 次，seed 42）：
  Trust−Random 全预算点单侧 95% 下界 > 0（50% 预算 Δ=+33.6pp，
  CI [+19.0,+35.7]）；Trust−Disagreement 全点显著；Trust−ModelConf 在 ≥10%
  预算显著、5% 点 INCONCLUSIVE（如实保留）。
- 同截获率所需预算：80% 截获率 Trust 需 47% 复核 vs Random 80%。

## 6. 边界与措辞红线

- 风险分在同评估数据上校准，排序优势含样本内成分；holdout 按冻结协议表述为
  "一致性佐证"，不写"独立验证"；
- 该实验证明的是"排序信号对比"，不是真实人工实验——不宣称节省了多少工时；
- 截获率只与错误全集 746 比较，错误集不变则数字可复现（复现链第 8 步）。
