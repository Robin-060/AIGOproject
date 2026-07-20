# Trust Engine 工作计划：步骤 + 四人分工

> **版本**: v1.0  
> **日期**: 2026-07-18  
> **负责人**: 你（Trust Engine 管理人）  
> **组员**: 4 人（含你）  
> **对接**: 数据与模型组（提供 QualityReport + ModelPrediction）、平台展示组（消费 ReliabilityResult）

---

## 0. 你的职责：管什么、不管什么

### 我们管：

```
数据与模型组给我们       我们产出                 给平台展示组

QualityReport    ──┐
                   ├──→ Evidence Layer ──→ Reliability Engine ──→ ReliabilityResult
ModelPrediction[] ─┘                                              (risk_score/level/action/reasons)
```

### 我们不管：

- ❌ 数据质量检查的实现（数据与模型组负责 `checker.py`，我们只管消费 `QualityReport`）
- ❌ 模型怎么加载、怎么推理（数据与模型组负责 Model Adapter）
- ❌ Web 面板画什么样子（平台展示组负责）
- ❌ PRD 和 4 页文档撰写（文档统筹负责）

### 我们的代码文件：

```
src/
├── evidence/                    ← 我们负责
│   ├── data_evidence.py         ← 数据质量 → 风险分 (0-30)
│   ├── single_model.py          ← 模型自信度 → 风险分 (0-15)
│   ├── multi_model.py           ← 多模型一致性 → 风险分 (0-40) ★核心
│   └── physics.py               ← 物理约束 → 风险分 (0-15)
├── engine/
│   └── reliability.py           ← 汇总四证据 → 风险评分 → 等级 → 路由
├── pipeline.py                  ← 主流程（与数据组协作）
tests/
├── test_evidence.py             ← 证据模块测试
├── test_engine.py               ← 引擎测试
└── fixtures/                    ← 测试用例
config/
└── thresholds.yaml              ← 所有可调参数
```

---

## 1. 四人分工

```
你（管理人）
├── 多模型证据 + 可靠性引擎 + 整体集成
│
├── 组员 A：数据证据 (0-30) + 单模型证据 (0-15)
│   └── data_evidence.py + single_model.py + 它们的测试
│
├── 组员 B：物理证据 (0-15) + 决策路由
│   └── physics.py + router() + 它们的测试
│
└── 组员 C：实验设计 + 评测 + 参数调优
    └── 基线实现 + 消融实验 + 调参 + 实验报告
```

### 你（管理人）

| 职责 | 核心产出 |
|------|----------|
| **多模型证据** (0-40分) | `src/evidence/multi_model.py` |
| **可靠性引擎** (汇总+评分+路由) | `src/engine/reliability.py` |
| **Pipeline 集成** | `src/pipeline.py` — 串联 Data → Model → Evidence → Engine |
| **代码 Review** | 审查 A/B/C 的代码 + 合并 PR |
| **日会主持** | 15 分钟：验收昨天交付、解决阻塞、确认今天目标 |
| **接口对接** | 和数据组确认 QualityReport/Prediction 格式、和展示组确认 ReliabilityResult 格式 |

### 组员 A：数据证据 + 单模型证据

| 职责 | 核心产出 | 工作量 |
|------|----------|--------|
| **数据证据模块** | `src/evidence/data_evidence.py` | ~40 行 |
| 读 QualityReport → 打分 + 原因码 | 缺道/断点/削波/SNR → 0-30 分 | |
| **单模型证据模块** | `src/evidence/single_model.py` | ~25 行 |
| 读 ModelPrediction[] → 打分 | 模型 score < 阈值 → 0-15 分 | |
| **测试** | `tests/test_evidence.py` (数据+单模型部分) | ~50 行 |

### 组员 B：物理证据 + 决策路由

| 职责 | 核心产出 | 工作量 |
|------|----------|--------|
| **物理证据模块** | `src/evidence/physics.py` | ~35 行 |
| 读 ModelPrediction[] → 打分 | P<S、S-P 范围 → 0-15 分 | |
| **决策路由函数** | `src/engine/reliability.py` 中的 router() | ~20 行 |
| LOW→ACCEPT, MED→ROUTE, HIGH→ABSTAIN | | |
| **测试** | `tests/test_evidence.py` (物理) + `tests/test_engine.py` | ~50 行 |

### 组员 C：实验设计 + 评测

| 职责 | 核心产出 | 工作量 |
|------|----------|--------|
| **基线实现** | 单模型 / 最高置信度 / 简单投票 三个基线 | ~60 行 |
| **消融实验** | 逐一去掉证据 → 看性能下降 | ~40 行 |
| **核心图表** | 风险-覆盖率曲线 (最重要的一张图) | ~30 行 |
| **参数调优** | 调 weights/thresholds → 记录 → 固定 | 半天 |
| **实验报告** | `docs/experiments/final_report.md` | 半天 |

---

## 2. M1 阶段：Trust Engine 任务 (7.18 – 7.21)

### 我们的 M1 目标

> **四个证据模块写完 + 引擎跑通 demo + 测试通过**

### M1.1 统一接口确认（你 + 全组，7.18）

```
任务:
□ 和数据与模型组确认:
  - QualityReport 字段冻结 → 他们给我的数据长什么样？
  - ModelPrediction 字段冻结 → 每个模型的输出长什么样？
  - 示例数据: 能不能给我 2 段波形 + 对应的模型预测结果？

□ 和平台展示组确认:
  - ReliabilityResult 字段冻结 → 我给他们的数据长什么样？
  - 他们需要哪些字段用于展示？

产出: 三方确认的 Schema（已写在 src/schema.py 里，冻结即可）
```

### M1.2 组员 A：数据证据 + 单模型证据（7.18-7.19）

```
任务:
□ 写 data_evidence.py
  输入: QualityReport (四个字段)
  输出: (score: 0-30, reasons: [str])
  
  逻辑:
  - 缺通道: +12~20
  - 断点: +8~15
  - 削波: +5~10
  - 低SNR: +8~15
  - 采样率不匹配: +5
  - 全OK → 0 分 + "DATA_QUALITY_OK"

□ 写 single_model.py
  输入: List[ModelPrediction]
  输出: (score: 0-15, reasons: [str])
  
  逻辑:
  - 每个预测 score < 0.3 → +5 分
  - 全 ≥ 0.3 → 0 分 + "CONFIDENCE_OK"

□ 写测试: 用固定数据验证边界情况
  - 全OK → 0分
  - 缺2通道 → ≥20分
  - 所有模型低分 → ≥10分

交付: data_evidence.py + single_model.py + 测试通过
```

### M1.3 组员 B：物理证据 + 路由（7.18-7.19）

```
任务:
□ 写 physics.py
  输入: List[ModelPrediction]
  输出: (score: 0-15, reasons: [str])
  
  逻辑:
  - P 时间 ≥ S 时间 → +10 分 (物理不可能)
  - S-P 时间差 < 0.1s → +5 分 (太短)
  - S-P 时间差 > 60s → +5 分 (太长)
  - OK → 0 分 + "PHYSICS_OK"

□ 写 router() 在 reliability.py 里
  输入: risk_score (0-100)
  输出: risk_level + action
  
  逻辑:
  - 0-30 → LOW → ACCEPT
  - 31-60 → MEDIUM → ROUTE
  - 61-100 → HIGH → ABSTAIN

□ 写测试: 
  - P=30s, S=25s → P 在 S 后 → ≥10分
  - P=12s, S=25s → 正常 → 0分

交付: physics.py + router() + 测试通过
```

### M1.4 你：多模型证据 + 引擎 + 集成（7.18-7.20）

```
任务:
□ 写 multi_model.py (核心模块，最重要)
  输入: List[ModelPrediction]
  输出: (score: 0-40, reasons: [str])

  逻辑:
  1. 按 phase 分组 (P 组、S 组)
  2. P 组内找所有模型的时间差:
     max_diff ≤ 0.3s → CONSENSUS → 0分
     0.3 < max_diff ≤ 1.0s → MILD → +8分
     max_diff > 1.0s → SEVERE → +20分
     全漏检 → +15分
  3. S 组同理 (容差 0.5s)
  4. 有模型漏检但其他有结果 → +10分

□ 写 reliability.py (汇总引擎)
  输入: QualityReport + List[ModelPrediction]
  输出: ReliabilityResult
  
  1. 调 A 的数据证据 → data_score
  2. 调 A 的单模型证据 → single_score
  3. 调自己的多模型证据 → multi_score
  4. 调 B 的物理证据 → physics_score
  5. 总 = 四者之和
  6. 调 B 的 router() → risk_level + action
  7. 生成 evidence_summary (一句话可读总结)

□ 写 pipeline.py (与数据组协作)
  串联: 读波形 → ModelAdapter → 质量检查 → 证据 → 引擎 → 输出 JSON

□ 审查 A/B 的代码，合并

交付: multi_model.py + reliability.py + pipeline.py + A/B 代码合入
```

### M1.5 组员 C：实验准备（7.19-7.21）

```
任务:
□ 和仿真数据组确认:
  - 仿真数据的标签格式 (P/S 精确时间)
  - 至少 30 段仿真数据就绪
  
□ 定义"错误"标准 (和全组确认):
  - P 波误差 > 0.5s → 错误
  - S 波误差 > 1.0s → 错误
  - 漏检 (标签有但模型没检) → 错误
  - 虚检 (标签无但模型报了) → 错误

□ 实现评分函数 evaluate_predictions():
  输入: predictions[] + ground_truth[]
  输出: {precision, recall, mae_p, mae_s, error_count, total}

□ 实现三个基线:
  - baseline_single: 只信 OBSTransformer
  - baseline_max_conf: 每样本取最高分的模型
  - baseline_vote: 多模型时间取平均

交付: 错误标准文档 + evaluate_predictions() + 三个基线函数
```

### M1 完成检查（7.21 晚，你主持）

```
□ A 的 data_evidence + single_model 测试通过
□ B 的 physics + router 测试通过
□ 你的 multi_model + reliability 测试通过
□ pipeline.py demo 模式跑通（模拟数据三场景）
□ C 的基线函数可调用 + 错误标准文档就绪
□ 四人各自代码已 push 到 GitHub
```

---

## 3. M2 阶段：Trust Engine 任务 (7.22 – 7.28)

### 我们的 M2 目标

> **用真实模型+真实数据跑通 + 调参 + 实验证明我们更好**

### M2.1 接入真实模型（你 + 数据组，7.22）

```
任务:
□ 数据组交付:
  - SeisBench 两个模型可调用
  - 至少 5 段真实 YM 数据
  - 至少 30 段仿真数据 (带标签)

□ 你集成:
  - pipeline.py 中替换模拟预测为真实 ModelAdapter
  - 跑通: 真实波形 → 两模型推理 → 证据 → 引擎 → JSON

交付: pipeline.py 在真实数据上跑通
```

### M2.2 参数调优（C 主导 + 你复核，7.23-7.24）

```
任务:
□ C 在仿真数据上跑网格搜索:
  - model_tolerance P: [0.1, 0.2, 0.3, 0.5, 1.0]
  - model_tolerance S: [0.2, 0.3, 0.5, 1.0, 1.5]
  - 风险阈值: low_max [20, 25, 30, 35, 40]
  - 证据权重微调

□ 每次调参记录:
  - 错误拦截率
  - 自动覆盖率
  - 选择性风险

□ 固定最终参数 → 更新 config/thresholds.yaml

交付: docs/experiments/param_tuning.md + 最终参数
```

### M2.3 消融实验（C + A + B，7.25-7.26）

```
任务:
□ C 设计消融实验:
  完整系统:            错误拦截率 = ?
  去掉数据证据:         错误拦截率 = ?
  去掉单模型证据:       错误拦截率 = ?
  去掉多模型证据:       错误拦截率 = ?  ← 预期下降最大
  去掉物理证据:         错误拦截率 = ?

□ A 提供: data_evidence 可独立开关
□ B 提供: physics 可独立开关

□ C 生成图表:
  图1: 风险-覆盖率曲线 (核心，Trust Layer vs 三个基线)
  图2: 消融柱状图 (哪个证据最重要)
  图3: 案例展示 (3-5 个被成功拦截的错误)

交付: 三张图 + 实验数据
```

### M2.4 实验报告初稿（C 主导，7.27-7.28）

```
任务:
□ 实验设置
□ 核心结果: 风险-覆盖率曲线
□ 消融分析
□ 典型案例 (截图)
□ 局限性讨论

交付: docs/experiments/draft_report.md
```

### M2 完成检查（7.28 晚，你主持）

```
□ 真实模型 + 真实数据跑通
□ 参数已调优 + config 已更新
□ 消融实验完成 + 三张图生成
□ Trust Layer 在至少一个指标上优于所有基线
□ 四人代码全部合入 main 分支
```

---

## 4. M3 阶段：Trust Engine 任务 (7.29 – 8.1)

### 我们的 M3 目标

> **配合联调、提供实验数据给文档组、修 bug**

### M3.1 配合联调（全员，7.29-7.30）

```
任务:
□ 你: 和数据组确认 pipeline.py 最终版本
□ A: 和展示组确认 evidence 输出格式能否被前端消费
□ B: 和展示组确认 reliability JSON 前端能正确渲染
□ C: 给文档组提供实验数据 (核心图表 + 指标表)
□ 全员: 修复联调中发现的 bug
```

### M3.2 最终实验报告（C，7.30-7.31）

```
任务:
□ 补充最终数据 (在全部样本上的完整结果)
□ 润色图表
□ 撰写结论

交付: docs/experiments/final_report.md
```

### M3.3 提交前检查（你 + 全员，7.31-8.1）

```
□ A/B/C: 各自代码的注释 + docstring 补齐
□ 你: 最终 code review + 合并
□ C: 确保实验数据与 4 页文档一致
□ 你: 确认一键复现脚本中 Trust Engine 部分正常
```

---

## 5. 每日同步（你主持，15 分钟）

| 时间 | 内容 |
|------|------|
| 0-2 分 | 每人一句话：昨天做了什么 |
| 2-5 分 | 你检查：和昨天计划的偏差 |
| 5-10 分 | 解决阻塞：代码问题 / 接口不明确 / 需要外部协助 |
| 10-13 分 | 确认今天目标：每人今天要交付什么 |
| 13-15 分 | 你同步：来自数据组/展示组的接口变更或需求 |

---

## 6. 对外接口清单

| 我们从谁拿 | 拿什么 | 格式 | 对接人 |
|-----------|--------|------|--------|
| 数据与模型组 | QualityReport | Pydantic (schema.py) | 信号物理同学 |
| 数据与模型组 | ModelPrediction[] | Pydantic (schema.py) | 算法同学 |
| 数据与模型组 | 仿真数据标签 | CSV (sample_id, P_time, S_time) | 仿真数据同学 |

| 我们给谁 | 给什么 | 格式 | 对接人 |
|----------|--------|------|--------|
| 平台展示组 | ReliabilityResult | JSON | 可视化同学 |
| 文档统筹组 | 实验数据 + 图表 | Markdown + PNG | 社会学同学 |

---

## 7. 快速参考：四个模块一句话

| 模块 | 一句话 | 负责人 |
|------|--------|--------|
| data_evidence | 数据本身靠得住吗？缺道/断点/噪声 → 0-30分 | A |
| single_model | 模型自己自信吗？score 太低 → 0-15分 | A |
| multi_model | 两个模型意见一致吗？时间差太大 → 0-40分 ★ | 你 |
| physics | 物理上说得通吗？P在S前、S-P合理 → 0-15分 | B |
| reliability | 四证据求和 → 0-100 → L/M/H → ACCEPT/ROUTE/ABSTAIN | 你 |
| router | 分数 → 等级 + 动作 | B |
| evaluate | 在真值标签上评估性能 | C |
| baselines | 单模型/最高分/投票 三种对照 | C |
