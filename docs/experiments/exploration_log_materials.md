# 探索日志素材汇总（A → C 交接件）

> 用途：C 撰写 exploration_log.md 的原材料。每条按
> Hypothesis → Experiment → Observation → Revision → Result → Limitation 组织，
> 所有数字有出处文件，C 的定量表述可直接引用。
> 覆盖：项目全程（含被推翻的早期方法），14 个实验条目 + 负结果清单 + 数字速查表。

## 一、实验时间线总表

| 编号 | 事件 | 类型 | 结果 |
|---|---|---|---|
| EXP01 | 小样本校准 → 895 条重校准 | 修正 | 容差 0.578→0.34 / 0.340→0.51 |
| EXP02 | 故障注入罚分校准 → 自然重校准（DS4） | 修正 | 注入罚分被证高估 5-20 倍 |
| EXP03 | 风险曲线非单调 → 证据权重调整 | 修正 | 风险分箱单调 |
| EXP04 | 假质量报告发现 → 真实质量清单重建 | 异常→修正 | 895 条真实 SNR/断点/削波/缺道 |
| EXP05 | 模型身份错位（geofon 指纹破案） | 异常→修正 | 三列真实身份锁定，代码对齐 |
| EXP06 | "PickBlue 需 4 分量"假设证伪 | 异常→修正 | v2 档案（main 9.2%→5.0%） |
| EXP07 | 主实验 v1：DS1 部分成立 + bootstrap | 正/负结果 | S 相显著落后，天花板 46.7% |
| EXP08 | EQT 第四模型（C 批准，不替换） | 正向发现 | 天花板 46.7→54.2% |
| EXP09 | STA/LTA 第五证据 12 组合校准 | **负结果（淘汰）** | X=0 胜出，弱相关 46.7% vs 60.9% |
| EXP10 | DS4 自然罚分重校准 | 正向发现 | v1.4：S 相从显著落后→统计并列 |
| EXP11 | DS3 判定：分歧与错误关联 | **负结果** | P 不显著/S rho=0.09；发现"完全一致也会错"（11.3%/8.0%） |
| EXP12 | DS5 泛化验证（_BLANCO 跨域） | **负结果→修正** | 跨域同降（21.5%）→ ID-only 域门（coverage 54.5→19.5%） |
| EXP13 | C 五刀落地（v1.5） | 修正 | 校准入证据层 + 分歧单向化 + FUSE 门槛 + 准入制度 |
| EXP14 | FUSE 门绕过审计 + NOT_EVALUABLE 纪律 | **负结果→修正** | 堵 4.5 步绕过后天花板 54.2→45.6%；50% 点 NOT_EVALUABLE；DS5 域门新标准未成立 |

## 二、逐条素材卡

### EXP01 小样本校准 → 全量重校准
- **H**：用少量样本（n=14-80）校准容差足够
- **E**：小样本分位校准容差（P 0.578s / S 0.340s）
- **O**：被质疑样本不足，结论可能不稳
- **R**：改用 895 条全量重新校准 → P 0.34 / S 0.51（95% 分位，n=674/455）
- **Limitation**：历史小样本参数保留于 docs/experiments/legacy/（修正证据链）

### EXP02 故障注入 → 自然校准
- **H**：人为注入故障可校准数据罚分
- **E**：895 条注入故障实验 → 错误率 28.6/35.8/32.8/91.3% → 罚分 8.6/10.7/9.9/27.4
- **O**：被质疑"故障是人为增加的，不是真实的"；代码注明 caveat
- **R**：DS4 用真实质量清单计算自然危害率 → 发现注入值高估 5-20 倍
  （强噪声注入 91.3% vs 自然 4.5%）；validation 程序通过后 v1.4 切换自然罚分
- **出处**：results/ds4_natural_hazard.json、results/ds4_penalty_grid.csv

### EXP03 风险曲线非单调 → 权重调整
- **H**：风险分越高，错误率越高
- **O**：早期风险校准曲线非单调
- **R**：调整证据权重（逻辑回归 n=895 校准 single/multi/physics 权重）
- **Result**：v1.4 风险分箱严格单调（4.18→10.38→28.57%，n=502/183/21）

### EXP04 假质量报告 → 真实质量清单
- **H**：历史基线实验的质量报告可信
- **O**：审计发现基线脚本硬编码 QualityReport(snr=20, 无缺道/断点/削波)
  ——数据证据层从未在真实质量上运行
- **R**：下载 OBS 数据集 3 chunks（2.7GB）→ 用数据组同款函数重建 895 条真实质量
- **Result**：真实画像：SNR 中位数 11dB、55.2% 有断点、100% 有削波、13.6% 缺 E
- **出处**：data/quality_manifest.csv、src/data_layer/quality_manifest_builder.py

### EXP05 模型身份错位（geofon 破案）
- **H**：冻结"PhaseNet"列是 obs 权重
- **E**：本地复现对不上（P 差 0.18s、S 差 0.30s、置信度 0.912 vs 0.795）
- **O**：源码证明 PickBlue(base="phasenet") ≡ PhaseNet obs（别名工厂）；
  若两列不同，"PhaseNet"列必不是 obs
- **R**：指纹匹配锁定 geofon（8 样本 P 8/8、置信度 8/8 精确吻合）；
  model_registry.md 记录真实身份；data_layer.py 改为 geofon + ZNE 通道
  （指纹复核完全一致）
- **Limitation**：数据组生成环境版本未冻结，无法追溯执行差异（如实记录）

### EXP06 "PickBlue 需 4 分量"假设证伪
- **H**：PickBlue 档案要求 Z/N/E/H 四通道，缺 E 即排除
- **O**：冻结数据 94% 缺 E 记录有 PickBlue 预测（数据组从未执行该限制）；
  实测缺 E 时 PickBlue 命中 91-93%，不受影响；反而 OBSTransformer 缺 E 时
  S 命中 74%→58%（真正降级的是它）
- **R**：v2 选择程序（预注册准则：main 50% 点 Unsafe 低者胜）：
  hydrophone_v2 档案（Z,H 必需）胜出 → main 9.2%→5.0%
- **Result**：缺 E 记录决策翻盘：ROUTE 独苗 180→2，FUSE 0→120，ABSTAIN 58

### EXP07 主实验 v1：DS1 部分成立 + 统计框架
- **E**：相位级 Equal-Coverage（1306 单元、五点位）+ cluster paired-bootstrap
  （60 台站 × 1000 次，seed 42）
- **O**：DS1 部分成立——优于 5/7 参照系，不优于 Voting；S 相显著落后
  （CI [+0.1, +5.3] 全正）；覆盖率天花板 46.7%；拦截率 94.1%
- **R**：定位三个根因：档案误杀 PickBlue（→EXP06）、OBSTransformer S 弱
  （72% 容差内）、风险排序被数据罚分稀释（→EXP10）
- **Limitation**：main/holdout 不稳定（5.0% vs 17.0%）如实记录

### EXP08 EQT 第四模型
- **H**：模型池缺一个真正的强 OBS 模型（geofon 是凑数的陆地模型）
- **E**：EQT 探针（50 条）：S 容差内 100% vs OBSTransformer 82%
- **R**：C 批准新增（锁死条件：不替换）；EQT 跑 895 条 → 四模型冻结 v2
- **Result**：天花板 46.7→54.2%（+47 单元恢复输出）；Trust 反超全部单模型

### EXP09 STA/LTA 第五证据（负结果，淘汰）
- **H**：STA/LTA 触发支持可作为第五证据（独立机制交叉验证）
- **E**：12 组合（W×X）预注册校准
- **O**：全部组合 4.2% 与基线相同；诊断：正确拾取 46.7% 无支持 vs 错误 60.9%
  ——弱相关 + 高误伤，排序边界不动
- **R**：按预注册准则 X=0 胜出，证据淘汰；STA/LTA 保留 Traditional 参照系用途
- **价值**：预注册的失败条款被执行（设计文档硬约束第 4 条），负结果完整留痕

### EXP10 DS4 自然罚分重校准
- **H**：注入校准罚分在自然数据上仍有效
- **O**：DS4 判定不成立——自然危害率远低于注入值（强噪声 4.5% vs 91.3%、
  缺道 5.0% vs 28.6%、削波 0% vs 35.8%）；低信噪样本错误率（4.5%）
  甚至低于无故障基线（6.6%）
- **R**：自然罚分候选（B_natural）validation 双线胜
  （main 4.2→3.82%，holdout 12.31→11.54%，方向一致）→ 冻结 v1.4
- **Result**：50% 点 Unsafe 5.8→5.4%；**bootstrap S 相从显著落后转为统计并列**

### EXP11 DS3 判定（分歧与错误关联，负结果）
- **H**：模型 P/S 拾取分歧与真实错误风险存在可重复关联
- **E**：分相位分带错误率 + Spearman（n=635 P / 644 S，≥2 模型有拾取）
- **O**：P 相关系不显著（rho=0.06, p=0.13）且呈 U 形；S 极弱（rho=0.09）
  且非单调。**关键发现：完全一致带（0-0.05s）错误率 11.3%/8.0%，
  高于中分歧带（4.6%/2.6%）——模型会抱团一起错**
- **R**：v1.5 将分歧改为单向风险证据（粗分三级）+ FUSE 校准置信度门槛
- **出处**：results/ds3_disagreement.json

### EXP12 DS5 泛化验证（_BLANCO 跨域，负结果→修正）
- **H**：跨域时 Trust 能通过提高 ABSTAIN 实现安全降级（DS5 原条款）
- **E**：chunk 000000 的 _BLANCO 台阵（200 条，四模型推理，同协议评估）
- **O**：原条款判定不成立——跨域后 Trust 与 Voting 同降（21.5%），
  天花板 54.5% 与域内 54.2% 相同（未主动降级）
- **R**：C 第三刀收缩——ID-only 域熟悉度门（马氏距离，XO 建正常范围）。
  **DS5 新成功标准**：coverage 主动下降 + retained unsafe 降低
  （不要求准确率恢复）
- **Result**：v1.4 引擎下新标准成立——BLANCO coverage 54.5%→19.5%，retained unsafe
  23.9%→21.8%；**边界**：retained 21.8% 仍高于域内 5.4%，门是必要护栏非完整解药
  ⚠️ v1.5 严格门槛引擎下重跑 → 新标准未成立（见 EXP14 / 负结果清单 11）
- **定稿（2026-08-31 团队确认）**：_BLANCO 台阵（200 条，与主域同数据集、不同台阵）
  即为正式的第二数据域交付；不再扩展第三域，9/1 止损条款以本定稿解除。
  报告措辞统一为"跨台阵第二数据域"，如实标注与主域同源数据集
- **出处**：results/domain_gate.json、results/generalization_blanco.json

### EXP13 C 五刀落地（v1.5）
- **H**：C 建议——校准置信度、分歧降级、域门收缩、准入制度、DS 口径调整
- **R**：① Platt 校准入证据层（PickBlue/OBSTransformer/EQT；geofon 样本
  不足保留 raw）② 分歧粗分三级 + FUSE 门槛 ③ ID-only 域门 ④ Evidence
  Admission Rule 冻结（STA/LTA 结案为被拒首例）
- **Result**：初版主结果持平（5.5%@50，与 Voting 统计并列），holdout 稳定性改善
  （11.5→10.0%）；置信度获得统计语义（校准后 0.78≈78% 正确）
  ⚠️ 该 5.5%@50 数字后来被 EXP14 取代——当时存在第 4.5 步绕过，50% 点位实为不可达
- **出处**：results/calibration/、docs/experiments/evidence_admission_rule.md、
  docs/experiments/ds_findings_v15.md

### EXP14 FUSE 门绕过审计 + NOT_EVALUABLE 纪律（v1.5 收口）
- **H**：v1.5 的校准 FUSE 门槛对所有 FUSE 路径生效
- **E**：policy_router 路径审计 → 发现第 4.5 步"多模型共识但无显式融合候选"分支
  直接走单模型主路，未检查 FUSION_CALIBRATED_CONFIDENCE_BELOW_FLOOR——
  低置信共识绕过 FUSE 门
- **O**：堵住后 Trust 最大可达覆盖率 54.2%→45.64%（596/1306 有有效输出），
  预声明 50% 点位不可达；原 5.5%@50 数字作废
- **R**：Equal-Coverage 纪律升级——不可达预声明点位输出 NOT_EVALUABLE /
  NOT_COMPARABLE_AT_TARGET，不填 Unsafe、不做显著性结论；
  bootstrap 另出天花板补充比较（非声明点位，明确标注"补充"）
- **Result**：ALL 天花板补充 Δ=+1.17pp（Trust 6.04 vs Voting 4.87），
  CI [-1.42, +2.87] 含 0 → INCONCLUSIVE；同口径下 DS5 域门新标准未成立
  （见负结果清单 10-11）
- **出处**：results/bootstrap_ci.json、results/equal_coverage_trust.csv、
  results/domain_gate.json

## 三、负结果清单（官方明确允许，须如实呈现）

1. **STA/LTA 第五证据被淘汰**（EXP09）——弱相关，预注册程序裁决 X=0
2. **DS4 相关性不成立**（EXP10 前半）——缺道/低信号与错误风险的相关性
   在自然数据上不存在（仅断点弱相关 9.5% vs 6.6%）
3. **DS3 相关性不成立**（EXP11）——P 不显著、S 极弱；且"完全一致也会错"
4. **DS5 原条款不成立**（EXP12 前半）——跨域后与 Voting 同降，未主动降级
5. **DS1 未全线成立**——与 Voting 统计并列而非显著领先（bootstrap CI 含 0）
6. **覆盖率天花板 45.64%**（严格 FUSE 门槛后；堵住绕过前为 54.2%）——近半数单元无安全自动路径（保守拒绝的代价）
7. **main/holdout 不稳定**——选择程序方向一致但幅度不稳（样本量限制）
8. **overlap 未审计**——obs/obst2024 与评估集的训练重叠 UNKNOWN，按 C 契约
   相关结论降级表述
9. **域门边界**（EXP12 后半）——v1.4 引擎下 retained unsafe 21.8% 仍高于域内 5.4%，
   门控是必要护栏、非完整解药
10. **FUSE 门被第 4.5 步绕过**（EXP14）——v1.4/v1.5 初版的 50% 点数字（天花板 54.2%、
    5.5%@50）在存在该路径漏洞时测得；堵住后天花板 45.64%，50% 预声明点位
    NOT_EVALUABLE——预声明点位不可达本身即是代价，如实记录
11. **DS5 域门新标准未成立（严格引擎下）**（EXP14）——coverage 37.8%→16.0%
    主动降级 ✓，但 retained unsafe 25.0% > 无门控 22.5% ✗：门只降"量"、未滤"质"；
    宽松档 familiar_borderline（coverage 25.2% / unsafe 21.8%）勉强双达标但幅度微弱

## 三·五、DS 判定总表（v1.5 新口径，C 调整）

| DS | 问题 | 判定 |
|---|---|---|
| DS1 | 是否真的优于简单投票 | ⚠️ **NOT_EVALUABLE@50%**（天花板 45.6% < 50%）；天花板补充比较 INCONCLUSIVE（诚实边界：同域模型接近时复杂调度边际有限） |
| DS2 | 基础排序是否可靠 | ✅ 成立（保住） |
| DS3 | 分歧能否识别风险 | ❌ 实测不成立 → v1.5 逻辑修正（单向风险证据 + FUSE 校准门槛 + 堵 4.5 步绕过） |
| DS4 | 数据质量是否预测错误 | ❌ 不成立 → 角色重定义（input integrity guard） |
| DS5 | shift 能否检测并降级 | ⚠️ 部分成立：coverage 主动降级 ✓ / retained unsafe 未降 ✗（新标准未成立） |

## 四、修正证据链（legacy 保留）

| 文件 | 内容 |
|---|---|
| docs/experiments/legacy/param_identification.json | 早期小样本参数（被 EXP01 取代） |
| docs/experiments/legacy/weight_calibration.json | 早期权重校准（被 n=895 逻辑回归取代） |
| src/calibrate/internal_score_calibration.py | 注入校准方法（被 EXP10 自然校准取代，保留作对照） |
| src/experiments/real_baseline_final.py | 历史成对口径 + 假质量基线（保留作历史记录） |
| configs/semifinal_main.yaml 版本注释 | v1.1→v1.4 全部变更留痕 |

## 五、v1.5 关键数字速查表（C 引用用）

| 数字 | 值 | 出处 |
|---|---|---|
| N_eval | 1306 (P 657 + S 649) | data/manifest_phase.csv |
| 容差 | P 0.5s / S 1.0s | 12 档敏感性证据 results/tolerance_sensitivity.json |
| Trust Unsafe@50% | **NOT_EVALUABLE**（天花板 45.64% < 50%，预声明点位不可达） | results/equal_coverage_trust.csv |
| Voting Unsafe@50% | 4.59% | results/baseline_results.csv |
| 最好单模型（EQT）@50% | 7.2% | results/model_comparison.csv |
| OBSTransformer S 容差内 | 72.0% | results/model_comparison.csv |
| 天花板 | 45.64%（596/1306 有有效输出；堵住 FUSE 门绕过前为 54.2%） | results/main_results.csv |
| 拦截率@50% | NOT_EVALUABLE（50% 点位不可达） | results/equal_coverage_trust.csv |
| Bootstrap Δ(vs Voting) | 50% 点 NOT_EVALUABLE；天花板补充（45.6% 点）Δ=+1.17pp, CI [-1.42, +2.87] → INCONCLUSIVE | results/bootstrap_ci.json |
| S 相 Δ | 天花板补充 Δ=+3.4pp, CI [-1.0, +5.67] → INCONCLUSIVE | results/bootstrap_ci.json |
| 风险分箱 | 4.07→9.2→28.57%（单调，n=418/163/14；30+ 分箱 n<10 标不可靠） | results/risk_bins.csv |
| failure 未拦住@50% | NOT_EVALUABLE（50% 点位不可达） | results/failure_raw.csv |
| 校准器（Platt） | PickBlue/EQT Brier 改善 12-16%；geofon 不校 | results/calibration/platt_calibrators.json |
| 域门阈值（XO 马氏距离） | 95%=3.94 / 99%=5.27 | results/domain_gate.json |
| DS5 新标准 | ❌ 未成立（严格引擎下）：coverage 37.8→16.0% ✓ / retained unsafe 25.0% vs 22.5% ✗ | results/domain_gate.json |

## 六、数字出处规则（C 引用时）

- 所有主实验数字来自 v1.5（configs/semifinal_main.yaml 冻结，含 FUSE 门绕过修复）
- 历史数字（29.1%→2.8%、5.5%@50 等）**不得引用**，已由 v1.5 全链重跑取代
- 任何定量表述指回上表"出处"文件即可满足可追溯要求
