# Experiments

实验脚本说明。所有定量结论均基于真实模型推理 + 真实标注数据。

## 正式实验（进报告）

| 脚本 | 说明 | 数据 |
|------|------|------|
| `seisbench_noise.py` | 噪声鲁棒性实验：L0-L3 四档噪声 × 三模型 | SeisBench OBS test split |
| `noise_robustness.py` | 噪声实验汇总与评估指标 | 同上 |
| `stalta_baseline.py` | 传统 STA/LTA 基线 | SeisBench OBS |
| `real_ablation.py` | 消融实验（真实预测） | 895 条批量记录 |
| `real_baseline_ablation.py` | 基线对比 + 消融（真实预测） | 同上 |
| `cpu_benchmark.py` | CPU 推理耗时基准 | SeisBench OBS |

## 辅助脚本

| 脚本 | 说明 |
|------|------|
| `__init__.py` | 包标记 |

## 运行方式

```bash
python -m src.experiments.seisbench_noise       # 需本地 OBS chunk 数据
python -m src.experiments.real_ablation         # 需 data/batch_calibration/records_all.json
```

## 说明

- 早期使用 `simulate_predictions()` 假预测的脚本已删除（被真实数据版本取代）。
- 所有报告数字以 `docs/experiments/` 下的 JSON/CSV 为准，脚本可复现。
