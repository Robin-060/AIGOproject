# EXP17 判据预注册：post-hoc Failure-driven Policy Refinement（2026-09-01 冻结）

> 本文件是 EXP17 的**判据预注册**（实验本身为 post-hoc failure-driven，见 §1）。
> 判据**先于任何改动实验冻结**，任何偏离即实验作废。
> v1.5.1 为冻结结果，本实验不修改、不覆盖其任何产物；全部输出使用新文件。

## EXP17-R1 预注册：融合容差 robustness check（2026-09-01，C 裁决后冻结）

> 触发：主 Claim 参数审计中 P0.30/S0.50 被列为红灯候选（legacy 常量、
> 与校准共识容差并存无 rationale）。本方案在**看到替代结果之前**冻结。

1. **代码核查事实（冻结前静态审计，非实验结果）**：当前运行路径中融合内聚
   容差读取的是 `config.consensus_tolerance_p_s/s`（= 校准共识容差 **0.34/0.51**，
   95% 分位导出）；`CONSENSUS_TOLERANCE = {P:0.30, S:0.50}` 仅剩
   `multi_model` 中 config=None 的兜底分支（运行中 config 恒存在，不触发），
   以及 `fusion.py` 一个未使用的 import。**即：0.30/0.50 不在冻结运行路径。**
2. **固定替代值**：P 0.34 / S 0.51（来源：既有校准共识容差，数据导出）。
3. **单变量检查**：确认 A 的候选池在该替代值下的四判据 + paired bootstrap；
   **不搜索任何其他容差、不重写历史配置、原 EXP17 结果保留。**
4. **裁决**：通过 → 作为 robustness evidence（红灯解除，主 Claim 不依赖
   legacy 常量）；不通过 → 降低 A 的 Claim 表述，不继续调参。

## 最终裁决（2026-09-01，C 方案 a）

- A（Consensus Route）**采用**：覆盖率 45.64%→54.13%（c1 ✓）、risk ranking
  保持且更强（c3 ✓：截获@50%预算 94.26%）、风险分箱单调（c4 ✓）；
  c2 未达：ΔUnsafe 点估计 +0.92pp（绿灯内），配对 cluster bootstrap 单侧
  95% 上界 +2.24pp，略超 +2.0pp 界（统计功效限制）。
- B（Only-usable-survivor）**弃用**（负结果）：c2（+4.87pp）+ c3（截获塌至
  64.55%）双败；A+B 累加 c2 亦败。
- 正式表述口径（C 定稿）："在不增加模型、不重新训练的情况下，failure-driven
  policy refinement 使自动覆盖率相对提高约 18.6%；同时 Trust 风险排序显著提高
  人工复核效率。安全性点估计接近 Voting，但在预设 +2pp 非劣界下尚未获得充分
  统计证据。" Review prioritization 明确成立；Automation coverage 明确恢复；
  **安全非劣只写"接近、未确认"，绝不写"持平"或"通过"**。

## 0. 修订记录（amendments）

- **v1.0（2026-09-01）**：A/B/C 三干预 + 判据 c1/c2（Coverage≥50%、ΔUnsafe 单侧
  95% 上界 <+2.0pp vs 6.04%）+ holdout 辅助。A 验收 PASS。
  （v1.0 口径：锚点 6.04%、参照点固定 bootstrap；后被最终裁决修订，见下一条。）
- **v1.1（2026-09-01，C 指示，先于 B 判定复核冻结）**：补充判据 c3/c4——
  政策优化**只针对自动决策路径，不得破坏已获胜的 risk ranking**：
  - c3 Review Budget 曲线保持：截获@50% 复核预算（点估计）≥ v1.5.1 冻结值
    （`results/review_budget_summary.json` 的 83.6%），全曲线一并报告；
  - c4 风险分箱排序保持：可靠箱（n≥10）错误率严格单调不减。
  四项判据**全部**满足才 PASS；任何一项失败即回退并记负结果。
- **最终裁决修订（2026-09-01，C 方案 a，先于采用决定）**：c2 锚点由"v1.5.1
  天花板点 6.04%"修订为 **Voting@50% 冻结锚点 4.59%**，bootstrap 由参照点固定
  改为**配对 station-cluster bootstrap**（EXP 与 Voting 同轮重采样，60 台站 ×
  1000 次，seed 42）；A 的 c2 结论相应由 v1.0 的"验收 PASS"修正为**未确认**
  （点估计 +0.92pp，单侧 95% 上界 +2.24pp > +2.0pp 界）。c3/c4（v1.1）不变。
  留痕产物：`results/paired_bootstrap_A.json`、
  `results/exp17_summary_A.json`（bootstrap_source 字段）。

## 1. 实验身份与边界

- **定位**：post-hoc failure-driven policy refinement——在 v1.5.1 冻结实验发现
  "Trust 在 45.64% 形成 coverage ceiling"之后，由 failure analysis 驱动的
  算法机制改进验证，不改变数据/seed/模型/判据/指标/DS。
- **允许改动**：仅 `policy_router.py` 的决策逻辑（三个预注册干预，单变量）。
- **禁止改动**：TrustConfig 参数、数据罚分、置信校准、物理/分歧阈值、风险权重、
  数据、seed、正确性判据、五个 DS 的定义与判定。

## 2. 诊断依据（v1.5.1 冻结引擎重放, ranking_mode）

703 个未自动输出单元分解（`results/policy_diagnosis.json`）：

| 卡点 | n | 有正确拾取 | 全部拾取正确 |
|---|---|---|---|
| 第 5 步 INSUFFICIENT_EVIDENCE_FOR_SELECTION | 487（P229/S258） | 430 | 312 |
| 第 4.5 步 CONSENSUS_WITHOUT_ADMISSIBLE_FUSION | 112 | 105 | 89 |
| 分歧 | 99 | 91 | 10 |

细分：第 5 步 487 条全部为 `consensus=INSUFFICIENT` 且 survivors ≥2
（479 条 n_survivors=2）；312 条全部拾取正确；471 条最高校准置信度 ≥0.70。
第 4.5 步 112 条中 101 条已满足 floor 0.70（卡点是融合结构门槛，非置信门槛）。

## 3. 三个干预（顺序 A→B→C，单变量，逐个独立验收）

### A. Consensus Route（第 4.5 步）
- 现状：CONSENSUS 但无通过全部门槛的融合候选 → ABSTAIN（fail-closed）。
- 改动：CONSENSUS 且融合候选不可接受时，若共识簇内存在"有该相位真实拾取、
  校准置信度 ≥0.70、相位风险 ≤ 自动阈值"的幸存模型 → ROUTE 其中**校准置信度
  最高**者（tie-break: 模型名字典序, 确定性）；否则维持 ABSTAIN。
- 不改：融合判定本身、floor 值、风险门槛。

### B. Only-usable-survivor（第 3 步触发条件扩展）
- 现状：`len(survivors)==1` → ACCEPT/ROUTE；否则继续后续步骤。
- 改动：触发条件扩展为 `len(survivors)==1` **或**（survivors ≥2 且恰有 1 个
  survivor 有该相位拾取）→ 按第 3 步原逻辑执行（含风险门槛检查与
  primary_model 判定）。有拾取 survivor >1 时维持原流程。
- 不改：共识/分歧判定、outlier 逻辑、风险门槛。

### C. Fusion floor sweep（仅报告）
- 校准置信度门槛 0.70 → 0.65 → 0.60 → 0.55 四个级别逐一重跑，
  完整报告 Coverage / Unsafe / Interception / Review Burden 曲线；
  **默认值不变**，任一级通过主判据仅作记录，不自动升为正式参数。

## 4. 验收标准（钉死，逐干预适用）

> ⚠️ 本节为 v1.0/v1.1 判据原文（留档）。**最终生效口径见顶部「最终裁决」与
> §0 修订记录**：c2 锚点已修订为 Voting@50%（4.59%）+ 配对 bootstrap，
> A 的 c2 结论为"未确认"而非 v1.0 原文的"验收 PASS"。

**主判据 1（覆盖率可达）**：Trust 覆盖率天花板 ≥ 50%
（50% 预声明点位 COMPARABLE）。

**主判据 2（安全不显著恶化）**：EXP17@50% 的 Unsafe 与 v1.5.1 天花板点
Unsafe 6.04% 的差值，按主实验同款 cluster paired bootstrap（60 台站 × 1000 次，
seed 42）计算，**单侧 95% CI 上界 < +2.0pp 视为不显著恶化**；否则该干预判定
失败，回退改动，**禁止为达标再微调该干预参数**。

**辅助判据 3（holdout 一致性）**：holdout 分片上该干预的覆盖率不下降，
且 Unsafe 变化方向与主结果不矛盾（仅报告，作定性一致）。

**判据 3（v1.1，C 指示）Review Budget 曲线保持**：EXP17 在 50% 复核预算下的
错误截获率（点估计）不低于 v1.5.1 冻结值 83.6%；0-60% 全曲线与四策略对比
一并报告，不允许 Trust 排序优势坍塌。

**判据 4（v1.1，C 指示）风险分箱排序保持**：可靠箱（n≥10）的错误率严格
单调不减（DS2 的口径保持）；各箱 n/错误率一并报告。

**辅助判据 4（仅报告）**：Error Interception@50% 复核预算与 Review Budget
曲线的其余细节。

**组合规则**：通过主判据的干预按 A→B→C 顺序累加，每次累加后重新核验全部
判据；任何一步失败则从组合中移除该干预并记录负结果。

## 5. 文件与记录纪律

- 所有 EXP17 产物使用 `_exp17` 后缀新文件（main_results_exp17.csv 等），
  不覆盖任何 v1.5.1 结果文件；运行身份 `config_version=experiment_exp17`。
- 每个干预的完整数字与 bootstrap CI 进 `results/exp17_*.json`；
  结论进探索日志 EXP17 卡片（含失败干预的负结果）。

## 6. No-Go

- 禁止在判据失败后调整权重/阈值/罚分"再试一次"（单变量一次判定）。
- 禁止删除或修改 v1.5.1 的任何负结果记录。
- 禁止新增模型、重新训练、更换数据或真值。
