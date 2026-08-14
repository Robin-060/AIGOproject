"""
消融实验 — 基于 P3 的真实 SeisBench 预测数据

逐一关闭四类证据，观察错误放行率变化。
数据源: phase3 的 docs/experiments/noise_predictions_seisbench.json (真实三模型推理)

用法:
    python -m src.experiments.real_ablation
"""

import json
from pathlib import Path
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.trust_engine.schema import (
    SampleMetadata, QualityReport, ModelPrediction, ModelProfile,
    AdapterStatus, TrustConfig, ModelSuitability, PhysicsCheck,
)
from src.trust_engine.reliability import evaluate_reliability
from src.trust_engine.data_evidence import evaluate_data_evidence
from src.trust_engine.model_suitability import evaluate_model_suitability
from src.trust_engine.single_model import evaluate_single_model_evidence
from src.trust_engine.physics import check_model_prediction
from src.trust_engine.multi_model import analyze_multi_model_consensus
from src.trust_engine.fusion import build_fusion_candidates

PRED_PATH = Path("data/phase3/noise_predictions_seisbench.json")
TRUTH_PATH = Path("data/phase3/noise_records_seisbench.csv")
OUT_DIR = Path("docs/experiments")
OUT_DIR.mkdir(parents=True, exist_ok=True)

P_TOL = 0.5
S_TOL = 1.0

PROFILES = [
    ModelProfile(model_name="PhaseNet", required_channels=["Z", "N", "E"],
                 accepted_sampling_rates_hz=[100.0], resampling_supported=True,
                 required_preprocessing_version="seisbench_v0.12"),
    ModelProfile(model_name="PickBlue", required_channels=["Z", "N", "E", "H"],
                 accepted_sampling_rates_hz=[100.0], resampling_supported=True,
                 required_preprocessing_version="seisbench_v0.12"),
    ModelProfile(model_name="OBSTransformer", required_channels=["H"],
                 preferred_channels=["Z", "N", "E"],
                 accepted_sampling_rates_hz=[100.0], resampling_supported=True,
                 required_preprocessing_version="seisbench_v0.12"),
]

ADAPTERS = [
    AdapterStatus(model_name=m, loaded=True, run_succeeded=True, output_comparable=True)
    for m in ("PhaseNet", "PickBlue", "OBSTransformer")
]


def load_data():
    """载入 P3 的真实预测 + 真值 (L0 档)"""
    with open(PRED_PATH, "r", encoding="utf-8") as f:
        preds_raw = json.load(f)
    with open(TRUTH_PATH, "r", encoding="utf-8") as f:
        import csv
        truth_raw = list(csv.DictReader(f))

    # 真值表: (sample_id, noise_level) → {truth_p_s, truth_s_s}
    truth_map = {}
    for row in truth_raw:
        key = (row["sample_id"], row["noise_level"])
        if key not in truth_map:
            truth_map[key] = {
                "P": float(row["truth_p_s"]) if row["truth_p_s"] else None,
                "S": float(row["truth_s_s"]) if row["truth_s_s"] else None,
            }

    # 按 (sample_id, noise_level) 分组预测
    groups = defaultdict(list)
    for p in preds_raw:
        groups[(p["sample_id"], p["noise_level"])].append(p)

    samples = []
    for key, preds in groups.items():
        if key not in truth_map:
            continue
        truth = truth_map[key]
        if truth["P"] is None or truth["S"] is None:
            continue
        samples.append({
            "sample_id": key[0],
            "noise_level": key[1],
            "predictions": [
                ModelPrediction(**{k: v for k, v in p.items()
                                   if k != "noise_level"})
                for p in preds
            ],
            "ground_truth": truth,
        })
    return samples


def run_trust_layer(sample, enable=None):
    config = TrustConfig()
    meta = SampleMetadata(
        sample_id=sample["sample_id"], data_source="REAL",
        preprocessing_version="seisbench_v0.12",
    )
    quality = QualityReport(
        available_channels=["Z", "N", "E", "H"],
        missing_channels=[],
        snr_db={"L0": 20.0, "L1": 10.0, "L2": 5.0, "L3": 2.0}[sample["noise_level"]],
        source="REAL_CALCULATION",
    )
    preds = sample["predictions"]

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

    cons = analyze_multi_model_consensus(preds, suits, physics)
    fusions = build_fusion_candidates(preds, cons)

    return evaluate_reliability(
        meta, quality, PROFILES, preds,
        config, data_ev, suits, singles, physics, cons, fusions,
        enable=enable,
    )


def evaluate(sample, result):
    """判定: correct / wrong(不安全错误) / reject"""
    p_d = result.phase_decisions.get("P")
    s_d = result.phase_decisions.get("S")
    if not p_d or not s_d:
        return "reject"
    if p_d.action == "ABSTAIN" or s_d.action == "ABSTAIN":
        return "reject"
    if p_d.selected_time_s is None or s_d.selected_time_s is None:
        return "reject"
    p_ok = abs(p_d.selected_time_s - sample["ground_truth"]["P"]) <= P_TOL
    s_ok = abs(s_d.selected_time_s - sample["ground_truth"]["S"]) <= S_TOL
    return "correct" if (p_ok and s_ok) else "wrong"


def main():
    samples = load_data()
    print(f"载入 {len(samples)} 条真实样本 (L0-L3)\n")

    ablation_configs = {
        "Full": None,
        "No Data": {"data": False, "single_model": True, "multi_model": True, "physics": True},
        "No Single": {"data": True, "single_model": False, "multi_model": True, "physics": True},
        "No Multi": {"data": True, "single_model": True, "multi_model": False, "physics": True},
        "No Physics": {"data": True, "single_model": True, "multi_model": True, "physics": False},
    }

    results = {}
    for name, enable in ablation_configs.items():
        stats = {"correct": 0, "wrong": 0, "reject": 0}
        for sample in samples:
            r = run_trust_layer(sample, enable)
            verdict = evaluate(sample, r)
            stats[verdict] += 1
        results[name] = stats
        total = stats["correct"] + stats["wrong"] + stats["reject"]
        wrong_rate = stats["wrong"] / total if total else 0
        safe_rate = (stats["correct"] + stats["reject"]) / total if total else 0
        print(f"  {name:12s} 错误放行={wrong_rate:.1%} 安全率={safe_rate:.1%} "
              f"(正确={stats['correct']} 错误={stats['wrong']} 拒绝={stats['reject']})")

    # 画图
    names = list(results.keys())
    wrong_rates = []
    for name in names:
        r = results[name]
        total = r["correct"] + r["wrong"] + r["reject"]
        wrong_rates.append(r["wrong"] / total if total else 0)

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(names, wrong_rates, color="#4CAF50")
    ax.set_ylabel("Wrong-pass rate (higher = evidence matters more)")
    ax.set_title("Ablation on Real SeisBench Predictions (L0-L3, 80 windows)")
    for bar, v in zip(bars, wrong_rates):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005,
                f"{v:.1%}", ha="center", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "real_ablation.png", dpi=150)
    plt.close(fig)
    print(f"\n✅ 图已保存 → {OUT_DIR / 'real_ablation.png'}")


if __name__ == "__main__":
    main()
