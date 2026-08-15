"""
风险校准曲线 — 风险分 vs 实际错误率

验证风险评分体系的有效性: 风险分越高, 实际错误率越高(单调递增)。
数据: data/batch_calibration/records_all.json (895 条真实标注)

用法:
    python -m src.experiments.risk_calibration_curve
"""

import json
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.trust_engine.schema import (
    SampleMetadata, QualityReport, ModelPrediction, ModelProfile,
    AdapterStatus, TrustConfig,
)
from src.trust_engine.reliability import evaluate_reliability
from src.trust_engine.data_evidence import evaluate_data_evidence
from src.trust_engine.model_suitability import evaluate_model_suitability
from src.trust_engine.single_model import evaluate_single_model_evidence
from src.trust_engine.physics import check_model_prediction
from src.trust_engine.multi_model import analyze_multi_model_consensus
from src.trust_engine.fusion import build_fusion_candidates

RECORDS_PATH = Path("data/batch_calibration/records_all.json")
OUT_DIR = Path("docs/experiments")
OUT_DIR.mkdir(parents=True, exist_ok=True)

P_TOL = 0.5
S_TOL = 1.0

PROFILES = [
    ModelProfile(model_name="PhaseNet", required_channels=["Z", "N", "E"],
                 accepted_sampling_rates_hz=[100.0], resampling_supported=True,
                 required_preprocessing_version="synthetic_v1"),
    ModelProfile(model_name="PickBlue", required_channels=["Z", "N", "E", "H"],
                 accepted_sampling_rates_hz=[100.0], resampling_supported=True,
                 required_preprocessing_version="synthetic_v1"),
    ModelProfile(model_name="OBSTransformer", required_channels=["H"],
                 preferred_channels=["Z", "N", "E"],
                 accepted_sampling_rates_hz=[100.0], resampling_supported=True,
                 required_preprocessing_version="synthetic_v1"),
]
ADAPTERS = [
    AdapterStatus(model_name=m, loaded=True, run_succeeded=True, output_comparable=True)
    for m in ("PhaseNet", "PickBlue", "OBSTransformer")
]


def compute_risk(record):
    """返回 (风险分, 是否含错误拾取)"""
    preds = [
        ModelPrediction(
            sample_id=record["sample_id"], model_name=m, phase=ph,
            time_s=v[f"{ph}_pick"], score=v.get("confidence"),
            adapter_status="OK", preprocessing_version="synthetic_v1",
            prediction_source="REAL_MODEL",
        )
        for m, v in record["predictions"].items()
        for ph in ("P", "S") if v.get(f"{ph}_pick") is not None
    ]
    if not preds:
        return None

    meta = SampleMetadata(sample_id=record["sample_id"], data_source="REAL",
                          preprocessing_version="synthetic_v1")
    quality = QualityReport(available_channels=["Z", "N", "E", "H"],
                            missing_channels=[], snr_db=20.0,
                            source="REAL_CALCULATION")
    config = TrustConfig()
    data_ev = evaluate_data_evidence(quality)
    suits = evaluate_model_suitability(meta, quality, PROFILES, ADAPTERS)
    singles = evaluate_single_model_evidence(preds)

    physics = []
    seen = set()
    for p in preds:
        if p.model_name in seen:
            continue
        seen.add(p.model_name)
        p_ps = [x for x in preds if x.model_name == p.model_name and x.phase == "P"]
        s_ps = [x for x in preds if x.model_name == p.model_name and x.phase == "S"]
        physics.append(check_model_prediction(
            p_ps[0] if p_ps else None, s_ps[0] if s_ps else None,
            config, target_id=p.model_name,
        ))
    cons = analyze_multi_model_consensus(preds, suits, physics, config)
    fusions = build_fusion_candidates(preds, cons)
    result = evaluate_reliability(
        meta, quality, PROFILES, preds,
        config, data_ev, suits, singles, physics, cons, fusions,
    )

    # 模型错误标签
    wrong = 0
    for m, v in record["predictions"].items():
        for ph in ("P", "S"):
            t = v.get(f"{ph}_pick")
            gt = record.get(f"truth_{ph.lower()}_s")
            tol = P_TOL if ph == "P" else S_TOL
            if t is not None and gt is not None and abs(t - gt) > tol:
                wrong = 1

    return result.overall_risk_score, wrong


def main():
    with open(RECORDS_PATH, encoding="utf-8") as f:
        records = json.load(f)

    buckets = defaultdict(lambda: [0, 0])  # [错误数, 总数]
    for r in records:
        out = compute_risk(r)
        if out is None:
            continue
        risk, wrong = out
        b = int(risk // 10) * 10
        buckets[b][1] += 1
        buckets[b][0] += wrong

    xs, ys, counts = [], [], []
    for b in sorted(buckets):
        w, n = buckets[b]
        xs.append(b + 5)  # 桶中心
        ys.append(w / n if n else 0)
        counts.append(n)
        print(f"风险分 {b:2d}-{b+9:2d}: 错误率 {ys[-1]:5.1%} (n={n})")

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(xs, ys, "o-", color="#2196F3", linewidth=2.5, markersize=10)
    for x, y, n in zip(xs, ys, counts):
        ax.annotate(f"n={n}", (x, y), textcoords="offset points",
                    xytext=(0, 12), ha="center", fontsize=9, color="#666")
    ax.set_xlabel("Risk Score")
    ax.set_ylabel("Actual Model Error Rate")
    ax.set_title("Risk Calibration: Risk Score vs Actual Error Rate")
    ax.grid(alpha=0.3)
    ax.set_ylim(0, 1.05)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "risk_calibration_curve.png", dpi=150)
    plt.close(fig)
    print(f"\n✅ 图已保存 → {OUT_DIR / 'risk_calibration_curve.png'}")


if __name__ == "__main__":
    main()
