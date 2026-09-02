# Experiments：正式复现与探索工具

> 主结论以 `configs/semifinal_main.yaml`、`results/evidence_manifest.json` 和
> `docs/final_report.md` 为准。早期脚本只作历史方法参照，不能单独作为最终数字源。

## 1. 最短复现入口

```bash
bash reproduce_core.sh
bash reproduce_exp17.sh
python3 scripts/verify_exp17_evidence.py
python3 -m pytest -q
```

- `reproduce_core.sh`：冻结输入 hash → baselines → v1.5.1 主实验 → Equal-Coverage →
  paired/cluster bootstrap → EXP16 Review Efficiency → 主图与运行轨迹。
- `reproduce_exp17.sh`：v1.5.1 逐单元对账 → EXP17-A/B/A+B/C → c1–c4 →
  `paired_bootstrap_A.json` → R1 参数来源核验。
- `verify_exp17_evidence.py`：只读核对冻结数字、裁决和 evidence manifest。

完整环境、命令和预期输出见 `docs/reproduction.md`。

## 2. 主实验脚本

| 模块 | 作用 | 主要产物 |
|---|---|---|
| `reproduce_main.py` | 核心复现编排器 | `reproduction_report.json`、`run_trajectory.jsonl` |
| `run_baselines.py` | 八类参照系 | `baseline_results.csv` |
| `run_main_experiment.py` | v1.5.1 冻结主实验 | `main_results.csv` |
| `bootstrap_analysis.py` | Equal-Coverage station-cluster bootstrap | `bootstrap_ci.json` |
| `review_budget_curve.py` | EXP16 复核预算曲线 | `review_budget_curve*.csv/json` |
| `review_budget_ci.py` | EXP16 cluster bootstrap CI | `review_budget_ci.json` |
| `policy_diagnosis.py` | 703 个未自动输出的失败分解 | `policy_diagnosis.csv/json` |
| `exp17_policy_refinement.py` | EXP17-A/B/A+B 与 floor sweep | `exp17_summary_*.json`、`main_results_exp17_*.csv` |
| `paired_bootstrap.py` | EXP17 c2 唯一统计数字源 | `paired_bootstrap_A.json` |
| `run_trajectory.py` | 真实执行轨迹与输出 hash | `run_trajectory.jsonl` |

## 3. 补充实验

| 脚本 | 定位 |
|---|---|
| `seisbench_noise.py` / `noise_robustness.py` | 早期 20 条噪声实验，仅作补充边界证据 |
| `stalta_baseline.py` | 传统 STA/LTA 参照系，不作为新证据 |
| `run_eqt_batch.py` | 第四套 EQTransformer 冻结预测生成，断点续跑 |
| `end_to_end_verification.py` | 小样本原始波形→模型→Trust 的执行链核对 |

## 4. 输出纪律

- v1.5.1 产物与 EXP17 产物分轨命名；EXP17 不覆盖 `main_results.csv` 或 `results/v151_archive/`。
- Coverage 与 Unsafe 成对报告；Error Interception 与 Review Burden 成对报告。
- c2 必须引用 `paired_bootstrap_A.json`：点估计 +0.92pp，单侧 95% 上界 +2.24pp，
  因高于 +2.0pp 界而 `NOT ESTABLISHED`。
- `R1 PASS` 只表示显式参数路径复现一致，不是 EXP17 safety Gate PASS。
- 不以文件字节相同代替数值对账；跨平台行尾差异不应改写科学裁决。
