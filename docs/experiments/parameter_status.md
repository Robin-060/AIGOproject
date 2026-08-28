# 参数现状对照表（A → C 交接件）

> 目的：解决 C 契约 v1.2 表格25 引用的参数与仓库当前值不一致的问题。
> 仓库当前参数集：calibrated_v1.0（src/trust_engine/schema.py）。
> 本表状态：候选值清单；按 C 契约 6.2 节，最终以 validation 选择程序确认后绑定。

## 对照表

| 参数 | C 契约 v1.2 引用值 | 仓库当前值 (calibrated_v1.0) | 来源 | 处置建议 |
|---|---|---|---|---|
| 模型共识容差 P | 0.30s (heuristic_v0.1) | **0.34s** | 双模型正确差值 95% 分位，n=674 | C 更新为候选值 0.34 |
| 模型共识容差 S | 0.50s (heuristic_v0.1) | **0.51s** | 双模型正确差值 95% 分位，n=455 | C 更新为候选值 0.51 |
| 严重分歧阈值 P/S | 1.00s / 2.00s | **参数已删除** | 死参数，已从 schema 移除 | C 删除此行 |
| P/S 物理间隔 min | 0.1s | **5.7s** | S-P 时差 2.5% 分位，n=411 | C 更新为候选值 5.7 |
| P/S 物理间隔 max | 60.0s | **33.42s** | S-P 时差 97.5% 分位，n=411 | C 更新为候选值 33.42 |
| risk level 分段 | 0-30 LOW / 31-60 MEDIUM / 61-100 HIGH | **一致** ✓ | schema risk_level() | 无需修改 |
| 正确性容差 P/S | 尚未绑定 | 0.5s / 1.0s（流程冻结） | 历史协议 + 敏感性证据（12 档扫描结论稳定，results/tolerance_sensitivity.json） | 待 C 签认（冲突 1 已备齐证据） |
| data_weight | — | 30.0 | 保守下限 | 已确认 |
| single_model_weight | — | 24.0 | 逻辑回归，n=895 | 已确认 |
| multi_model_weight | — | 37.0 | 逻辑回归，n=895 | 已确认 |
| physics_weight | — | 40.0 | 逻辑回归，n=895 | 已确认 |
| automatic_risk_threshold | — | 10.0 | 风险校准曲线 n=891（≤10 分错误率 12.6%） | 已确认 |

## 待 C 契约更新的三处

1. 表格25 共识容差：0.30/0.50 → **0.34/0.51（候选值，calibration 来源 n=674/455）**
2. 表格25 严重分歧阈值：**整行删除**（参数已不存在于 schema）
3. 表格25 物理间隔：0.1/60.0 → **5.7/33.42（候选值，n=411 分位）**

## 深层说明（对应 C 契约 6.2 阈值冻结程序）

calibrated_v1.0 的全部参数是在历史全量 895 条上校准的。按 C 契约的
validation/test 隔离要求，这些参数在本表中一律标为"候选值"：
- 建立 validation/test split 后（A 待办项），在 validation 上运行选择程序
  （如目标 Coverage 下最小化 Unsafe Output Rate）
- validation 确认后的参数升级为绑定值，config_version 升版（如
  calibrated_v2.0 或 semifinal_selected_v1.0）
- locked test 只运行一次，不回调
