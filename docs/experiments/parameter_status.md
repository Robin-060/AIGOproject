# 参数冻结状态表（复赛最终版）

> 状态：**FINAL / FROZEN**
> 唯一运行源：`configs/semifinal_main.yaml`
> TrustConfig 参数集名：`calibrated_v1.0`；实验身份：`semifinal_v1.5.1-bugfix`，
> 以完整 config SHA-256 与结果行关联。

## 1. 当前绑定值

| 参数 | 当前值 | 来源 / 用途 | 状态 |
|---|---:|---|---|
| P consensus tolerance | 0.34 s | 双模型正确差值 95% 分位，n=674 | 冻结 |
| S consensus tolerance | 0.51 s | 双模型正确差值 95% 分位，n=455 | 冻结 |
| severe disagreement P/S | 1.0 s / 2.0 s | 分歧粗分与基线协议 | 冻结 |
| correctness tolerance P/S | 0.5 s / 1.0 s | 统一相位级正确性评价 | 流程冻结 |
| S−P interval min/max | 5.7 s / 33.42 s | 真实 S−P 分布 2.5% / 97.5% 分位，n=411 | 冻结 |
| fusion confidence floor | 0.70 | 融合证据准入门槛 | 冻结 |
| automatic risk threshold | 10.0 | 交互默认值；正式 ranking mode 由协议控制 | 冻结 |
| risk LOW / MEDIUM 分界 | 10 / 30 | ordinal risk bins | 冻结 |
| data / single / multi / physics weights | 30 / 24 / 37 / 40 | 校准与历史证据链，详见溯源表 | 冻结 |
| global / holdout / bootstrap seed | 42 | 数据分片与重采样 | 冻结 |
| bootstrap | 60 stations × 1000 | station-cluster paired bootstrap | 冻结 |

## 2. EXP17 参数来源审计

EXP17 正式运行路径从冻结 config 读取 P=0.34 s / S=0.51 s。历史常量 P=0.30/S=0.50
仅作为 `config=None` 的 legacy fallback，未进入冻结运行。R1 显式固定 0.34/0.51 后重跑，
Coverage 54.13%、Unsafe 5.51%、Error Interception 94.26% 和配对 bootstrap 上界 +2.24pp
与 EXP17-A 冻结结果完全一致。

`R1 PASS` 仅表示参数来源与执行路径复现一致，不表示 EXP17 c2 或总体安全 Gate 通过。

## 3. 历史值的地位

| 历史值 | 当前处置 |
|---|---|
| P=0.30 / S=0.50 | legacy fallback，不在正式运行路径 |
| P/S interval 0.1 / 60.0 | 早期 heuristic，已被 5.7 / 33.42 取代 |
| 人工注入故障罚分 | 保留为方法参照；自然故障外推边界已披露 |

历史值不删除，但不得与当前冻结参数混用。详细校准证据见
`docs/parameter_provenance.md`；正式引用以 config 和 `results/evidence_manifest.json` 为准。

## 4. 变更纪律

1. 任何新参数或 routing 规则必须创建新的版本化实验；
2. 不原地改写 v1.5.1、EXP16 或 EXP17 冻结结果；
3. 不为使候选通过而更改 +2.0pp 非劣界、bootstrap 口径或评价分母；
4. 参数修订必须同步 config、run trajectory、raw result、图表与 Scientific Claim。
