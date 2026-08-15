"""
基线对比实验 — 基于 895 条真实标注数据

对比四种方法在真实数据上的错误放行率:
  1. 单模型 (OBSTransformer)
  2. 最高置信度
  3. 简单投票
  4. Trust Layer

数据: data/batch_calibration/records_all.json (895 条, 官方 P/S 标注)

用法:
    python -m src.experiments.real_baseline_final
"""

import json
import statistics
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RECORDS_PATH = Path("data/batch_calibration/records_all.json")
OUT_DIR = Path("docs/experiments")
OUT_DIR.mkdir(parents=True, exist_ok=True)

P_TOL = 0.5
S_TOL = 1.0


def load_records():
    with open(RECORDS_PATH, encoding="utf-8") as f:
        return json.load(f)


def evaluate_pair(record, p_time, s_time):
    """判定一个 P/S 对: correct / wrong / reject"""
    if p_time is None or s_time is None:
        return "reject"
    gt_p, gt_s = record["truth_p_s"], record["truth_s_s"]
    if gt_p is None or gt_s is None:
        return None  # 无完整真值, 不计入
    p_ok = abs(p_time - gt_p) <= P_TOL
    s_ok = abs(s_time - gt_s) <= S_TOL
    return "correct" if (p_ok and s_ok) else "wrong"


# ── 三种基线 ──

def baseline_single(record, model="OBSTransformer"):
    v = record["predictions"].get(model, {})
    return v.get("P_pick"), v.get("S_pick")


def baseline_max_conf(record):
    p_cands = [(m, v["P_pick"], v.get("confidence") or 0)
               for m, v in record["predictions"].items() if v.get("P_pick") is not None]
    s_cands = [(m, v["S_pick"], v.get("confidence") or 0)
               for m, v in record["predictions"].items() if v.get("S_pick") is not None]
    p_best = max(p_cands, key=lambda x: x[2])[1] if p_cands else None
    s_best = max(s_cands, key=lambda x: x[2])[1] if s_cands else None
    return p_best, s_best


def baseline_vote(record):
    p_times = [v["P_pick"] for v in record["predictions"].values() if v.get("P_pick") is not None]
    s_times = [v["S_pick"] for v in record["predictions"].values() if v.get("S_pick") is not None]
    p_med = statistics.median(p_times) if p_times else None
    s_med = statistics.median(s_times) if s_times else None
    return p_med, s_med


# ── Trust Layer ──

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


def trust_layer_pick(record):
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
        return None, None

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

    p_d = result.phase_decisions.get("P")
    s_d = result.phase_decisions.get("S")
    if not p_d or not s_d or p_d.action == "ABSTAIN" or s_d.action == "ABSTAIN":
        return None, None
    if p_d.selected_time_s is None or s_d.selected_time_s is None:
        return None, None
    return p_d.selected_time_s, s_d.selected_time_s


def main():
    records = load_records()
    print(f"真实标注样本: {len(records)}")

    methods = {
        "Single (OBST)": baseline_single,
        "Max-Conf": baseline_max_conf,
        "Voting": baseline_vote,
        "Trust Layer": trust_layer_pick,
    }

    results = {}
    for name, fn in methods.items():
        stats = {"correct": 0, "wrong": 0, "reject": 0}
        for r in records:
            p, s = fn(r)
            verdict = evaluate_pair(r, p, s)
            if verdict:
                stats[verdict] += 1
        results[name] = stats
        total = sum(stats.values())
        wr = stats["wrong"] / total if total else 0
        print(f"  {name:14s} 正确={stats['correct']:3d} 错误={stats['wrong']:3d} "
              f"拒绝={stats['reject']:3d} 错误放行率={wr:.1%}")

    # 画图
    names = list(results.keys())
    wrong_rates = []
    for name in names:
        s = results[name]
        total = sum(s.values())
        wrong_rates.append(s["wrong"] / total if total else 0)

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = ["#F44336", "#FF9800", "#2196F3", "#4CAF50"]
    bars = ax.bar(names, wrong_rates, color=colors, width=0.55)
    ax.set_ylabel("Wrong-pass rate (lower is better)")
    ax.set_title(f"Baseline Comparison on Real Labelled Data (n={len(records)})")
    for bar, v in zip(bars, wrong_rates):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.002,
                f"{v:.1%}", ha="center", fontsize=12, fontweight="bold")
    ax.set_ylim(0, max(wrong_rates) * 1.3 + 0.02)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "real_baseline.png", dpi=150)
    plt.close(fig)
    print(f"\n✅ 图已保存 → {OUT_DIR / 'real_baseline.png'}")


if __name__ == "__main__":
    main()
