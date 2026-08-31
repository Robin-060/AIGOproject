# 复赛评估协议（冻结版 v1.1）

> 冻结时间 2026-08-28（Gate 0），对应 `configs/semifinal_main.yaml`（semifinal_v1.1）。
> 本协议是 A 的冻结交付物：所有 baseline、Trust 主实验、Demo 反馈面板必须使用同一套定义。
> v1.1 变更：评价单位按 C 契约 v1.2 改为**相位级 Primary**，成对判定降级为 Secondary。

## 1. 数据与评估子集

- 数据文件：`data/batch_calibration/records_all.json`（895 条，seisbench OBS 公开数据集的官方 P/S reference picks）
- 完整性指纹：sha256 `738e46aa...29d25699`，相位级清单见 `data/manifest_phase.csv`
- chunk 分布：201805 × 116、201806 × 288、201807 × 491；部署 XO，独立台站 60 个
- **主评估单位 `(sample_id, phase)`：N_eval = 1306**（P 真值 657 + S 真值 649）
- 真值缺失的相位：**已自查（2026-08-28）**——895 条全部有 source_id（事件目录），均为事件窗口、无噪声窗口；缺失真值 = 该相位在源数据集中无标注（trace_*_status 为空），按 C 契约 Unknown 不进入 primary，排除原因见 manifest 的 exclusion_reason
- label_source：seisbench OBS 数据集参考拾取（Zenodo 10277799），411 条真值与元数据 arrival_sample 100% 吻合；label_quality：manual / automatic 两档（见 manifest）
- 留出子集：按 chunk 分层 20%（seed 42，358 个单元）作稳健性交叉检查，不作主结论
- cluster 重采样单元：station（60 个）——统计检验时避免把同一台站的相关窗口当独立样本

## 2. 评价单位（v1.1 冻结）

- **Primary**：按 `(sample_id, phase)` 评估 P 和 S，分别报告样本数、错误数与指标；不得只给混合平均（C 契约 4.2）
- **Secondary**：成对判定（P+S 均 correct 且 final_pair_status 完整）仅用于"事件级完整性"声明，不作主指标
- **噪声窗口**：expected_event=False 时无拾取计 correct、虚假拾取计 wrong（待数据组确认噪声标签后启用）

## 3. 正确性判定协议（相位级）

| 情形 | 判定 |
|---|---|
| 预测存在且 \|p̂−p\| ≤ 容差 | correct |
| 预测存在但超差 | **wrong（不安全输出）** |
| 无预测（NO_PICK） | 不计自动输出；真值要求该相位时按错误计入拦截口径 |

容差：P = 0.5s，S = 1.0s（依据见 3.1）。

### 3.1 容差依据与敏感性证据（状态：C 已审阅，v1.5 五刀审核中接受校准方向）

依据两份证据（复现脚本 `src/experiments/tolerance_sensitivity.py`，
结果 `results/tolerance_sensitivity.json`，评估子集 411 条成对口径）：

1. **结论稳健性**：P 容差 ∈ {0.2, 0.3, 0.5, 1.0} × S 容差 ∈ {0.5, 1.0, 2.0}
   共 12 个档位上，Trust Layer 不安全输出率**严格低于** Single/MaxConf/Vote
   三个基线（冻结档 10.1% vs 34.4%/31.5%/35.4%）。容差选择不改变结论方向。
2. **残差双峰分布**：正确拾取误差中位数 P≈0.03–0.07s、S≈0.20–0.31s；
   错误拾取为 20–40s 量级的 gross error。0.5/1.0 档落在两峰之间的空档，
   对判定分类结果不敏感。
3. **文献惯例**：0.5/1.0 为相拾取评测常用容差档（出处由 C 依据
   Liu et al. 2025 等文献核实），待 A+C 共同签认后本项由"流程冻结"
   升级为"科学绑定"。

## 4. 五个核心指标（相位级口径，强制配对报告）

| 指标 | 定义 | 强制配对 |
|---|---|---|
| Coverage | 自动放行的相位单元数 ÷ N_eval（1306） | 必须与 Unsafe Output Rate 同报 |
| Unsafe Output Rate | 自动输出单元中 wrong 的比例（核心安全指标） | 必须与 Coverage 同报，**禁止单独报告** |
| Error Interception Rate | 被 ABSTAIN/Review 拦下的错误（含真值要求相位的 NO_PICK）÷ 全部错误 | 必须与 Review Burden 同报 |
| Review Burden | 进入人工复核的相位单元比例 | 必须与 Error Interception Rate 同报 |
| Selective Risk | 自动处理单元上的平均 0-1 loss | 必须按不同 Coverage 点报告 |

禁止表述："错误率 2.8%"。正确表述："Coverage=X% 时 Unsafe Output Rate=Y%"。

## 5. Equal-Coverage 公平性协议

- 比较点：Coverage = 50%、60%、70%、80%、90%（Primary point = 60%，其余为敏感性点）。
- 所有策略使用相同数据、相同真值、相同模型输出、相同正确性容差。
- 各策略通过自身旋钮对齐到目标覆盖率点后再比 Unsafe Output Rate。
- 不得通过提高拒绝比例单独宣称 Unsafe Rate 下降。
- **NOT_EVALUABLE 纪律（v1.5 起）**：某策略在预声明点位不可达（覆盖率天花板
  低于目标点）时，该点位输出 NOT_EVALUABLE / NOT_COMPARABLE_AT_TARGET，
  **不给出 Unsafe 数值与显著性结论**——不等覆盖比较的显著性结论视为口径错误。
  可达性以 max achievable coverage 判定（feasible 字段进入所有结果文件）；
  补充比较只允许在天花板点位进行，并明确标注"非声明点位"。
- 确证条件（C 契约 8.4）：cluster paired-bootstrap（station 重采样），
  ΔUnsafe 单侧 95% CI 上界 < 0；P、S 点估计分别报告，双相位声明需 Holm 校正。

## 6. 随机数与可复现性

- global_seed = 42；随机 baseline 用 0–99 共 100 个种子取均值 ± 标准差（报告 95% 区间）。
- 所有实验脚本的随机源必须显式记录种子。
- 历史数字规则：29.1%→2.8% 等历史阶段性结果必须由本配置 + reproduce 脚本重新生成后方可进入最终材料。

## 7. 软件与模型冻结

- seisbench 0.12.3、torch 2.13.0+cpu、obspy 1.5.0
- PhaseNet checkpoint `obs`、PickBlue base `phasenet`、OBSTransformer `obst2024`
- 模型预测覆盖率（895 条中有 P 预测的比例）：PhaseNet 125、PickBlue 747、OBSTransformer 825
