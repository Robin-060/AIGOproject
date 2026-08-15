# Legacy 校准结果

此目录存放**已被取代的早期校准结果**，仅作过程记录，不用于最终结论。

## 文件说明

| 文件 | 被取代原因 | 替代者 |
|------|------|------|
| `param_identification.json` | 放宽口径网格扫描（实验性方法，样本 n=64） | `risk_calibration_curve.png`（风险校准曲线，n=891） |
| `weight_calibration.json` | 小样本逻辑回归（n=64） | `weight_calibration_batch.json`（n=895） |

## 原则

- 最终参数一律以 `docs/parameter_provenance.md` 溯源表为准。
- 早期小样本结果与新的大样本结果冲突时，以新结果为准。
- 保留这些文件是为了透明记录校准方法的演进过程。
