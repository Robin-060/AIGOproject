# OBS Trust Layer — 最终实验报告（EXP16 / EXP17 冻结版）

> 版本基线：`semifinal_v1.5.1-bugfix`（config hash `9727570d…602b6d`，parent `semifinal_v1.5.1`）
> 证据基线：`results/evidence_manifest.json`（全部关键文件 sha256、c1–c4 裁决、文件分类）
> 统一结论（全材料口径）：**Coverage recovery supported; safety non-inferiority inconclusive.**

## 1. 摘要

本项目研究"多模型 AI 拾取进入真实 OBS 科研工作流时，哪些输出应自动进入后续流程、哪些应优先交给专家复核"。不重训模型，在冻结数据、冻结模型、统一相位级评价协议下，形成三项相互独立的主成果：

| 成果 | 核心结果 | 科学结论 |
|---|---|---|
| 人工复核效率（EXP16） | 50% 复核预算截获 83.6% 错误（Random 50.0%），CI [+19.0,+35.65]；holdout 80.1% | Trust 风险排序显著提高单位复核预算的错误截获效率 |
| 自动化瓶颈诊断（v1.5.1） | Coverage 天花板 45.64%（596/1306）；703 个未自动输出分解为 487/112/99/5 | Low Coverage was primarily policy-limited，而非模型普遍无候选 |
| Failure-driven refinement（EXP17） | EXP17-A：Coverage 45.64%→**54.13%**，Unsafe 5.51%，截获 94.26%；ΔUnsafe 点估计 +0.92pp，配对 bootstrap 单侧 95% 上界 **+2.24pp** | Coverage recovery supported；safety non-inferiority **inconclusive** |

- EXP17-A 判据：**c1 PASS、c2 NOT ESTABLISHED、c3 PASS、c4 PASS**（c2 上界 +2.24pp 高于 +2.0pp 冻结界 0.24pp）。
- EXP17-B（Only-usable-survivor）负结果完整保留：Coverage 81.62% 但 c2 +4.87pp、c3 64.55% 双败，弃用。
- R1（参数来源审计）：显式固定 P=0.34s / S=0.51s 重跑与冻结 EXP17-A 完全一致，76/76 tests passed——**R1 PASS 仅表示执行路径不依赖 legacy 0.30/0.50 常量，不代表 EXP17 总体安全 Gate PASS**。
- v1.5.1 原始负结果不被覆盖：45.64% 天花板、50% 点位 NOT_EVALUABLE、S 相显著更差。

## 2. 研究问题与成果总览

- **RQ1**：如何综合数据质量、多模型分歧及流程一致性证据，对 AI 拾取结果的错误风险进行评估，并在自动覆盖率与不安全输出风险之间形成可验证的选择性决策机制？
- **RQ2（Derived）**：当严格 policy 造成自动 Coverage ceiling 时，能否利用推理时可见证据恢复部分 Coverage，同时保持 Unsafe 非劣与 review prioritization 能力？
- **测量纪律**：Coverage 永远与 Unsafe 同报；Error Interception 永远与 Review Burden 同报；自动化安全比较与人工排序比较使用不同参照、共享冻结评价单元与错误定义，不得把"排序更好"改写成"同 Coverage 下更安全"。

## 3. 主实验 v1.5.1（冻结结果，保留）

- 评估单元：1306 个 Primary 相位单元（P 657 + S 649）；错误全集 746（wrong 36 + no_pick 710）。
- 真实有效输出 596/1306 = **45.64%**（560 correct / 36 wrong / 710 no_pick）；预声明 50% 点位 **NOT_EVALUABLE**（不可达点位不填 Unsafe、不做显著性结论）。
- 天花板补充比较（非声明点位）：总体 Δ=+1.17pp，CI [−1.09,+2.93] → INCONCLUSIVE；**S 相在自身 45.45% 天花板处显著更差**（Δ=+3.39pp，CI [+0.90,+5.96]）。DS1（同 Coverage 下更安全）未成立。
- 原始产物冻结于 `results/v151_archive/`，任何后续实验（bugfix、EXP17）不改写该目录。

## 4. EXP16 Review Efficiency（明确正结果）

在冻结预测上比较四种送审排序（不重训模型、不改 Trust score、不改 DS），错误全集 746，作用于相同 1306 单元：

| Review budget | TrustRisk | Random | ModelConf | Disagreement |
|---|---:|---:|---:|---:|
| 5% | 8.7% | 5.0% | 8.6% | 6.7% |
| 10% | 17.4% | 10.1% | 15.8% | 13.7% |
| 20% | 34.5% | 20.0% | 27.7% | 27.7% |
| 30% | 51.2% | 30.0% | 39.3% | 37.7% |
| 50% | **83.6%** | 50.0% | 59.9% | 56.3% |

- 统计背书（cluster bootstrap，60 台站 × 1000 次，seed 42）：Trust−Random 全预算点显著（50% 预算 Δ=+33.6pp，CI [+19.0,+35.65]）；Trust−Disagreement 全点显著；Trust−ModelConf 在 ≥10% 预算显著，5% 点 INCONCLUSIVE（如实保留）。
- holdout 佐证（260 单元 / 161 错误）：Trust 80.1% vs Random 49.9% / ModelConf 56.5% / Disagreement 59.0%。
- 同截获率所需预算（反查表）：80% 截获率 Trust 需约 47% 复核预算，Random 需 80%。
- 边界：该结果支持"风险排序提高复核效率"，未做真实人工时间/成本实验，不宣称"人工成本下降 X%"。

## 5. EXP17 Policy Refinement（post-hoc，failure-driven）

### 5.1 身份与边界

EXP17 是 v1.5.1 之后的 **post-hoc failure-driven refinement**，不是原始预声明实验；判据预注册于 `docs/experiments/exp17_preregistration.md`（先于干预执行冻结，修订记录留痕）。实验不修改数据、模型、GT、容差、seed、Voting 参照与 +2.0pp 界；routing rule 只使用推理时可见证据（truth-blind），禁止使用 evaluation truth。

### 5.2 bugfix 与 refinement 分轨

- `v1.5.1-bugfix`（`3efc94c`）：ROUTE 必须选择具有目标相位有效 prediction 的模型——修复 7 个 invalid-pick action，核心数值零变化，**不计算法贡献**。
- EXP17-A/B/C 在 bugfix 基线上单变量评估。

### 5.3 诊断（`results/policy_diagnosis.json`）

703 个未自动输出：Step 5 证据不足 487（430 个至少一模型正确，312 个全对，仅事后诊断）、Step 4.5 共识无融合 112（105/89）、真分歧 99（91/10）、其他 5。101/112 已满足 FUSE floor 0.70——瓶颈是证据准入与 routing 保守，而非置信门槛。距离 50% Coverage 只差 57 个真实 selected pick。

### 5.4 干预结果与判据

| 方案 | c1 Coverage | c2 Safety | c3 Review @50% | c4 分箱 | 裁决 |
|---|---|---|---|---|---|
| A Consensus Route | 54.13% ✓ | 点估计 +0.92pp；上界 +2.24pp ✗ | 94.26% ✓ | 4.17→9.14→28.57 ✓ | **采用**（c2 未确认，不宣称整体 PASS） |
| B Only-usable-survivor | 81.62% ✓ | 上界 +4.87pp ✗ | 64.55% ✗ | PASS | **弃用**（safety+ranking 双败，负结果保留） |
| A+B 累加 | 90.12% ✓ | 上界 +4.0pp ✗ | 84.96% | — | **弃用组合**（留档） |
| C floor sweep | 0.60→51.76%；0.55→53.22% | 各档 c2 均 ✗ | — | — | 留档实验，不升级；均劣于 A |

c2 判据：ΔUnsafe = Unsafe_EXP17@50 − Voting@50（冻结锚点 4.59%），配对 station-cluster bootstrap（60 台站 × 1000，seed 42）单侧 95% 上界 < +2.0pp。点估计 ≤+1.0pp 仅为内部绿灯，不替代 c2。

### 5.5 R1 参数来源审计

运行路径 fusion 内聚容差读取校准导出值 P=0.34s / S=0.51s；legacy 常量 0.30/0.50 仅剩 config=None 兜底，不在冻结运行路径。显式固定 0.34/0.51 重跑与冻结 EXP17-A 完全一致（54.13% / 5.51% / 94.26% / 上界 +2.24pp），76/76 tests passed。**R1 PASS 仅表示参数路径复现一致。**

### 5.6 统一结论

> **Coverage recovery supported; safety non-inferiority inconclusive.**
> c1/c3/c4 PASS，c2 NOT ESTABLISHED；R1 PASS 仅表示参数路径复现一致，不代表 EXP17 总体通过。

## 6. 失败结果与负结果（如实保留）

1. DS1 未全线成立：同 Coverage 下不比 Voting 显著更安全（天花板补充比较 INCONCLUSIVE）。
2. S 相长尾显著更差：45.45% 天花板处 Δ=+3.39pp，CI [+0.90,+5.96]。
3. EXP17-B 双败（c2 +4.87pp、c3 64.55%）——"覆盖率好看 ≠ 可接受"的实证。
4. EXP17-A 的 c2：点估计 +0.92pp 在工程界内，但 CI 级非劣未建立（上界 +2.24pp > +2.0pp）。
5. EXP17-C floor sweep：全局降 floor 可推开天花板但均劣于 A。
6. DS3 分歧-错误相关性不成立（P 不显著、S 极弱；"完全一致也会错"11.3%/8.0%）。
7. DS4 相关性不成立（自然数据上缺道/低信号与错误风险无关）。
8. DS5 原条款不成立（_BLANCO 跨域后与 Voting 同降至 21.5%）。
9. 22 个漏检反例（含 15 个 wrong 输出中至少一个单模型正确、7 个 >30s 错误全部为 S 相）见 `results/failure_raw.csv`。
10. 历史小样本校准、故障注入、非单调 risk curve 等早期方法保留于 `docs/experiments/legacy/`。

## 7. Limitations

1. EXP17 为 post-hoc failure-driven 验证，不是独立 blind confirmatory test；判据预注册不等于原始预声明实验。
2. c2 的 CI 级安全非劣未建立（+2.24pp > +2.0pp 界），需要更大样本进一步确认。
3. 风险权重拟合含 holdout 记录，holdout 仅作一致性佐证，不是独立 locked test。
4. 第二数据域 _BLANCO 与主域同数据集不同台阵，不证明跨数据集泛化。
5. Trust risk 是 ordinal score，不是校准错误概率。
6. 结果不等价于 production deployment safety；未做真实专家工时、成本或下游 catalog 影响实验。
7. 数据/模型训练重叠未审计（overlap UNKNOWN），相关结论按 C 契约降级表述。

## 8. No-Go 与表述纪律

- 不写 EXP17-A"整体通过""与 Voting 持平""非劣成立"或"证明安全"；不把 c2 未通过写成"算法已证明劣化"。
- 不把 legacy P=0.30/S=0.50 误写为冻结运行参数；不把 post-hoc EXP17 描述为原始预声明实验。
- 不把 ROUTE bugfix 包装成算法贡献；不把 +2.0pp 界事后改为 +2.3pp，不更换 bootstrap 口径择优。
- 不把 risk 称为概率；不把 review ordering 称为替代专家或已降低实际人工成本。
- 不写跨数据集泛化、严格独立 locked test、production deployment 或全面安全自动化。

## 9. 补充实验：SeisBench 20 条噪声鲁棒性

> 本节为早期小样本补充实验（非主结果），降级保留作 Demo 与边界证据。

公开 OBS `test` split 固定选 20 条四通道波形，四档噪声（L0 原始 / L1 10dB / L2 5dB / L3 2dB），PhaseNet-geofon、PickBlue、OBSTransformer 真实推理：

| 噪声 | 方法 | 正确 | 拒绝 | 不安全错误 | 安全处理率 |
|---|---|---:|---:|---:|---:|
| L0 | OBSTransformer | 18 | 0 | 2 | 90% |
| L0 | 最高置信度 | 18 | 0 | 2 | 90% |
| L0 | Trust Layer | 8 | 12 | 0 | 100% |
| L1–L3 | Trust Layer | 0 | 20 | 0 | 100% |

解读（如实）：Trust Layer 四档均未放行错误 P/S 对，但其 L1–L3 覆盖率是 0——结论是"高噪下不乱给答案"，不是"高噪下仍能准确拾取"。20/20 对应 Wilson 95% 区间约 83.9%–100%，不宣称外推。结果文件：`noise_predictions_seisbench.json`、`noise_records_seisbench.csv`、`noise_summary_seisbench.csv`。

## 10. Demo 与工程

Streamlit Demo（`src/web/`）消费冻结结果与真实 Trust Engine：Fixed（冻结反馈/Equal-Coverage/R1 面板）、Searchable（risk threshold、P/S tolerance、evidence weight 可调）、Feedback（Coverage+Unsafe、Interception+Review 成对展示）、Case Explorer（真实失败样本 + ABSTAIN 确定性解释，reason code 模板见 `schema_contract.md` §13）。Docker Compose 双服务（FastAPI :8000 + Streamlit :8501）。架构与调用关系见 `docs/architecture_diagrams.md`（含 PNG 图）。

## 11. 复现

- 主链一键复现：`bash reproduce_core.sh`（等价 `python -m src.experiments.reproduce_main`，九步，含冻结物 sha256 校验）。
- EXP17 复现命令与预期数字：见 `docs/reproduction.md` §8。
- 测试：`python -m pytest -q` → 76 passed。
- 证据交接包：`results/evidence_manifest.json`。

## 12. 结论

Trust Layer 的组合风险证据可用于人工复核优先级排序（EXP16 正结果）；failure decomposition 证明 45.64% 天花板来自 policy 保守而非模型无候选；truth-blind EXP17-A 将 Coverage 恢复至 54.13%（Unsafe 5.51%，截获 94.26%），且结果不依赖 legacy 参数——但相对 Voting 的 CI 级安全非劣尚未建立。所有负结果、bugfix 与 refinement 分轨留痕，全部数字可沿 data → config → script → raw result → figure/table 追溯。
