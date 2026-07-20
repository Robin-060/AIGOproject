"""
主流程 — 串联所有模块 + Demo

负责人: D

用法:
    python src/pipeline.py                  # Demo 演示
    python src/pipeline.py --input data.npy  # 单样本分析
"""

import numpy as np
import json
import sys

from src.schema import (
    SampleAnalysis, WaveformInfo, QualityReport,
    ModelPrediction, ReliabilityResult
)
from src.engine.reliability import evaluate_reliability


def analyze_sample(
    sample_id: str,
    waveform: np.ndarray,
    meta: dict = None,
    quality: QualityReport = None,
    predictions: list = None,
) -> SampleAnalysis:
    """
    单个样本的完整分析流程

    Args:
        sample_id: 样本标识
        waveform: 波形数据 (n_samples, n_channels)
        meta: 元信息 {"channels": [...], "sampling_rate": 100.0, ...}
        quality: 数据质量报告 (数据组提供)
        predictions: 模型预测列表 (数据组提供)

    Returns:
        SampleAnalysis
    """
    if meta is None:
        meta = {}

    # 1. 波形元信息
    info = WaveformInfo(
        station=meta.get("station", ""),
        network=meta.get("network", ""),
        channels=meta.get("channels", []),
        sampling_rate=meta.get("sampling_rate", 100.0),
        start_time=meta.get("start_time", ""),
        duration_s=waveform.shape[0] / meta.get("sampling_rate", 100.0),
    )

    # 2. 数据质量 (数据组提供，无则给空)
    if quality is None:
        quality = QualityReport()

    # 3. 模型预测 (数据组提供)
    if predictions is None:
        predictions = []

    # 4. 可靠性评估
    reliability = evaluate_reliability(quality, predictions)

    return SampleAnalysis(
        sample_id=sample_id,
        waveform_info=info,
        quality=quality,
        predictions=predictions,
        reliability=reliability,
    )


# ═══════════════════════════════════════════════════════════
# Demo — 模拟数据验证完整流程
# ═══════════════════════════════════════════════════════════

def demo_run():
    """用模拟数据跑三个典型场景"""
    emoji = {"LOW": "✅ 低风险", "MEDIUM": "⚠️ 中风险", "HIGH": "❌ 高风险"}
    bar = "=" * 60

    print(f"\n{bar}")
    print("  OBS 可信AI调度层 — Trust Engine Demo")
    print(f"{bar}")

    # ── 场景 1: 一切正常 ──────────────────────────────
    print("\n[场景 1] 数据正常 + 两模型一致 → 应自动通过")

    quality1 = QualityReport(
        missing_channels=[], gap_ratio=0.0,
        clipping_ratio=0.01, snr_db=15.0
    )
    predictions1 = [
        ModelPrediction("OBSTransformer", "0.1.0", "P", 12.30, 0.91, "W01"),
        ModelPrediction("OBSTransformer", "0.1.0", "S", 25.50, 0.85, "W01"),
        ModelPrediction("PhaseNet", "original", "P", 12.42, 0.88, "W01"),
        ModelPrediction("PhaseNet", "original", "S", 25.62, 0.82, "W01"),
    ]
    result1 = analyze_sample("S001_NORMAL", np.zeros((6000,3)),
                              quality=quality1, predictions=predictions1)

    print(f"  数据: {result1.quality.summary()}")
    print(f"  风险: {result1.reliability.risk_score}/100 "
          f"→ {emoji.get(result1.reliability.risk_level, '?')}")
    print(f"  动作: {result1.reliability.action}")
    print(f"  原因: {result1.reliability.reason_codes}")

    # ── 场景 2: 模型严重分歧 ──────────────────────────
    print("\n[场景 2] 两模型 P 波差 6 秒 → 应拒绝自动处理")

    quality2 = QualityReport(
        missing_channels=[], gap_ratio=0.0,
        clipping_ratio=0.0, snr_db=12.0
    )
    predictions2 = [
        ModelPrediction("OBSTransformer", "0.1.0", "P", 12.30, 0.91, "W02"),
        ModelPrediction("OBSTransformer", "0.1.0", "S", 25.50, 0.85, "W02"),
        ModelPrediction("PhaseNet", "original", "P", 18.70, 0.92, "W02"),  # 差 6.4s!
        ModelPrediction("PhaseNet", "original", "S", 30.80, 0.80, "W02"),
    ]
    result2 = analyze_sample("S002_DISAGREE", np.zeros((6000,3)),
                              quality=quality2, predictions=predictions2)

    print(f"  数据: {result2.quality.summary()}")
    print(f"  风险: {result2.reliability.risk_score}/100 "
          f"→ {emoji.get(result2.reliability.risk_level, '?')}")
    print(f"  动作: {result2.reliability.action}")
    print(f"  原因: {result2.reliability.reason_codes}")

    # ── 场景 3: 数据质量差 ────────────────────────────
    print("\n[场景 3] 缺通道 + 低信噪比 → 应拒绝自动处理")

    quality3 = QualityReport(
        missing_channels=["BH1", "BH2"], gap_ratio=0.0,
        clipping_ratio=0.0, snr_db=1.8
    )
    predictions3 = [
        ModelPrediction("OBSTransformer", "0.1.0", "P", 10.00, 0.40, "W03"),
    ]
    result3 = analyze_sample("S003_BAD_DATA", np.zeros((6000,3)),
                              quality=quality3, predictions=predictions3)

    print(f"  数据: {result3.quality.summary()}")
    print(f"  风险: {result3.reliability.risk_score}/100 "
          f"→ {emoji.get(result3.reliability.risk_level, '?')}")
    print(f"  动作: {result3.reliability.action}")
    print(f"  原因: {result3.reliability.reason_codes}")

    # ── 验证结果 ─────────────────────────────────────
    print(f"\n{bar}")
    errors = []
    if result1.reliability.risk_level != "LOW":
        errors.append("场景1 应为 LOW")
    if result2.reliability.risk_level == "LOW":
        errors.append("场景2 不应为 LOW")
    if result3.reliability.risk_level == "LOW":
        errors.append("场景3 不应为 LOW")

    if errors:
        for e in errors:
            print(f"  ❌ {e}")
    else:
        print("  ✅ 三个场景全部通过!")
        print("  Trust Engine 核心逻辑验证成功")
    print(f"{bar}\n")

    # 场景1 的完整 JSON
    if "--json" in sys.argv:
        print("\n场景1 完整输出:\n")
        print(result1.to_json())


if __name__ == "__main__":
    demo_run()
