# 统一输出 Schema（A → B / C 接口契约）

> 冻结时间 2026-08-28（Gate 0，A+B 共同冻结）。
> B 的 Demo 只消费本契约字段，不得在前端重新计算科学结论；
> C 的定量结论必须能指回本契约对应的结果文件。

## 1. 单样本决策结果

`run_pipeline()` 返回 `ReliabilityResult`（dataclass，见 `src/trust_engine/schema.py:266`），
通过 `result.to_json()` 序列化。字段如下：

| 字段 | 类型 | 说明 |
|---|---|---|
| sample_id | str | 样本标识 |
| evidence_status | str | 证据完整性状态 |
| overall_risk_score | float | 总风险分（顶层没有 `risk_score` 字段） |
| overall_risk_level | str | LOW / MEDIUM / HIGH |
| phase_decisions | dict | key 为 "P"/"S"，值见 PhaseDecision |
| model_assessments | list | 每模型共识角色与风险 |
| evidence_breakdown | dict | 四证据分解（data/single/multi/physics） |
| reason_codes | list[str] | 决策原因码 |
| final_pair_status | str | P/S 成对状态 |
| config_version | str | 参数集版本（当前 calibrated_v1.0） |
| data_source | str | 数据来源标记 |

PhaseDecision 字段：`phase`、`action`（ACCEPT/FUSE/ABSTAIN）、`selected_model`、
`selected_time_s`、`fused_pick`、`rejected_models`、`risk_score`、`risk_level`、`reason_codes`。

**B 的决策展示取数**：`phase_decisions["P"].action` / `phase_decisions["S"].action`；
风险取 `overall_risk_score`；版本号展示 `config_version`。

## 2. 批量实验结果（Feedback 面板数据源）

批量指标（Coverage/Unsafe/Interception/Review）**不在单次 run_pipeline 返回中**，
来自 A 的批量结果 CSV（`results/` 目录），B 的面板从以下文件读取：

| 文件 | 内容 |
|---|---|
| results/baseline_results.csv | 五类 baseline × 5 个 coverage 点 × 指标 |
| results/main_results.csv | Trust 主实验逐样本决策与判定 |
| results/risk_bins.csv | 风险分箱错误率 |

## 3. 可调参数（Demo 交互契约）

B 的 Demo 可调参数全部来自 `TrustConfig`（`src/trust_engine/schema.py`），
每个滑块必须标注校准默认值与来源：

| 参数 | 默认值 | 来源 |
|---|---|---|
| automatic_risk_threshold | 10.0 | 风险校准曲线 n=891（≤10 分错误率 12.6%） |
| consensus_tolerance_p_s | 0.34 | 95% 分位 n=674 |
| consensus_tolerance_s_s | 0.51 | 95% 分位 n=455 |
| data_weight | 30.0 | 保守下限 |
| single_model_weight | 24.0 | 逻辑回归 n=895 |
| multi_model_weight | 37.0 | 逻辑回归 n=895 |
| physics_weight | 40.0 | 逻辑回归 n=895 |

用户修改参数后，Demo 必须显示"已偏离 calibrate_v1.0"及偏离清单；
批量反馈面板直接读取上述 CSV，不在前端重算。
