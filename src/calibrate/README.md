# Calibration 脚本说明

参数校准脚本。**最终采用的校准方法以 `docs/parameter_provenance.md` 溯源表为准。**

## 最终方法（决定当前参数值）

| 脚本 | 校准什么 | 方法 | 数据 |
|------|------|------|------|
| `weight_calibration_batch.py` | 证据权重 single/multi/physics | 逻辑回归 | n=895 |
| `recalibrate_large.py` | P/S 容差 + 物理边界 | 分位统计 | n=411~674 |
| `data_weight_regression.py` | data_weight 参考上界 | 扩充回归 | n=4475（含故障注入） |
| `internal_score_calibration.py` | 数据证据内部扣分 | 故障危害率反推 | 895×4 |
| `risk_calibration_curve.py`（在 experiments/） | 风险分界 low/medium | 风险-错误率曲线 | n=891 |

## 早期方法（已被取代，保留作过程记录）

| 脚本 | 被取代原因 |
|------|------|
| `param_calibration.py` | 放宽口径方法，后被风险校准曲线取代 |
| `identify_parameters.py` | 同上 |
| `tolerance_calibration.py` | n=14/36 小样本，后被 recalibrate_large 取代 |
| `weight_calibration.py` | n=64 小样本，后被 weight_calibration_batch 取代 |
| `data_weight_calibration.py` | 故障注入汇总统计，后被 data_weight_regression 取代 |
| `batch_calibration.py` | 批量推理工具（P3 在她机器上跑），产出已入库 |

## 数据依赖

- `data/batch_calibration/records_all.json` — 895 条真实标注样本（批量校准主数据）
- `docs/experiments/data_weight_calibration.json` — 故障注入汇总
