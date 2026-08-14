"""
真实预测版基线对比 + 消融实验 (帮 P2 完成)

用 data/synthetic/trust_input.json (真实三模型推理结果) 跑:
  1. 基线对比: 单模型 / 最高置信度 / 简单投票 / Trust Layer
  2. 消融实验: 逐一关闭四证据

用法:
    python -m src.experiments.real_baseline_ablation

产出:
    docs/experiments/real_risk_coverage.png
    docs/experiments/real_ablation.png
"""

import json
from pathlib import Path

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

TRUST_INPUT = Path("data/synthetic/trust_input.json")
OUT_DIR = Path("docs/experiments")
OUT_DIR.mkdir(parents=True, exist_ok=True)

P_TOLERANCE = 0.5
S_TOLERANCE = 1.0

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

# 严格版 (原默认) vs 放宽版
STRICT_CONFIG = TrustConfig()
RELAXED_CONFIG = TrustConfig(
    automatic_risk_threshold=60.0,   # 原30: 风险≤60 允许自动处理
    risk_low_max=45.0,               # 原30
    risk_medium_max=75.0,            # 原60
)

ADAPTERS = [
    AdapterStatus(model_name=m, loaded=True, run_succeeded=True, output_comparable=True)
    for m in ("PhaseNet", "PickBlue", "OBSTransformer")
]


def load_samples():
    with open(TRUST_INPUT, "r", encoding="utf-8") as f:
        raw = json.load(f)
    samples = []
    for s in raw:
        if not s["predictions"]:
            continue  # 无模型检出的样本跳过
        samples.append({
            "metadata": SampleMetadata(**s["metadata"]),
            "quality": QualityReport(**s["quality"]),
            "predictions": [ModelPrediction(**p) for p in s["predictions"]],
            "ground_truth": {
                "P": _to_float(s["ground_truth"]["P_time_s"]),
                "S": _to_float(s["ground_truth"]["S_time_s"]),
            },
            "label": s["label"],
        })
    return samples


def _to_float(v):
    """标签里的空串/'-1' 转 None, 其余转 float"""
    if v in (None, "", "-1"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def run_trust_layer(sample, enable=None, config=None):
    """完整 Trust Layer 流水线"""
    if config is None:
        config = TrustConfig()
    data_ev = evaluate_data_evidence(sample["quality"])
    suits = evaluate_model_suitability(
        sample["metadata"], sample["quality"], PROFILES, ADAPTERS
    )
    singles = evaluate_single_model_evidence(sample["predictions"])

    physics = []
    seen = set()
    for p in sample["predictions"]:
        if p.model_name in seen:
            continue
        seen.add(p.model_name)
        p_ps = [x for x in sample["predictions"] if x.model_name == p.model_name and x.phase == "P"]
        s_ps = [x for x in sample["predictions"] if x.model_name == p.model_name and x.phase == "S"]
        physics.append(check_model_prediction(
            p_ps[0] if p_ps else None, s_ps[0] if s_ps else None,
            config, target_id=p.model_name,
        ))

    cons = analyze_multi_model_consensus(sample["predictions"], suits, physics)
    fusions = build_fusion_candidates(sample["predictions"], cons)

    return evaluate_reliability(
        sample["metadata"], sample["quality"], PROFILES, sample["predictions"],
        config, data_ev, suits, singles, physics, cons, fusions,
        enable=enable,
    )


def trust_layer_pick(result):
    """从 Trust Layer 结果取 P/S 时间对, ABSTAIN 视为拒绝"""
    p_d = result.phase_decisions.get("P")
    s_d = result.phase_decisions.get("S")
    if not p_d or not s_d or p_d.action == "ABSTAIN" or s_d.action == "ABSTAIN":
        return None, None
    return p_d.selected_time_s, s_d.selected_time_s


def evaluate_pick(sample, p_time, s_time):
    """对比真值: 返回 'correct' / 'wrong' / 'reject'"""
    if p_time is None or s_time is None:
        return "reject"
    gt_p, gt_s = sample["ground_truth"]["P"], sample["ground_truth"]["S"]
    if gt_p is None or gt_s is None:
        return None  # 无真值, 不计入
    p_ok = abs(p_time - gt_p) <= P_TOLERANCE
    s_ok = abs(s_time - gt_s) <= S_TOLERANCE
    return "correct" if (p_ok and s_ok) else "wrong"


# ═══════════════ 基线方法 ═══════════════

def baseline_single(sample, model="OBSTransformer"):
    p = next((x for x in sample["predictions"]
              if x.model_name == model and x.phase == "P"), None)
    s = next((x for x in sample["predictions"]
              if x.model_name == model and x.phase == "S"), None)
    return p.time_s if p else None, s.time_s if s else None


def baseline_max_conf(sample):
    for phase in ("P", "S"):
        cands = [x for x in sample["predictions"]
                 if x.phase == phase and x.score is not None]
        if not cands:
            return None, None
    p_best = max((x for x in sample["predictions"] if x.phase == "P" and x.score is not None),
                 key=lambda x: x.score)
    s_best = max((x for x in sample["predictions"] if x.phase == "S" and x.score is not None),
                 key=lambda x: x.score)
    return p_best.time_s, s_best.time_s


def baseline_vote(sample):
    import statistics
    p_times = [x.time_s for x in sample["predictions"] if x.phase == "P"]
    s_times = [x.time_s for x in sample["predictions"] if x.phase == "S"]
    if not p_times or not s_times:
        return None, None
    return statistics.median(p_times), statistics.median(s_times)


def run_method(samples, method_fn):
    """对一批样本跑一种方法, 统计正确/错误/拒绝"""
    correct = wrong = reject = 0
    for sample in samples:
        p, s = method_fn(sample)
        verdict = evaluate_pick(sample, p, s)
        if verdict == "correct":
            correct += 1
        elif verdict == "wrong":
            wrong += 1
        elif verdict == "reject":
            reject += 1
    return {"correct": correct, "wrong": wrong, "reject": reject}


def main():
    samples = load_samples()
    valid = [s for s in samples if s["ground_truth"]["P"] is not None]
    print(f"载入 {len(samples)} 条有效样本 (有预测), {len(valid)} 条有真值\n")

    # ── 基线对比 (严格 vs 放宽) ──
    methods = {
        "单模型(OBST)": lambda s: baseline_single(s),
        "最高置信度": baseline_max_conf,
        "简单投票": baseline_vote,
        "Trust Layer 严格": lambda s: trust_layer_pick(run_trust_layer(s, config=STRICT_CONFIG)),
        "Trust Layer 放宽": lambda s: trust_layer_pick(run_trust_layer(s, config=RELAXED_CONFIG)),
    }

    print("基线对比:")
    results = {}
    for name, fn in methods.items():
        r = run_method(valid, fn)
        results[name] = r
        total = r["correct"] + r["wrong"] + r["reject"]
        safe_rate = (r["correct"] + r["reject"]) / total if total else 0
        print(f"  {name:12s} 正确={r['correct']} 错误={r['wrong']} "
              f"拒绝={r['reject']} 安全处理率={safe_rate:.1%}")

    # ── 消融实验 ──
    print("\nAblation:")
    ablation_configs = {
        "Full": None,
        "NoData": {"data": False, "single_model": True, "multi_model": True, "physics": True},
        "NoSingle": {"data": True, "single_model": False, "multi_model": True, "physics": True},
        "NoMulti": {"data": True, "single_model": True, "multi_model": False, "physics": True},
        "NoPhysics": {"data": True, "single_model": True, "multi_model": True, "physics": False},
    }

    ablation = {}
    for name, enable in ablation_configs.items():
        r = run_method(valid, lambda s: trust_layer_pick(run_trust_layer(s, enable, config=RELAXED_CONFIG)))
        ablation[name] = r
        total = r["correct"] + r["wrong"] + r["reject"]
        wrong_rate = r["wrong"] / total if total else 0
        auto_rate = (r["correct"] + r["wrong"]) / total if total else 0
        print(f"  {name:10s} wrong={wrong_rate:.1%} auto={auto_rate:.1%} "
              f"(correct={r['correct']} wrong={r['wrong']} reject={r['reject']})")

    # ── 图 1: 基线对比 ──
    fig, ax = plt.subplots(figsize=(9, 5))
    names = list(results.keys())
    wrong_rates = []
    for name in names:
        r = results[name]
        total = r["correct"] + r["wrong"] + r["reject"]
        wrong_rates.append(r["wrong"] / total if total else 0)
    bars = ax.bar(names, wrong_rates, color=["#F44336", "#FF9800", "#2196F3", "#9E9E9E", "#4CAF50"])
    ax.set_ylabel("Wrong-pass rate (lower is better)")
    ax.set_title("Baseline Comparison on Real Predictions")
    plt.xticks(rotation=15, ha="right")
    for bar, v in zip(bars, wrong_rates):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                f"{v:.1%}", ha="center", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "real_baseline.png", dpi=150)
    plt.close(fig)

    # ── 图 2: 消融 ──
    fig, ax = plt.subplots(figsize=(9, 5))
    names = list(ablation.keys())
    wrong_rates = []
    for name in names:
        r = ablation[name]
        total = r["correct"] + r["wrong"] + r["reject"]
        wrong_rates.append(r["wrong"] / total if total else 0)
    bars = ax.bar(names, wrong_rates, color="#4CAF50")
    ax.set_ylabel("Wrong-pass rate (higher = evidence is more important)")
    ax.set_title("Ablation on Real Predictions (relaxed config)")
    for bar, v in zip(bars, wrong_rates):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                f"{v:.1%}", ha="center", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "real_ablation.png", dpi=150)
    plt.close(fig)

    print(f"\n✅ 图表已保存:")
    print(f"  {OUT_DIR / 'real_baseline.png'}")
    print(f"  {OUT_DIR / 'real_ablation.png'}")


if __name__ == "__main__":
    main()
