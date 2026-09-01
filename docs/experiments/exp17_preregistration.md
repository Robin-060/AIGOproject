# EXP17 预注册：Failure-driven Policy Refinement（2026-09-01 冻结）

> 本文件是 EXP17 的预注册判据。**先于任何改动实验冻结**，任何偏离即实验作废。
> v1.5.1 为冻结结果，本实验不修改、不覆盖其任何产物；全部输出使用新文件。

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

**主判据 1（覆盖率可达）**：Trust 覆盖率天花板 ≥ 50%
（50% 预声明点位 COMPARABLE）。

**主判据 2（安全不显著恶化）**：EXP17@50% 的 Unsafe 与 v1.5.1 天花板点
Unsafe 6.04% 的差值，按主实验同款 cluster paired bootstrap（60 台站 × 1000 次，
seed 42）计算，**单侧 95% CI 上界 < +2.0pp 视为不显著恶化**；否则该干预判定
失败，回退改动，**禁止为达标再微调该干预参数**。

**辅助判据 3（holdout 一致性）**：holdout 分片上该干预的覆盖率不下降，
且 Unsafe 变化方向与主结果不矛盾（仅报告，作定性一致）。

**辅助判据 4（仅报告）**：EXP16 Review Budget 曲线（Trust 排序优势）与
Error Interception@50% 复核预算在干预后是否保持。

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
