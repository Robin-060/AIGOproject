# STA/LTA 第五证据设计文档

> 状态：设计稿（2026-08-29 晚），C 已批准方向。参数校准走预注册程序（C 契约 6.2）。
> C 锁死条件：**STA/LTA 是第五证据，不是真值**（不参与正确性判定、不进 manifest）；
> **参数只在 validation 校准**（不在 test 上调）。

## 1. 证据定义

对每个 (模型, 相位) 拾取，检查其时间点附近是否存在 STA/LTA 触发的独立支持：

- 在拾取时间 ±W 秒窗口内存在 STA/LTA 触发 → 有支持，不加罚
- 窗口内无任何触发 → **可疑**，该模型该相位的风险分 +X

动机：STA/LTA 与深度模型是完全不同的机制（能量比 vs 波形特征学习）。
两个独立机制同时认可，拾取可信度更高；模型"自信地错"的位置
（如 OBSTransformer 的坏 S）通常没有 STA/LTA 支持——传统方法成了
深度模型的独立证人。

数据源：`data/sta_lta_picks.csv`（895 条，带通 2-15Hz + 斜率修正协议，
与 Traditional baseline 同一实现，冻结于 8/29）。

## 2. 参数网格（validation 校准对象）

| 参数 | 含义 | 候选值 |
|---|---|---|
| W（支持窗口） | 拾取 ±W 秒内查触发 | {0.5, 1.0, 1.5}s |
| X（罚分） | 无支持时风险加分 | {0, 5, 8, 10} |

共 3×4 = 12 个候选组合（含 X=0 的"不启用"对照）。

## 3. 预注册选择准则

- **数据集**：main 分片（validation 角色，1046 相位单元）；holdout 仅作确认
- **准则**（跑之前声明，不得改）：
  **"main 上 Trust 覆盖率天花板处（46.7% 点位）Unsafe Output Rate
  更低者胜；并列时取更小的 X（更保守的罚分）"**
- **程序**：12 个组合逐一跑 Trust 全链（四模型 v1.3 冻结预测），
  选出胜者 → holdout 确认 → 冻结为 v1.3 正式参数
- **记录**：全部 12 个组合的结果表进探索日志（含落选组合，append-only）

## 4. 集成方式

- 新增 `src/trust_engine/stalta_evidence.py`：
  `evaluate_stalta_support(picks, sta_lta_map, window_s, penalty)`
- 在相位风险计算中加入该项（v1.3 起：风险 = 四证据 + STA/LTA 支持证据），
  config 版本同步升版
- 证据分解（evidence_breakdown）中单独列出一项，Demo 可展示

## 5. 硬约束（违反即回滚）

1. STA/LTA 触发时间**不得**写入 manifest_phase.csv 的 reference_time_s
2. STA/LTA 输出**不得**参与正确性判定（判定只用 seisbench 参考拾取）
3. 参数选择**不得**在 holdout/test 上调——选完参数后 test 只跑一次
4. 证据失效时（如支持度与正确性无相关性）如实记录为 DS4 负结果

## 6. 执行顺序（依赖 EQT 完成）

1. EQT 895 条推理完成 → 四模型冻结预测升版（v1.3）
2. 写 stalta_evidence.py + 集成到主实验
3. 12 组合 × main 分片跑 Trust 全链
4. 胜者 holdout 确认
5. 冻结 v1.3 参数 + 探索日志记录全表
