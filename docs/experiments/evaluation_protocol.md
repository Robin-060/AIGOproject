# 复赛评估协议（冻结版 v1.5.1-bugfix）

> 初次冻结 2026-08-28（Gate 0）；当前审计修复版对应
> `configs/semifinal_main.yaml`（semifinal_v1.5.1，parent=semifinal_v1.5）。
> 本协议是 A 的冻结交付物：所有 baseline、Trust 主实验、Demo 反馈面板必须使用同一套定义。
> v1.1 变更：评价单位按 C 契约 v1.2 改为**相位级 Primary**，成对判定降级为 Secondary。

## 1. 数据与评估子集

- 数据文件：`data/batch_calibration/records_all_v2.json`（895 条，四模型冻结预测与官方 P/S reference picks）
- 完整性指纹：完整 SHA-256 由冻结配置的 `frozen_artifacts` 声明并由
  `reproduce_main` 强制验证；相位级清单见 `data/manifest_phase.csv`
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
| Selective Risk | 自动处理单元上的平均 0-1 loss（wrong=1, correct=0）；本口径下 auto 集内仅 correct/wrong 两类，故数值等同 Unsafe Output Rate，落盘为 equal_coverage_trust.csv 的 selective_risk_pct 列 | 必须按不同 Coverage 点报告 |

禁止表述："错误率 2.8%"。正确表述："Coverage=X% 时 Unsafe Output Rate=Y%"。

## 5. Equal-Coverage 公平性协议

- 预声明点：Coverage = 50%；60%、70%、80%、90% 为覆盖率敏感性点。
- 所有策略使用相同数据、相同真值、相同模型输出、相同正确性容差。
- 各策略通过自身旋钮对齐到目标覆盖率点后再比 Unsafe Output Rate。
- 不得通过提高拒绝比例单独宣称 Unsafe Rate 下降。
- **NOT_EVALUABLE 纪律（v1.5 起）**：某策略在预声明点位不可达（覆盖率天花板
  低于目标点）时，该点位输出 NOT_EVALUABLE / NOT_COMPARABLE_AT_TARGET，
  **不给出 Unsafe 数值与显著性结论**——不等覆盖比较的显著性结论视为口径错误。
  可达性以 max achievable coverage 判定（feasible 字段进入所有结果文件）；
  补充比较只允许在天花板点位进行，并明确标注"非声明点位"。
- **冻结档案纪律（v1.5.1 起）**：正式复现必须直接读取
  `configs/semifinal_main.yaml` 的 `experiment.frozen_profile`（hydrophone_v2），
  **禁止在复现中重新比较候选档案并按结果选优**（结果驱动选择）。候选选择程序
  （EXP06 预注册比较）降级为历史记录，仅可通过
  `python -m src.experiments.run_main_experiment --profile-selection` 显式重放，
  其输出只写 `results/profile_selection_exp06.csv`，不覆盖正式产出。
  复现入口同时校验 TrustConfig 参数集与 YAML `parameter_set` 一致，不一致即拒绝运行。
- **EXP17 最终裁决协议（2026-09-01，版本修订留痕）**：v1.5.1 之后的 policy
  改动实验属于 post-hoc failure-driven refinement。数据、模型、评价单元与
  truth-blind 边界保持冻结；三个干预单变量、
  顺序 A→B→C、逐干预验收。最终裁决冻结的四判据为：c1 真实 selected-pick
  Coverage ≥50%；c2 ΔUnsafe = Unsafe@50 − Voting@50 冻结锚点 4.59%，配对
  station-cluster bootstrap 单侧 95% 上界 < +2.0pp（点估计 ≤+1.0pp 仅为内部
  绿灯）；c3 Review Budget 截获@50%预算 ≥ v1.5.1 冻结值 83.6%；c4 风险分箱
  （可靠箱 n≥10）错误率严格单调不减。失败即回退并记负结果，禁止按结果微调
  干预参数。初版判据与 c2 后续修订均记录于
  `docs/experiments/exp17_preregistration.md`；历史表述中的"vs v1.5.1 天花板点
  6.04%"为早期草案锚点，已被最终裁决的 Voting@50 锚点取代，因此当前协议不作
  严格预注册确证表述。
- 确证条件（C 契约 8.4）：cluster paired-bootstrap（station 重采样），
  ΔUnsafe 单侧 95% CI 上界 < 0；P、S 点估计分别报告，双相位声明需 Holm 校正。

## 6. 随机数与可复现性

- **holdout 口径说明（2026-09-01 澄清，同一 split 不换集）**：冻结配置写
  "holdout_20pct 358 单元"，评估报告写 holdout 260 单元——两者一致，统计
  口径不同：358 = `data/manifest_phase.csv` 全部 1790 行的 20%（main 1432 +
  holdout 358）；260 = 其中 N_eval=1306 个 Primary 相位单元的 holdout 部分
  （main 1046 + holdout 260），其余 484 行为非 Primary 行（见
  primary_inclusion/exclusion_reason 列）。正式评估一律使用 Primary 口径 260。

- global_seed = 42；随机 baseline 用 0–99 共 100 个种子，报告均值、标准差
  和跨 seed 的 2.5%/97.5% percentile interval，不将其误称为均值置信区间。
- 所有实验脚本的随机源必须显式记录种子。
- 历史数字规则：29.1%→2.8% 等历史阶段性结果必须由本配置 + reproduce 脚本重新生成后方可进入最终材料。

## 7. 软件与模型冻结

- 核心复现基于冻结预测，不加载模型；完整推理参考环境为 seisbench 0.12.3、
  torch 2.13.0+cpu、obspy 1.5.0
- 四个冻结 checkpoint：PhaseNet `geofon`、PickBlue/PhaseNet `obs`、
  OBSTransformer `obst2024`、EQTransformer `obs`；身份见 `model_registry.md`
- 预测覆盖 count（P/S）：PhaseNet 125/15、PickBlue 747/827、
  OBSTransformer 825/881、EQTransformer 753/794
- 正式 profile 固定为 `hydrophone_v2`；历史候选比较属于 EXP06，
  `reproduce_core` 不得重新按结果选 profile
