# A 任务卡：数据证据 + 最高置信度基线

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
  │   ├── data_evidence      (0-30) ← 【你负责】
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
│   ├── data_evidence.py            ← 【你负责】
│   ├── single_model.py             ← B 负责
│   ├── multi_model.py              ← D 负责 ★
│   └── physics.py                  ← B 负责
├── engine/
│   └── reliability.py              ← D + B
├── pipeline.py                     ← D 负责
tests/
├── test_evidence.py                ← 【你】+ B + D
├── test_engine.py                  ← B
└── evaluate.py                     ← 【你(最高置信度基线)】+ C
config/
└── thresholds.yaml                 ← D + C
```

### 完整步骤总览

```
M0 ✅ 已完成

M1 基础设施 — 所有模块写完 + 测试通过    ← 你现在在这里
  ├── 你: data_evidence + 最高置信度基线 + 测试
  ├── B: single_model + physics + router + 简单投票基线 + 测试
  ├── C: 错误标准 + 评测框架 + 单模型基线
  └── D: multi_model + reliability + pipeline

M2 核心开发 — 接入真实模型 + 调参 + 消融实验
  ├── 你 + B: 配合消融实验（模块可单独开关）
  ├── C: 网格调参 + 消融实验 + 核心图表
  └── D: 接入 SeisBench 真实模型

M3 联调交付
  └── 全员: 配合联调 + 修 bug + 给文档组提供数据
```

---

## ⚠️ 阻塞关系（开工前必读）

```
你不依赖任何人 → 可以立即开工

但 D 的 reliability.py 需要调你的 evaluate_data_evidence()
→ 你写完函数签名后立刻通知 D
→ 不用等完美版，先给函数签名 + 初版即可

你的 baseline_max_confidence 需要加到 C 的 evaluate.py
→ C 先建好 evaluate.py 框架 → 你往里加
```

### 开工顺序

```
第1天 (无依赖):  data_evidence.py  ← 全力写
第2天 (交付):    写完 + 测试通过 → 通知 D 和 C
第3天 (联调):    配合 D 联调 reliability.py
```

---

## 你负责的部分 → 属于 M1

```
模块 1: src/evidence/data_evidence.py     ← 数据质量 → 风险分 (0-30)
模块 2: tests/evaluate.py 中的 baseline_max_confidence()  ← 最高置信度基线

tests/
└── test_evidence.py          ← 你负责（测 data_evidence, 5 个测试用例）
```

### 模块 1：数据证据

```
输入: QualityReport              输出: (score: 0-30, reasons: [str])
(M1 数据组还没就绪？先用模拟数据)
      │                                   │
      ▼                                   ▼
data_evidence.py:                  "数据没问题"     → 0 分
  缺道? 断点? 削波? SNR?           "缺 1 个通道"    → 12 分
                                   "噪声大 + 断点"  → 23 分
```

---

## M1 步骤

### 1. 写 `src/evidence/data_evidence.py`

```python
def evaluate_data_evidence(quality: QualityReport) -> Tuple[float, List[str]]:
    """根据数据质量报告给风险打分 (满分 30)"""
    pass
```

**打分规则**：

| 检查项 | 条件 | 加分 | 原因码 |
|--------|------|------|--------|
| 缺通道 | 缺 ≥2 个 | +20 | `CHANNEL_MULTI_MISSING` |
| 缺通道 | 缺 1 个 | +12 | `CHANNEL_MISSING` |
| 断点严重 | gap_ratio > 0.1 | +15 | `GAP_SEVERE` |
| 断点中等 | gap_ratio > 0.02 | +8 | `GAP_MODERATE` |
| 削波严重 | clipping_ratio > 0.1 | +10 | `CLIPPING_SEVERE` |
| 削波中等 | clipping_ratio > 0.02 | +5 | `CLIPPING_MODERATE` |
| 低信噪比 | snr_db < 3.0 | +15 | `LOW_SIGNAL` |
| 中信噪比 | snr_db < 8.0 | +8 | `MODERATE_SIGNAL` |
| 采样率不对 | sampling_rate_ok == False | +5 | `SAMPLING_RATE_MISMATCH` |
| 一切正常 | 上面都不触发 | 0 | `DATA_QUALITY_OK` |

最后 `return (min(score, 30), reasons)`。

---

### 2. 写测试（5 个测试用例）

加到 `tests/test_evidence.py`：

```python
from src.schema import QualityReport
from src.evidence.data_evidence import evaluate_data_evidence


def test_data_normal():
    """一切正常 → 0 分"""
    q = QualityReport(missing_channels=[], gap_ratio=0.0,
                       clipping_ratio=0.0, snr_db=20.0)
    score, reasons = evaluate_data_evidence(q)
    assert score == 0
    assert "DATA_QUALITY_OK" in reasons


def test_data_missing_channel():
    """缺 1 个通道 → ≥ 12 分"""
    q = QualityReport(missing_channels=["BH1"], gap_ratio=0.0,
                       clipping_ratio=0.0, snr_db=20.0)
    score, reasons = evaluate_data_evidence(q)
    assert score >= 12
    assert "CHANNEL_MISSING" in reasons


def test_data_low_snr():
    """低信噪比 → ≥ 15 分"""
    q = QualityReport(missing_channels=[], gap_ratio=0.0,
                       clipping_ratio=0.0, snr_db=1.5)
    score, _ = evaluate_data_evidence(q)
    assert score >= 15


def test_data_combined():
    """缺 2 通道 + 断点 + 削波 + 低SNR → 被截断到 30"""
    q = QualityReport(missing_channels=["BH1", "BH2"],
                       gap_ratio=0.5, clipping_ratio=0.3, snr_db=2.0)
    score, _ = evaluate_data_evidence(q)
    assert score == 30


def test_data_gap():
    """中等断点 → ≥ 8 分"""
    q = QualityReport(missing_channels=[], gap_ratio=0.05,
                       clipping_ratio=0.0, snr_db=20.0)
    score, _ = evaluate_data_evidence(q)
    assert score >= 8


if __name__ == "__main__":
    test_data_normal();         print("✅ test_data_normal")
    test_data_missing_channel(); print("✅ test_data_missing_channel")
    test_data_low_snr();         print("✅ test_data_low_snr")
    test_data_combined();        print("✅ test_data_combined")
    test_data_gap();             print("✅ test_data_gap")
    print("\n🎉 全部通过！")
```

---

### 3. 写最高置信度基线

在 `tests/evaluate.py` 中追加（C 创建文件框架，你往里加这个函数）：

```python
def baseline_max_confidence(predictions_per_sample: Dict) -> Dict:
    """
    基线: 每个样本选择 score 最高的模型结果
    决策逻辑: 遍历所有模型预测 → 取 score 最大的
    """
    results = {}
    for sample_id, predictions in predictions_per_sample.items():
        if not predictions:
            results[sample_id] = None
            continue
        
        # 按 phase 分组，每组选 score 最高的
        p_preds = [p for p in predictions if p.phase == "P"]
        s_preds = [p for p in predictions if p.phase == "S"]
        
        best_p = max(p_preds, key=lambda x: x.score) if p_preds else None
        best_s = max(s_preds, key=lambda x: x.score) if s_preds else None
        
        results[sample_id] = {"P": best_p, "S": best_s}
    
    return results
```

---

### 4. M1 验收标准

```
□ data_evidence.py 写毕 → 5 个测试 ✅
□ baseline_max_confidence 写毕 → 逻辑验证通过
□ push 到 GitHub
□ 四人对等 review 通过
```

---

## M2 接续

```
□ data_evidence 加 enable 开关（配合 C 消融实验）
□ baseline_max_confidence 用于 C 的对比实验
```

---
