# 复现说明（Reproduction Guide）

> 对应复赛交付"README 与复现说明"及 C 契约复现要求
> （运行入口、依赖安装、配置方法、随机种子、raw results 可检查）。

公开仓库：<https://github.com/Robin-060/AIGOproject>。正式提交以包内
`SUBMISSION_MANIFEST.md` 记录的不可变 release tag 与 commit 为准，不以评审期间的
分支最新状态替代冻结身份。

## 1. 一键入口

```bash
pip install -r requirements-core.txt     # A 最小复现依赖（不含模型推理/Demo）
bash smoke_test_a.sh                     # A: 配置 + 完整 hash + A 测试
bash reproduce_core.sh                   # 一键复现核心数字与三张主图
# 等价于: python -m src.experiments.reproduce_main
```

复现范围：冻结数据校验 → 基线对比 → 主实验（冻结档案 hydrophone_v2，直接读取、不重新选优）→ 全方法对比 → bootstrap → 主图 → 探索轨迹。
**全程使用冻结预测，不运行模型推理**（预测是冻结物；重跑模型的入口见第 6 节）。
shell 入口适用于 Linux/macOS，以及安装了 Git Bash 或 WSL 的 Windows；
纯 PowerShell 可直接运行等价 Python 命令。

EXP17（post-hoc refinement）的复现命令与预期数字见 **§7**；
全部关键文件的 sha256 与 c1–c4 裁决见 `results/evidence_manifest.json`。

## 2. 环境

| 包 | 版本 |
|---|---|
| A 核心复现 | 见 requirements-core.txt；不加载模型权重 |
| 完整推理参考环境 | seisbench 0.12.3 / torch 2.13.0+cpu / obspy 1.5.0 |
| 已验证 clean 环境 | seisbench 0.12.5 / torch 2.13.0 / obspy 1.5.1（冻结预测结果一致） |

### 2.1 计算资源、运行时间与成本

| 路径 | 计算要求 | 已记录时间/成本 |
|---|---|---|
| 核心重放（必需） | CPU-only；无需 GPU、模型权重或商业 API | 正式日志 `reproduce_main` 为 51.9 秒；评审建议预留 1–5 分钟；API 费用 0 |
| Streamlit Demo（可选） | CPU 即可；读取仓库示例与冻结证据 | 启动时间依本机依赖缓存而异；无按次 API 费用 |
| 四模型重新推理（可选） | 约 35 GB 数据；GPU 推荐但非核心复现条件 | 未形成跨硬件冻结 benchmark，不声明未经验证的时长或云成本 |

核心路径的目标是复核报告数字而不是重新训练模型；项目没有模型训练成本，也未调用商业
推理服务。完整推理的硬件、网络和存储成本由复现者环境决定。

## 3. 数据来源与冻结物

| 文件 | 内容 | 来源 |
|---|---|---|
| data/batch_calibration/records_all_v2.json | 895 条 × 四模型冻结预测 + 真值 | 数据组运行 + EQT 由 A 批量推理（seisbench OBS 数据集 Zenodo 10277799） |
| data/quality_manifest.csv | 895 条真实质量（SNR/断点/削波/缺道） | 本地波形计算（quality_manifest_builder.py） |
| data/manifest_phase.csv | 1306 个 (sample_id, phase) 评估单元 + 真值标签 | 相位级展开 + 元数据自查 |
| data/sta_lta_picks.csv | STA/LTA 传统基线触发 | 本地波形计算（带通 2-15Hz + 斜率修正） |
| data/eqt_predictions.json | EQT 推理原始输出 | run_eqt_batch.py |

五个数据文件、Platt 校准器和 model registry 均经 `reproduce_main` 第 1 步
使用完整 SHA-256 校验（LF 规范化口径）。配置文件自身 SHA-256 写入每条主结果、
bootstrap、复现报告与真实运行日志。

## 4. 配置与随机种子

| 项 | 值 | 位置 |
|---|---|---|
| 实验配置 | semifinal_v1.5.1（parent=semifinal_v1.5） | configs/semifinal_main.yaml |
| 冻结 profile | hydrophone_v2；正式复现禁止重新选优 | 同上 |
| 全局/留出集种子 | 42 | 同上 |
| holdout 划分 | chunk 分层 20%，seed 42 | manifest_phase.csv split 列 |
| 随机基线种子 | 0-99（100 个） | semifinal_main.yaml（脚本读取） |
| bootstrap 种子/次数 | 42 / 1000 次（cluster=60 台站） | semifinal_main.yaml（脚本读取） |
| 置信度校准 | Platt（main 拟合，holdout 验证）；geofon 不校准 | confidence_calibration.py |

## 5. 输出与核心数字（v1.5 预期）

| 输出 | 文件 |
|---|---|
| 基线对比 | results/baseline_results.csv |
| 主实验逐单元 | results/main_results.csv |
| Equal-Coverage Trust | results/equal_coverage_trust.csv |
| 风险分箱 | results/risk_bins.csv |
| 全方法对比 | results/method_comparison_v2.csv |
| bootstrap | results/bootstrap_ci.json |
| 主表/主图 | results/equal_coverage_table.csv、figures/*.png |
| failure 明细 | results/failure_raw.csv |
| 探索历史 | results/exploration_trajectory.jsonl（EXP01–15；缺失引用时失败） |
| 真实运行轨迹 | results/run_trajectory.jsonl（run_id/commit/config/seed/step/hash/干预披露） |
| 复现报告 | results/reproduction_report.json |

核心数字（v1.5.1 审计修复；数据、模型、阈值和判据未调优）：Trust 覆盖率天花板 **45.6%**——
预声明点位 50% **NOT_EVALUABLE**（不等覆盖比较不给出显著性结论）；
总体天花板补充比较：Trust 6.0% vs Voting 4.9%，Δ=+1.17pp，
95% CI [−1.09,+2.93] → INCONCLUSIVE；P 相自身天花板结果也为
INCONCLUSIVE（Δ=−1.33pp，CI [−4.62,+2.13]）；S 相在自身 45.45%
天花板处显著更差（Δ=+3.39pp，CI [+0.90,+5.96]）。P/S 补充点位不同，
不得直接比较两相效应。Voting@50% = 4.59%。

## 6. 重跑模型推理（可选，非复现必需）

- 数据层推理：`python -m src.data_layer.data_layer --trace N`（PhaseNet=geofon+ZNE，
  PickBlue=obs，OBSTransformer=obst2024；身份见 docs/model_registry.md）
- EQT 批量：`python -m src.experiments.run_eqt_batch`（断点续跑）
- 注意：模型推理输出随环境波动（±0.02s 量级），冻结预测为评估唯一口径

## 7. EXP17 复现（post-hoc failure-driven refinement，不覆盖 v1.5.1）

前置：先完成 §1 主链复现（EXP17 的 v1.5.1 对账以 `results/main_results.csv` 为参照）。
EXP17 使用环境变量 `OBS_EXP17_POLICY` 显式开启干预，默认关闭 = v1.5.1 冻结行为；
所有输出写入 `_exp17` 后缀新文件或 floorsweep 文件，**不覆盖任何 v1.5.1 产物**。

一键入口（串联 对账→A→配对 bootstrap→R1 核验→数字核验→只读终检）：

```bash
bash reproduce_exp17.sh
```

### 7.1 命令与输出

| 步骤 | 命令 | 输出 |
|---|---|---|
| 0. v1.5.1 对账 | runner 每步自动执行（打印"差异 N 个"）；要求 **N = 0** | 对照 `results/main_results.csv` |
| 1. EXP17-A | `python -m src.experiments.exp17_policy_refinement --intervention A` | `results/main_results_exp17_A.csv`、`results/exp17_summary_A.json` |
| 2. EXP17-B + A+B | `python -m src.experiments.exp17_policy_refinement --intervention B` | `results/exp17_summary_B.json`、`results/exp17_summary_AB.json` + 对应 CSV |
| 3. 配对 bootstrap（c2 唯一数字源） | `python -m src.experiments.paired_bootstrap --tag A` | `results/paired_bootstrap_A.json` |
| 4. EXP17-C floor sweep（留档） | `python -m src.experiments.exp17_policy_refinement --floor-sweep` | `results/floor_sweep.json` + `main_results_floorsweep_*.csv` |
| 5. R1 显式参数复现与核验 | `bash reproduce_exp17.sh` 读取配置中显式 P=0.34/S=0.51，重新运行 EXP17-A，再核验冻结 R1 verdict/identical/alternative 字段 | 重跑的 A 结果与 `results/exp17_robustness_R1.json`（冻结裁决记录） |

### 7.2 预期数字（核验标准，以数值对账为准）

| 产物 | 预期 |
|---|---|
| exp17_summary_A | ceiling **54.13%**；unsafe@50 **5.51%**；interception@50预算 **94.26%**；c1 ✓ c2 ✗（点估计 +0.92pp，单侧上界 +2.24pp）c3 ✓ c4 ✓；verdict=FAIL（即 c2 未过） |
| paired_bootstrap_A | 点估计 **+0.92pp**；单侧 95% 上界 **+2.24pp**；CI [−1.40,+2.58]；verdict=NOT_NON-INFERIOR；seed 42、60 台站 × 1000、n_valid 660 |
| exp17_summary_B | ceiling **81.62%**；c2 上界 **+4.87pp**；c3 FAIL（64.55%）；verdict=FAIL（负结果保留） |
| exp17_summary_AB | ceiling **90.12%**；c2 上界 **+4.0pp**；verdict=FAIL（留档） |
| floor_sweep | 0.70→45.64%；0.60→51.76%；0.55→53.22%（均劣于 A，不升级） |
| R1 | verdict=PASS（仅指显式参数路径与冻结 EXP17-A 一致；**不代表 EXP17 总体 Gate PASS**） |

统一结论（全链通过后引用）：
**Coverage recovery supported; safety non-inferiority inconclusive.**

### 7.3 注意事项

- 核验以数值对账为准，不比较文件字节（行尾规范跨平台）。
- 任何一步失败即停止并记负结果；禁止为达标调整 +2.0pp 界、bootstrap 口径或干预参数。
- B/A+B/floor sweep 为负结果与留档实验，复现后仍须保留原裁决（FAIL/弃用），不得改写为通过。

### 7.4 EXP17-A、paired bootstrap 与 R1 的可拆分命令

需要逐步审计时，可执行：

```bash
# 显式参数已冻结在 configs/semifinal_main.yaml：P=0.34s / S=0.51s
python3 -m src.experiments.exp17_policy_refinement --intervention A
python3 -m src.experiments.paired_bootstrap --tag A
python3 scripts/verify_exp17_evidence.py
```

预期：EXP17-A 输出 Coverage 54.13%、Unsafe 5.51%、Error Interception 94.26%；
`paired_bootstrap_A.json` 输出 ΔUnsafe +0.92pp、单侧 95% 上界 +2.24pp；终检显示
c1/c3/c4 通过、c2 `NOT ESTABLISHED`。R1 的 PASS 仅表示上述显式参数运行与冻结
EXP17-A 一致，不是 EXP17 safety Gate PASS。

## 8. 已知边界（如实声明）

- obs/obst2024 与评估集的训练重叠未审计（overlap UNKNOWN）——按 C 契约
  相关结论降级表述
- 冻结"PhaseNet"列实为 geofon（陆地模型），身份与证据见 model_registry.md
- 覆盖率天花板 45.6%（严格 FUSE 门槛后；596/1306 单元有安全自动路径，其余保守拒绝）
- main/holdout 结果存在幅度不稳定（3.82% vs 11.54%），样本量限制
