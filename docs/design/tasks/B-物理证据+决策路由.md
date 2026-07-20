# B 任务卡：单模型证据 + 物理证据 + 决策路由 + 简单投票基线

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
  │   ├── single_model       (0-15) ← 【你负责】
  │   ├── multi_model        (0-40) ← D 负责 ★核心
  │   └── physics            (0-15) ← 【你负责】
  │
  ├── Reliability Engine（引擎层）
  │   └── evaluate_reliability()   ← D 负责
  │
  ├── Router（路由层）
  │   └── route()                  ← 【你负责】
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
│   ├── single_model.py             ← 【你负责】
│   ├── multi_model.py              ← D 负责 ★
│   └── physics.py                  ← 【你负责】
├── engine/
│   └── reliability.py              ← D + 【你(router 部分)】
├── pipeline.py                     ← D 负责
tests/
├── test_evidence.py                ← A + 【你】+ D
├── test_engine.py                  ← 【你负责】
└── evaluate.py                     ← C + A + 【你(简单投票基线)】
config/
└── thresholds.yaml                 ← D + C
```

### 完整步骤总览

```
M0 ✅ 已完成

M1 基础设施 — 所有模块写完 + 测试通过    ← 你现在在这里
  ├── 你: single_model + physics + router + 简单投票基线 + 测试
  ├── A: data_evidence + 最高置信度基线 + 测试
  ├── C: 错误标准 + 评测框架 + 单模型基线
  └── D: multi_model + reliability + pipeline

M2 核心开发 — 接入真实模型 + 调参 + 消融实验
  ├── 你 + A: 配合消融实验（模块可单独开关）
  ├── C: 网格调参 + 消融实验 + 核心图表
  └── D: 接入 SeisBench 真实模型

M3 联调交付
  └── 全员: 配合联调 + 修 bug + 给文档组提供数据
```

---

## ⚠️ 阻塞关系（开工前必读）

```
你不依赖任何人 → 可以立即开工

但 D 的 reliability.py 需要调你的三个函数:
  evaluate_single_model() / evaluate_physics() / route()
→ 你先写好函数签名 + 初版 → 立刻通知 D
→ 不用等完美版，先给接口

你的 baseline_voting 需要加到 C 的 evaluate.py
→ C 先建好框架 → 你往里加
```

### 开工顺序

```
第1天 (无依赖):  single_model.py + physics.py + router()  ← 三个并行写
第2天 (交付):    写完 + 12 个测试通过 → 通知 D 和 C
第3天 (联调):    配合 D 联调 reliability.py
```

---

## 你负责的部分 → 属于 M1

```
模块 1: src/evidence/single_model.py     ← 模型自信度 → 风险分 (0-15)
模块 2: src/evidence/physics.py          ← 物理约束 → 风险分 (0-15)
模块 3: src/engine/reliability.py 中的 router()  ← 分数 → 等级 + 动作
模块 4: tests/evaluate.py 中的 baseline_voting() ← 简单投票基线

tests/
├── test_evidence.py     ← 你负责（single_model 3 个 + physics 4 个）
└── test_engine.py       ← 你负责（router 4 个）
```

---

## M1 步骤

### 1. 写 `src/evidence/single_model.py`

```python
def evaluate_single_model(predictions: List[ModelPrediction]) -> Tuple[float, List[str]]:
    """根据模型自身的置信度打分 (满分 15)"""
    pass
```

**打分规则**：

| 条件 | 加分 | 原因码 |
|------|------|--------|
| 每个 score < 0.3 的预测 | +5 | `LOW_CONFIDENCE_{model}_{phase}` |
| 所有预测 score ≥ 0.3 | 0 | `CONFIDENCE_OK` |
| 上限 | min(score, 15) | |

```
3 个预测, 2 个 score < 0.3 → 2 × 5 = 10 分
5 个预测, 全 < 0.3 → 25 → 截断为 15 分
```

---

### 2. 写 `src/evidence/physics.py`

```python
def evaluate_physics(
    predictions: List[ModelPrediction],
    sp_min_s: float = 0.1, sp_max_s: float = 60.0
) -> Tuple[float, List[str]]:
    """检查物理约束 (满分 15)"""
    pass
```

**打分规则**：

| 条件 | 加分 | 原因码 |
|------|------|--------|
| P 或 S 任一缺失 | 0（加 `PHYSICS_INSUFFICIENT_DATA`） | |
| p_time >= s_time | +10 | `PHYSICS_P_AFTER_S` |
| S-P < 0.1s | +5 | `PHYSICS_SP_TOO_SHORT` |
| S-P > 60s | +5 | `PHYSICS_SP_TOO_LONG` |
| 全 OK | 0 | `PHYSICS_OK` |

多个模型 → P/S 各取中位数再比较。

---

### 3. 写 `router()` 在 `src/engine/reliability.py` 中

```python
def route(risk_score: float):
    if risk_score <= 30:   return ("LOW", "ACCEPT")
    elif risk_score <= 60:  return ("MEDIUM", "ROUTE")
    else:                   return ("HIGH", "ABSTAIN")
```

---

### 4. 写简单投票基线

在 `tests/evaluate.py` 中追加（C 创建文件框架，你往里加）：

```python
def baseline_voting(predictions_per_sample: Dict) -> Dict:
    """
    基线: 多模型 P/S 时间取中位数
    """
    import statistics
    results = {}
    for sample_id, predictions in predictions_per_sample.items():
        p_times = [p.time_s for p in predictions if p.phase == "P" and p.time_s > 0]
        s_times = [p.time_s for p in predictions if p.phase == "S" and p.time_s > 0]
        
        p_median = statistics.median(p_times) if p_times else -1
        s_median = statistics.median(s_times) if s_times else -1
        
        results[sample_id] = {"P_time": p_median, "S_time": s_median}
    return results
```

---

### 5. 写测试

**single_model 测试** — 加到 `tests/test_evidence.py`：

```python
from src.evidence.single_model import evaluate_single_model

def test_single_all_confident():
    preds = [ModelPrediction("A", "P", 10.0, score=0.91),
             ModelPrediction("B", "P", 10.1, score=0.88)]
    score, _ = evaluate_single_model(preds)
    assert score == 0

def test_single_some_low():
    preds = [ModelPrediction("A", "P", 10.0, score=0.21),
             ModelPrediction("B", "P", 10.1, score=0.15),
             ModelPrediction("A", "S", 25.0, score=0.91)]
    score, _ = evaluate_single_model(preds)
    assert score == 10

def test_single_capped():
    preds = [ModelPrediction(f"M{i}", score=0.1) for i in range(10)]
    score, _ = evaluate_single_model(preds)
    assert score == 15
```

**physics 测试**：

```python
from src.evidence.physics import evaluate_physics

def test_physics_normal():
    preds = [ModelPrediction("A", "P", 12.30), ModelPrediction("B", "P", 12.42),
             ModelPrediction("A", "S", 25.50)]
    score, reasons = evaluate_physics(preds)
    assert score == 0 and "PHYSICS_OK" in reasons

def test_physics_p_after_s():
    preds = [ModelPrediction("A", "P", 30.0), ModelPrediction("A", "S", 25.0)]
    score, reasons = evaluate_physics(preds)
    assert score >= 10 and "PHYSICS_P_AFTER_S" in reasons

def test_physics_sp_too_short():
    preds = [ModelPrediction("A", "P", 12.0), ModelPrediction("A", "S", 12.05)]
    score, _ = evaluate_physics(preds)
    assert score >= 5

def test_physics_no_data():
    preds = [ModelPrediction("A", "P", 12.0)]
    score, reasons = evaluate_physics(preds)
    assert "PHYSICS_INSUFFICIENT_DATA" in reasons and score == 0
```

**router 测试** — `tests/test_engine.py`：

```python
from src.engine.reliability import route

def test_route_accept():   assert route(8)  == ("LOW", "ACCEPT")
def test_route_fuse():     assert route(45) == ("MEDIUM", "ROUTE")
def test_route_abstain():  assert route(78) == ("HIGH", "ABSTAIN")
def test_route_boundary():
    assert route(30)[0] == "LOW" and route(31)[0] == "MEDIUM"
    assert route(60)[0] == "MEDIUM" and route(61)[0] == "HIGH"
```

---

### 6. M1 验收标准

```
□ single_model 测试 3 个 ✅
□ physics 测试 4 个 ✅
□ router 测试 4 个 ✅
□ baseline_voting 逻辑验证通过
□ 共 12 个测试 ✅，push 到 GitHub
```

---

## M2 接续

```
□ single_model/physics 加 enable 开关（配合 C 消融实验）
□ router 阈值改成读 config/thresholds.yaml
```

---
