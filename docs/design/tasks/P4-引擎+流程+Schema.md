# P4 任务卡：可靠性引擎 + Pipeline + Schema

---

## 项目全局：Trust Engine

```
OBS 波形 → Data Module (另一组) → QualityReport + ModelPrediction[]
                                       │
                    ═══════════ Trust Engine ═══════════
                    ├── data_evidence   (0-30) ← P1
                    ├── single_model    (0-15) ← P1
                    ├── multi_model     (0-40) ← P3
                    ├── physics         (0-15) ← P2
                    ├── reliability     (引擎) ← 你
                    ├── route()         (路由) ← P2 (函数放你的文件里)
                    └── pipeline        (主流程) ← 你
                                       │
                               ReliabilityResult → 展示组
```

## 代码目录

```
src/
├── schema.py              ← 你 (全组共用，已写好)
├── evidence/
│   ├── data_evidence.py   ← P1
│   ├── single_model.py    ← P1
│   ├── multi_model.py     ← P3
│   └── physics.py         ← P2
├── engine/
│   └── reliability.py     ← 你 ★ (P2 在你文件里写 route)
└── pipeline.py            ← 你 ★
```

## 你的模块 → M1

### 模块 1：`schema.py` — 全组共用数据结构

把整套 Schema 写好，P1/P2/P3 才能开工。**这是第一优先级。**

```python
# 需要定义:
QualityReport     # 数据组给的质量报告
ModelPrediction   # 数据组给的模型预测
Evidence          # 四证据汇总
ReliabilityResult # 最终输出
SampleAnalysis    # 顶层对象
route()           # 工具函数
```

### 模块 2：`reliability.py` — 可靠性引擎

输入 `QualityReport + List[ModelPrediction]` → 输出 `ReliabilityResult`

```python
def evaluate_reliability(quality, predictions, enable=None):
    # 调 P1: evaluate_data_evidence(quality)       → d_score
    # 调 P1: evaluate_single_model(predictions)    → s_score
    # 调 P3: evaluate_multi_model(predictions)     → m_score
    # 调 P2: evaluate_physics(predictions)         → p_score
    
    total = d_score + s_score + m_score + p_score
    level, action = route(total)                  # P2 的函数
    
    return ReliabilityResult(risk_score=total, risk_level=level, ...)
```

**P1/P2/P3 还没写完时用占位函数**（try import, except 返回 0），不阻塞自己。

### 模块 3：`pipeline.py` — 主流程 + Demo

```python
def analyze_sample(sample_id, quality, predictions):
    """串联: 质量 → 模型 → 证据 → 引擎 → 结果"""

def demo_run():
    """三个模拟场景验证逻辑"""
    # 场景1: 正常 → LOW
    # 场景2: 模型打架 → HIGH
    # 场景3: 数据差 → HIGH
```

### 测试（4 个）

```python
# 场景1 → LOW, 场景2 → 不为LOW, 场景3 → 不为LOW, pipeline跑通
```

### 验收

```
□ schema.py 定稿（和全组确认）
□ reliability.py（含 route 占位 + enable 开关）
□ pipeline.py + demo 三个场景 ✅
□ push 到 dev-trust-engine
```

---

## 开工顺序

```
你 → schema.py 定稿（P1/P2/P3 等你这个）
P1/P2/P3 → 各自写证据模块（不互相等）
你 → reliability.py + pipeline.py（等 P1/P2/P3 给函数签名后集成）
```
