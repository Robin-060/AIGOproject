# C 任务卡：评测框架 + 单模型基线 + 实验设计 + 参数调优

---

## 项目全局：Trust Engine 是什么、怎么做

### 项目整体架构

```
OBS 波形
  │
  ▼
Data Module (数据与模型组)    ← 另一条工作线
  ├── 数据质量检查 → QualityReport
  └── 模型推理 → ModelPrediction[]
  │
  ▼
══════════════════════ Trust Engine（我们在做） ══════════════════
  │
  ├── Evidence Layer（证据层）
  │   ├── data_evidence      (0-30) ← A 负责
  │   ├── single_model       (0-15) ← B 负责
  │   ├── multi_model        (0-40) ← D 负责 ★核心
  │   └── physics            (0-15) ← B 负责
  │
  ├── Reliability Engine（引擎层）
  │   └── evaluate_reliability()   ← D 负责
  │
  ├── Router（路由层）
  │   └── route()                  ← B 负责
  │
  └── Pipeline（主流程）
      └── analyze_sample()         ← D 负责
  │
  ▼
ReliabilityResult → 平台展示组（另一条工作线）
```

### 我们的代码目录

```
src/
├── schema.py                       ← 全组共用数据结构（已定稿）
├── evidence/
│   ├── data_evidence.py            ← A 负责
│   ├── single_model.py             ← B 负责
│   ├── multi_model.py              ← D 负责 ★
│   └── physics.py                  ← B 负责
├── engine/
│   └── reliability.py              ← D + B
├── pipeline.py                     ← D 负责
tests/
├── test_evidence.py                ← A + B + D
├── test_engine.py                  ← B
└── evaluate.py                     ← 【你负责】主体 + A(最高置信度基线) + B(简单投票基线)
config/
└── thresholds.yaml                 ← D + 【你】
```

### 完整步骤总览

```
M0 ✅ 已完成

M1 基础设施 — 评测框架 + 基线           ← 你现在在这里
  ├── 你: 错误标准 + evaluate.py 框架 + 单模型基线
  ├── A: data_evidence + 最高置信度基线
  ├── B: single_model + physics + router + 简单投票基线
  └── D: multi_model + reliability + pipeline

M2 核心开发 — 调参 + 消融实验 + 核心图表 ← 你的主力阶段
  ├── 你: 网格调参 + 消融实验 + 核心图表 + 实验报告
  ├── A/B: 配合消融实验（模块可单独开关）
  └── D: 接入 SeisBench 真实模型

M3 联调交付
  ├── 你: 最终实验报告 + 给文档组提供数据
  └── 全员: 配合联调 + 修 bug
```

---

## ⚠️ 阻塞关系（开工前必读）

```
你不依赖任何人 → 可以立即开工

但 A 和 B 需要往你的 evaluate.py 里加基线函数
→ 你先建好 evaluate.py 框架 + 占位函数 → A、B 往里填

你依赖:
  - 仿真数据 + 标签（M2 阶段，等数据与模型组交付）
  - A/B/D 模块加 enable 开关（消融实验需要）
```

### 开工顺序

```
第1天 (无依赖):  错误标准 + evaluate.py 框架 + 单模型基线
第2天 (收基线):  A、B 把他们的基线函数加到你的文件中
第3天 (联调):    验证三个基线逻辑正确
M2:              主力实验（需要等仿真数据）
```

---

## 你的职责

```
    Trust Engine 产出的 ReliabilityResult
                    │
                    ▼
    你写 evaluate.py:
    读标签 (ground truth) → 判断样本"对不对" → 统计指标
                    │
                    ▼
    三个基线（你写1个，A和B各写1个，你负责汇总）:
    1. 单模型策略       → 固定 OBSTransformer    ← 你写
    2. 最高置信度策略    → 选 score 最高           ← A 写
    3. 简单投票策略      → 多模型取中位数          ← B 写
                    │
                    ▼
    M2 你主力: 调参 + 消融实验 + 核心图表 + 实验报告
```

---

## M1 任务

### 1. 定义错误标准

创建 `docs/experiments/error_definition.md`：

```markdown
# 预测错误判定标准

## P 波错误: |预测 - 真值| > 0.5s 或漏检
## S 波错误: |预测 - 真值| > 1.0s 或漏检
## 虚检: 模型报了但真值没有
## 整体判定: P 或 S 任一出错 → 该样本错误
```

---

### 2. 搭建 `tests/evaluate.py` 框架

```python
"""
评测模块: 对比预测和真值
"""
from typing import List, Dict
from src.schema import ModelPrediction, ReliabilityResult


def evaluate_sample(
    predictions: List[ModelPrediction],
    ground_truth: Dict[str, float],  # {"P": 12.35, "S": 25.50}
    p_tolerance: float = 0.5,
    s_tolerance: float = 1.0
) -> Dict:
    """单样本评估 → {p_correct, s_correct, overall_correct, p_error_s, s_error_s}"""
    pass


def evaluate_dataset(
    predictions_per_sample: Dict[str, List[ModelPrediction]],
    ground_truths: Dict[str, Dict[str, float]]
) -> Dict:
    """全数据集统计 → {total, correct, accuracy, mae_p, mae_s, ...}"""
    pass


def compute_trust_layer_metrics(
    reliability_results: List[ReliabilityResult],
    predictions_per_sample: Dict,
    ground_truths: Dict
) -> Dict:
    """Trust Layer 核心指标 → {error_detection_rate, auto_coverage, selective_risk, review_burden}"""
    pass


# ═══════ 三个基线 ═══════

def baseline_single_model(predictions_per_sample: Dict) -> Dict:
    """基线 1: 固定使用 OBSTransformer（你写）"""
    pass

def baseline_max_confidence(predictions_per_sample: Dict) -> Dict:
    """基线 2: 选 score 最高（A 写）"""
    pass  # A 往里填

def baseline_voting(predictions_per_sample: Dict) -> Dict:
    """基线 3: 多模型取中位数（B 写）"""
    pass  # B 往里填
```

---

### 3. 写单模型基线

```python
def baseline_single_model(predictions_per_sample: Dict) -> Dict:
    """基线 1: 固定使用 OBSTransformer"""
    results = {}
    for sample_id, predictions in predictions_per_sample.items():
        obst_preds = [p for p in predictions if p.model == "OBSTransformer"]
        p = next((p for p in obst_preds if p.phase == "P"), None)
        s = next((p for p in obst_preds if p.phase == "S"), None)
        results[sample_id] = {
            "P_time": p.time_s if p else -1,
            "S_time": s.time_s if s else -1,
        }
    return results
```

---

### 4. 验证逻辑

```python
def test_evaluate():
    predictions = {"S001": [ModelPrediction("A", "P", 12.30)]}
    ground_truths = {"S001": {"P": 12.35, "S": 25.50}}
    result = evaluate_dataset(predictions, ground_truths)
    assert result["total_samples"] == 1
    print("✅ evaluate_dataset 逻辑正确")
```

---

### 5. M1 验收标准

```
□ error_definition.md 完成
□ evaluate.py 框架完成（3 个函数 + 单模型基线）
□ A、B 的基线函数追加到文件中
□ 模拟数据验证逻辑 ✅
□ push 到 GitHub
```

---

## M2 任务：你的主力阶段

### 6. 参数调优

拿到仿真数据（≥30 段 + 标签 CSV）后：

```
遍历候选参数:
  p_tolerance:     [0.1, 0.2, 0.3, 0.5, 1.0]
  s_tolerance:     [0.2, 0.3, 0.5, 1.0, 1.5]
  risk_low_max:    [20, 25, 30, 35, 40]
  risk_medium_max: [50, 55, 60, 65, 70]

每组参数 → 跑全部仿真样本 → 记录三指标
选最优 → 更新 config/thresholds.yaml
```

产出: `docs/experiments/param_tuning.md`

---

### 7. 消融实验

```
实验组:
  完整系统
  去掉数据证据 (关 A 的 data_evidence)
  去掉单模型证据 (关 B 的 single_model)
  去掉多模型证据 (关 D 的 multi_model) ← 预期下降最多
  去掉物理证据 (关 B 的 physics)

记录: 错误拦截率 + 自动覆盖率
```

产出: 消融柱状图

---

### 8. 核心图表

```
图 1 ★: 风险-覆盖率曲线
  X: 自动覆盖率, Y: 错误拦截率
  四条线: Trust Layer / 单模型 / 最高置信度 / 简单投票

图 2: 消融柱状图
图 3: 典型案例 (3-5个被拦截的错误)
```

---

### 9. M3 接续

```
□ 补充最终样本数据
□ 润色三张图
□ 撰写 final_report.md
□ 给文档统筹组提供实验数据 + 核心图表
```
