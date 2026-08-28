# 复赛评估协议（冻结版）

> 冻结时间 2026-08-28（Gate 0），对应 `configs/semifinal_main.yaml`（semifinal_v1.0）。
> 本协议是 A 的冻结交付物：所有 baseline、Trust 主实验、Demo 反馈面板必须使用同一套定义。

## 1. 数据与评估子集

- 数据文件：`data/batch_calibration/records_all.json`（895 条，seisbench OBS 公开数据集的官方 P/S reference picks）
- 完整性指纹：sha256 `738e46aa...29d25699`，清单见 `data/manifest.csv`
- chunk 分布：201805 × 116、201806 × 288、201807 × 491
- **主评估子集 `eval_full_truth_pairs`：P 与 S 真值均非空的 411 条**。基线对比、Equal-Coverage 主实验均在此子集上报告。
- 留出子集 `holdout_20pct`（按 chunk 分层 20%，seed 42）仅作稳健性交叉检查，不作主结论。

## 2. 正确性判定协议

| 情形 | 判定 |
|---|---|
| P、S 均存在且 \|P̂−P\| ≤ 0.5s 且 \|Ŝ−S\| ≤ 1.0s | correct |
| P 或 S 任一缺失 | reject（不计入错误率，计入覆盖率分母） |
| P、S 均存在但任一超差 | **wrong（不安全输出）** |

容差 P=0.5s / S=1.0s 延续自历史基线协议（real_baseline_final.py），本次冻结为 semifinal 标准。

## 3. 五个核心指标（强制配对报告）

| 指标 | 定义 | 强制配对 |
|---|---|---|
| Coverage | 自动进入 ACCEPT/FUSE 等无需人工复核路径的样本比例 | 必须与 Unsafe Output Rate 同报 |
| Unsafe Output Rate | 自动输出样本中错误结果的比例（核心安全指标） | 必须与 Coverage 同报，**禁止单独报告** |
| Error Interception Rate | 所有错误预测中被拦截进入 ABSTAIN/Review 的比例 | 必须与 Review Burden 同报 |
| Review Burden | 进入人工复核的样本比例/数量 | 必须与 Error Interception Rate 同报 |
| Selective Risk | 系统自动处理样本上的真实错误风险 | 必须按不同 Coverage 点报告 |

禁止表述："错误率 2.8%"。正确表述："Coverage=X% 时 Unsafe Output Rate=Y%"。

## 4. Equal-Coverage 公平性协议

- 比较点：Coverage = 50%、60%、70%、80%、90%。
- 所有策略使用相同数据、相同真值、相同模型输出、相同正确性容差。
- 各策略通过自身旋钮对齐到目标覆盖率点后再比 Unsafe Output Rate。
- 不得通过提高拒绝比例单独宣称 Unsafe Rate 下降。

## 5. 随机数与可复现性

- global_seed = 42；随机 baseline 用 0–99 共 100 个种子取均值 ± 标准差。
- 所有实验脚本的随机源（numpy/pandas 抽样）必须显式记录种子。
- 历史数字规则：29.1%→2.8% 等历史阶段性结果必须由本配置 + reproduce 脚本重新生成后方可进入最终材料。

## 6. 软件与模型冻结

- seisbench 0.12.3、torch 2.13.0+cpu、obspy 1.5.0
- PhaseNet checkpoint `obs`、PickBlue base `phasenet`、OBSTransformer `obst2024`
- 模型预测覆盖率（895 条中有 P 预测的比例）：PhaseNet 125、PickBlue 747、OBSTransformer 825
