# Model Registry — 冻结预测的真实模型身份

> 状态：A 的事实交付物（2026-08-29），待 C 材料一致性审核（C 契约 3.2 必填字段）。
> 本文件回答一个问题：冻结预测（records_all.json）三列到底是谁跑出来的。

## 1. 总表（冻结数据三列 vs 档案声称）

> C 锁死条件：registry 区分 **architecture_origin（架构来源）** 与
> **checkpoint_training_domain（checkpoint 训练域）** —— 同架构异训练域
> （geofon vs obs）是模型异质性论证的关键。

| 冻结数据列名 | 档案声称 | **实际身份（已指纹验证）** | architecture_origin | checkpoint_training_domain | 通道 |
|---|---|---|---|---|---|
| PhaseNet | PhaseNet obs | **PhaseNet geofon**（陆地模型） | PhaseNet 架构（Zhu & Beroza, 2019） | 陆地 GEOfon 域 | ZNE 三分量 |
| PickBlue | PickBlue (独立 OBS 模型) | **PhaseNet obs** | PhaseNet 架构（同上） | OBS 域 | Z12H 四分量 |
| OBSTransformer | obst2024 | obst2024 ✓（档案无误） | OBSTransformer 架构（Niksejel & Zhang, 2024） | OBST2024 OBS 域 | ZNE 三分量 |
| EQTransformer（v1.3 新增，C 已批） | — | EQT-obs | EQTransformer 架构（Mousavi et al., 2020） | OBS 域 | ZNE 三分量 |

**结论（v1.3 起）：四套 checkpoint、三个架构（PhaseNet / OBSTransformer /
EQTransformer）、跨两个训练域（陆地 + OBS）——新增 EQT 为异构证据，
旧模型全部保留（C 锁死条件：不替换）。**

## 2. 逐模型注册信息（C 契约 3.2 字段）

### 2.1 冻结 "PhaseNet" 列 = PhaseNet geofon

| 字段 | 值 |
|---|---|
| class | `seisbench.models.PhaseNet` |
| weights_name | `geofon`（`PhaseNet.from_pretrained("geofon")`） |
| architecture_origin | PhaseNet 架构（Zhu & Beroza, 2019, doi:10.1093/gji/ggy423） |
| checkpoint_training_domain | 陆地 GEOfon 域（非 OBS） |
| in_channels / component_order | 3 / ZNE |
| training_domain | 陆地地震数据域（非 OBS） |
| default_args | P_threshold=0.570, S_threshold=0.073, blinding=[250,250] |
| score_semantics | max(P_peak, S_peak)，未校准 |
| eval_overlap_status | 与 OBS 评估集无训练域重叠（陆地训练）；待正式审计确认 |

**证据链**：8 个样本指纹匹配——P 拾取 8/8 完全吻合、置信度 8/8 完全吻合、
有 S 值的样本精确一致（85.1=85.1）、其余 7 个双方均无 S。
复现路径：`PhaseNet.from_pretrained("geofon")` + Z/N/E 三通道
（1→N、2→E 映射），脚本 `src/experiments/end_to_end_verification.py`。

### 2.2 冻结 "PickBlue" 列 = PhaseNet obs

| 字段 | 值 |
|---|---|
| class | `seisbench.models.PhaseNet`（经 `PickBlue(base="phasenet")` 工厂） |
| weights_name | `obs`（`PhaseNet.from_pretrained("obs")`） |
| architecture_origin | PhaseNet 架构（Zhu & Beroza, 2019）——与 2.1 同架构异训练域 |
| checkpoint_training_domain | OBS 域（海洋） |
| in_channels / component_order | 4 / Z12H |
| training_domain | OBS 数据域（海洋） |
| default_args | P_threshold=0.2, S_threshold=0.1 |
| score_semantics | max(P_peak, S_peak)，未校准 |
| eval_overlap_status | **UNKNOWN——很可能与评估集重叠（obs 权重以 OBS 数据训练），待审计** |

**证据链**（三层）：
1. 源码级：seisbench 0.12.3 `pickblue.py` 中 `PickBlue(base="phasenet")`
   直接返回 `PhaseNet.from_pretrained("obs", ...)`——同一调用
2. 权重级：两模型全部参数逐层 `torch.equal` = True
3. 输出级：本地复现与冻结预测偏差 0.02s，置信度 0.912 ≈ 0.907

### 2.3 冻结 "OBSTransformer" 列 = obst2024

| 字段 | 值 |
|---|---|
| class | `seisbench.models.OBSTransformer` |
| weights_name | `obst2024` |
| architecture_origin | OBSTransformer 架构（Niksejel & Zhang, 2024, doi:10.1093/gji/ggae049） |
| checkpoint_training_domain | OBST2024 OBS 域 |
| in_channels / component_order | 3 / ZNE |
| training_domain | OBST2024 OBS 数据集域 |
| default_args | {}（空） |
| score_semantics | max(P_peak, S_peak)，未校准 |
| eval_overlap_status | **UNKNOWN——待审计（训练集 OBST2024 与评估集 OBS 数据集的关系未验证）** |

**质量缺陷记录**（供辨别能力分析使用）：S 拾取系统性偏弱——50 条探针容差内
82%（对比 EQTransformer-obs 100%），残差 p90 = 0.38s；缺 E 通道时 S 命中率
降至 58%（74%→58%）。

## 3. 代码-行为不一致记录

仓库 `src/data_layer/data_layer.py` 的初始化代码（第 265、284 行）：

```python
models["PhaseNet"] = PhaseNet.from_pretrained("obs")   # 声称 obs
models["PickBlue"] = PickBlue(base="phasenet")          # 实际也加载 obs
```

问题：按此代码重跑会得到两个相同的 obs 模型，与冻结数据（geofon + obs）
不一致。说明生成 records_all.json 时的实际执行环境/脚本与仓库代码存在
未记录差异（数据组确认初始化调用一致，但版本号未冻结，无法追溯）。

**处理状态**：记录在案；代码是否修改由团队裁决（C 科学口径参与）。
冻结预测的地位不受影响——它是评估对象，本文件只修正其身份描述。

## 4. 档案-行为一致性审计（v2 修正记录）

| 档案假设 | 实际行为 | 修正 |
|---|---|---|
| "PickBlue 需要 4 分量" | 数据组 94% 的缺 E 记录上跑出预测；实测缺 E 时命中 91-93%（不降反升） | semifinal_v1.2：required=[Z,H]，preferred=[N,E] |
| OBSTransformer 无通道约束问题 | 缺 E 时 S 命中率 74%→58%，显著降级 | 保留 H 必需档案；其 S 缺陷由证据层与辨别度量处理 |

## 5. 待决事项（交 C）

1. `data_layer.py` 初始化代码：改代码 vs 记录在案（C 裁决，见第 3 节）
2. overlap audit 正式执行（A）——在完成前，涉及 obs/obst2024 的结论按
   C 契约 "overlap unknown 不入 primary claim" 处理
3. 置信度未校准的表述统一（连接 future research "单模型置信度校准"）
4. third_party_and_license.md 的权重来源/许可细化（C 材料）
