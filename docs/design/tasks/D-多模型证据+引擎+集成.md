# D 任务卡：多模型证据 + 可靠性引擎 + Pipeline 集成

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
  │   ├── multi_model        (0-40) ← 【你负责】 ★核心
  │   └── physics            (0-15) ← B 负责
  │
  ├── Reliability Engine（引擎层）
  │   └── evaluate_reliability()   ← 【你负责】
  │
  ├── Router（路由层）
  │   └── route()                  ← B 负责
  │
  └── Pipeline（主流程）
      └── analyze_sample()         ← 【你负责】
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
│   ├── multi_model.py              ← 【你负责】★
│   └── physics.py                  ← B 负责
├── engine/
│   └── reliability.py              ← 【你负责】主体 + B 负责 router()
├── pipeline.py                     ← 【你负责】
tests/
├── test_evidence.py                ← A + B + 【你(多模型部分)】
├── test_engine.py                  ← B
└── evaluate.py                     ← C 负责主体
config/
└── thresholds.yaml                 ← 【你 + C 共同维护】
```

### 完整步骤总览

```
M0 ✅ 已完成

M1 基础设施 — 所有模块写完 + 测试通过    ← 你现在在这里
  ├── 你: multi_model + reliability + pipeline
  ├── A: data_evidence + 最高置信度基线 + 测试
  ├── B: single_model + physics + router + 简单投票基线 + 测试
  └── C: 错误标准 + 评测框架 + 单模型基线

M2 核心开发 — 接入真实模型 + 调参 + 消融实验
  ├── 你: 接入 SeisBench 真实模型 + 全流程联调
  ├── A/B: 配合消融实验（模块可单独开关）
  └── C: 网格调参 + 消融实验 + 核心图表

M3 联调交付
  └── 全员: 配合联调 + 修 bug + 给文档组提供数据
```

---

## ⚠️ 阻塞关系（开工前必读）

```
你的 multi_model.py 不依赖任何人 → 可以立即开工 ✅

但你的 reliability.py 需要调 A 和 B 的函数：
  需要 A 的: evaluate_data_evidence()
  需要 B 的: evaluate_single_model(), evaluate_physics(), route()
→ 和 A/B 提前约定函数签名 → 先用占位函数写框架 → Day2 拿到初版后联调

你的 pipeline.py 需要 reliability.py → Day3 集成
```

### 开工顺序

```
第1天 (无依赖):  multi_model.py ← 全力写。同时告诉 A/B 函数签名约定
第2天 (集成):    reliability.py ← A/B 交付初版后立即联调
第3天 (联调):    pipeline.py + demo 跑通 + 全员测试
```

---

## 你负责的部分 → 属于 M1

```
src/evidence/
└── multi_model.py          ← 【你负责】★ 核心 (0-40 分)

src/engine/
└── reliability.py          ← 【你负责】主体（B 帮你写 router()）

src/
└── pipeline.py             ← 【你负责】串联所有模块
```

### 你的核心：多模型证据

```
输入: List[ModelPrediction] (OBSTransformer + PhaseNet 的 P/S 预测)
                            │
                            ▼
              ┌─────────────────────────┐
              │  multi_model.py         │
              │  1. 按 phase 分组        │
              │     P: [12.30, 12.42]   │
              │     S: [25.50, 25.62]   │
              │  2. 组内算时间差         │
              │     P: |30-42|=0.12s    │
              │  3. 判断一致程度         │
              │     ≤0.3s → CONSENSUS   │
              │     >1.0s → SEVERE      │
              │  4. 打分 0-40           │
              └─────────────────────────┘
                            │
                            ▼
输出: (score: 0-40, reasons: [str])
```

---

## M1 步骤

### 1. 写 `multi_model.py` ★

```python
def evaluate_multi_model(
    predictions: List[ModelPrediction],
    p_tolerance_s: float = 0.3,
    s_tolerance_s: float = 0.5
) -> Tuple[float, List[str]]:
    """
    多模型交叉验证 — Trust Layer 的核心证据 (满分 40)
    """
    pass
```

**打分规则**：

```
按震相分组:
  p_preds = [p for p in predictions if p.phase == "P" and p.time_s > 0]
  s_preds = [p for p in predictions if p.phase == "S" and p.time_s > 0]

P 波分歧:
  全漏了 P           → +15, ALL_MISSING_P
  ≥2 模型差 > 1.0s  → +20, DISAGREEMENT_P
  ≥2 模型差 > 0.3s  → +8,  MILD_DISAGREEMENT

S 波同理 (容差 0.5s, 严重阈值 2.0s)

有模型漏检但不是全漏 → +10, MODEL_MISSING_PICK
全一致             → 0,   MODEL_CONSENSUS
上限               = min(score, 40)
```

**四类场景验证**：

```
场景 A: P=12.30, 12.42 (差0.12s) → 0分, CONSENSUS
场景 B: P=12.30, 18.70 (差6.4s)  → 20分, DISAGREEMENT_P
场景 C: A检出P/S, B全漏           → 30分 (15+15)
场景 D: A检出, B漏了S             → 10分, MODEL_MISSING_PICK
```

---

### 2. 写 `reliability.py`

```python
def evaluate_reliability(
    quality: QualityReport,
    predictions: List[ModelPrediction]
) -> ReliabilityResult:
    """主入口: QualityReport + ModelPrediction[] → ReliabilityResult"""
    
    # 调 A/B/自己的四个证据函数
    d_score, d_reasons = evaluate_data_evidence(quality)       # A 写的
    s_score, s_reasons = evaluate_single_model(predictions)    # B 写的
    m_score, m_reasons = evaluate_multi_model(predictions)     # 你写的
    p_score, p_reasons = evaluate_physics(predictions)         # B 写的

    total = d_score + s_score + m_score + p_score
    level, action = route(total)                               # B 写的

    return ReliabilityResult(
        risk_score=round(total, 1),
        risk_level=level, action=action,
        reason_codes=四个原因码列表合并,
        evidence_summary=生成人类可读总结,
    )
```

---

### 3. 写 `pipeline.py`

```python
def analyze_sample(sample_id, waveform, meta, adapters=None) -> SampleAnalysis:
    """单个样本完整分析: Data → Quality → Models → Evidence → Engine → Result"""

def demo_run():
    """M1用模拟数据验证完整流程"""
    # 场景1: 正常 → LOW → ACCEPT
    # 场景2: 模型打架 → HIGH → ABSTAIN
    # 场景3: 数据质量差 → HIGH → ABSTAIN
```

---

### 4. 测试

```python
# 加到 tests/test_evidence.py

def test_multi_consensus():
    preds = [ModelPrediction("A", "P", 12.30), ModelPrediction("B", "P", 12.42),
             ModelPrediction("A", "S", 25.50), ModelPrediction("B", "S", 25.62)]
    score, reasons = evaluate_multi_model(preds)
    assert score == 0 and "MODEL_CONSENSUS" in reasons

def test_multi_disagreement():
    preds = [ModelPrediction("A", "P", 12.30), ModelPrediction("B", "P", 18.70)]
    score, _ = evaluate_multi_model(preds)
    assert score >= 20

def test_multi_missing():
    preds = [ModelPrediction("A", "P", 12.30)]
    score, _ = evaluate_multi_model(preds)
    assert score >= 10

def test_pipeline_demo():
    demo_run()
```

---

### 5. M1 验收标准

```
□ multi_model.py 写毕 + 测试 3 个 ✅
□ reliability.py 写毕（含 B 的 router）
□ pipeline.py demo 跑通（三个场景输出正确）
□ push 到 GitHub
```

---

## M2

```
□ 和数据组联调 SeisBench → pipeline.py 接入真实模型
□ 用真实 YM 数据跑通全流程 → 输出 reliability.json
□ 和展示组确认 JSON 格式
□ thresholds 改成读 config/thresholds.yaml
□ evaluate_reliability() 加 enable 开关，配合 C 消融实验
```

---

## M3

```
□ 全流程联调（Data → Model → Trust Engine → 展示组）
□ 代码冻结 + 确保 run_demo.py 一键跑通
□ 给文档组提供技术细节
```

---
