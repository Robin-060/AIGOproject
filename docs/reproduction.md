# 复现说明（Reproduction Guide）

> 对应复赛交付"README 与复现说明"及 C 契约复现要求
> （运行入口、依赖安装、配置方法、随机种子、raw results 可检查）。

## 1. 一键入口

```bash
pip install -r requirements.txt          # 依赖安装
bash smoke_test.sh                       # 环境自检: 依赖 + 冻结数据 + 52 个测试
bash reproduce_core.sh                   # 一键复现核心数字与三张主图
# 等价于: python -m src.experiments.reproduce_main
```

复现范围：冻结数据校验 → 基线对比 → 主实验（冻结档案 hydrophone_v2，直接读取、不重新选优）→ 全方法对比 → bootstrap → 主图 → 探索轨迹。
**全程使用冻结预测，不运行模型推理**（预测是冻结物；重跑模型的入口见第 6 节）。
两个 shell 脚本兼容 Linux 与 Windows（解释器自动回退 python3 → python）。

## 2. 环境（版本已冻结）

| 包 | 版本 |
|---|---|
| seisbench | 0.12.3 |
| torch | 2.13.0+cpu |
| obspy | 1.5.0 |
| numpy / scipy / pandas | 见 requirements.txt |

## 3. 数据来源与冻结物

| 文件 | 内容 | 来源 |
|---|---|---|
| data/batch_calibration/records_all_v2.json | 895 条 × 四模型冻结预测 + 真值 | 数据组运行 + EQT 由 A 批量推理（seisbench OBS 数据集 Zenodo 10277799） |
| data/quality_manifest.csv | 895 条真实质量（SNR/断点/削波/缺道） | 本地波形计算（quality_manifest_builder.py） |
| data/manifest_phase.csv | 1306 个 (sample_id, phase) 评估单元 + 真值标签 | 相位级展开 + 元数据自查 |
| data/sta_lta_picks.csv | STA/LTA 传统基线触发 | 本地波形计算（带通 2-15Hz + 斜率修正） |
| data/eqt_predictions.json | EQT 推理原始输出 | run_eqt_batch.py |

全部冻结物经 `reproduce_main` 第 1 步 sha256 校验（LF 规范化口径，跨平台稳定）。

## 4. 配置与随机种子

| 项 | 值 | 位置 |
|---|---|---|
| 实验配置 | semifinal_v1.5 | configs/semifinal_main.yaml |
| 全局/留出集种子 | 42 | 同上 |
| holdout 划分 | chunk 分层 20%，seed 42 | manifest_phase.csv split 列 |
| 随机基线种子 | 0-99（100 个） | random_baseline.py |
| bootstrap 种子/次数 | 42 / 1000 次（cluster=60 台站） | bootstrap_analysis.py |
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
| 探索轨迹 | results/exploration_trajectory.jsonl（EXP01–14，由 generate_trajectory.py 生成，产物引用缺失时告警） |
| 复现报告 | results/reproduction_report.json |

核心数字（v1.5 严格 FUSE 门槛后）：Trust 覆盖率天花板 **45.6%**——
预声明点位 50% **NOT_EVALUABLE**（不等覆盖比较不给出显著性结论）；
天花板点位补充比较：Trust 6.0% vs Voting 4.9%，Δ=+1.2pp，
95% CI 含 0 → INCONCLUSIVE（统计并列）；P 相点估计反超（−1.3pp）、
S 相落后（+3.4pp）。Voting@50% = 4.59%。

## 6. 重跑模型推理（可选，非复现必需）

- 数据层推理：`python -m src.data_layer.data_layer --trace N`（PhaseNet=geofon+ZNE，
  PickBlue=obs，OBSTransformer=obst2024；身份见 docs/model_registry.md）
- EQT 批量：`python -m src.experiments.run_eqt_batch`（断点续跑）
- 注意：模型推理输出随环境波动（±0.02s 量级），冻结预测为评估唯一口径

## 7. 已知边界（如实声明）

- obs/obst2024 与评估集的训练重叠未审计（overlap UNKNOWN）——按 C 契约
  相关结论降级表述
- 冻结"PhaseNet"列实为 geofon（陆地模型），身份与证据见 model_registry.md
- 覆盖率天花板 45.6%（严格 FUSE 门槛后；596/1306 单元有安全自动路径，其余保守拒绝）
- main/holdout 结果存在幅度不稳定（3.82% vs 11.54%），样本量限制
