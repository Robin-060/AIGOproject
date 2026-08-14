import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

from src.calibrate.grid_search import load_labels, simulate_predictions, run_one_config
from src.trust_engine.pipeline import DEMO_CONFIG

OUT_DIR = Path("docs/experiments")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def truth_for_phase(truth, phase):
    if phase == "P":
        return truth["P_time_s"], 0.5
    return truth["S_time_s"], 1.0


def single_model(preds):
    return [p for p in preds if p.model_name == "OBSTransformer"]


def highest_confidence(preds):
    selected = []

    for phase in ["P", "S"]:
        candidates = [
            p for p in preds
            if p.phase == phase and p.score is not None
        ]

        if candidates:
            selected.append(max(candidates, key=lambda p: p.score))

    return selected


def simple_vote(preds):
    selected = []

    for phase in ["P", "S"]:
        candidates = [p for p in preds if p.phase == phase]

        if not candidates:
            continue

        if len(candidates) == 1:
            selected.append(candidates[0])
            continue

        times = np.array([p.time_s for p in candidates])
        median_time = np.median(times)

        selected.append(
            min(candidates, key=lambda p: abs(p.time_s - median_time))
        )

    return selected


def collect_records(labels, selector):
    records = []

    for truth in labels:
        if truth["label"] != "EARTHQUAKE":
            continue

        preds = simulate_predictions(truth, disagreement=False)
        selected = selector(preds)

        for pred in selected:
            gt, tolerance = truth_for_phase(truth, pred.phase)

            if gt is None or gt < 0:
                continue

            error = abs(pred.time_s - gt)
            correct = error <= tolerance

            score = pred.score
            if score is None:
                score = 0.0

            records.append({
                "score": float(score),
                "correct": bool(correct),
            })

    return records


def risk_coverage(records):
    thresholds = np.linspace(0.0, 1.0, 41)

    coverage = []
    risk = []

    total = len(records)

    for threshold in thresholds:
        kept = [r for r in records if r["score"] >= threshold]

        if total == 0:
            coverage.append(0)
            risk.append(0)
            continue

        cov = len(kept) / total

        if kept:
            accuracy = sum(r["correct"] for r in kept) / len(kept)
            r = 1.0 - accuracy
        else:
            r = 0.0

        coverage.append(cov)
        risk.append(r)

    return np.array(coverage), np.array(risk)


def main():
    labels = load_labels()

    methods = {
        "OBSTransformer": single_model,
        "Highest Confidence": highest_confidence,
        "Simple Vote": simple_vote,
    }

    curves = {}

    print("\n===== Baseline Comparison =====")

    for name, selector in methods.items():
        records = collect_records(labels, selector)

        accuracy = (
            sum(r["correct"] for r in records) / len(records)
            if records else 0
        )

        avg_confidence = (
            np.mean([r["score"] for r in records])
            if records else 0
        )

        print(
            f"{name}: "
            f"accuracy={accuracy:.3f}, "
            f"avg_confidence={avg_confidence:.3f}, "
            f"n={len(records)}"
        )

        curves[name] = risk_coverage(records)

    # Trust Layer：直接使用当前 Trust Engine 的真实运行结果
    trust = run_one_config(DEMO_CONFIG, labels)

    trust_coverage = float(trust.get("auto_coverage", 0.0))
    trust_detection = float(trust.get("error_detection_rate", 0.0))
    trust_risk = 1.0 - trust_detection

    print(
        f"Trust Layer: "
        f"error_detection_rate={trust_detection:.3f}, "
        f"auto_coverage={trust_coverage:.3f}"
    )

    # Risk–Coverage Curve
    plt.figure(figsize=(9, 6))

    for name, (coverage, risk) in curves.items():
        plt.plot(coverage, risk, marker="o", markersize=3, label=name)

    # Trust Layer 是当前真实 operating point
    plt.scatter(
        [trust_coverage],
        [trust_risk],
        s=120,
        marker="*",
        label="Trust Layer"
    )

    plt.xlabel("Coverage")
    plt.ylabel("Risk")
    plt.title("Risk–Coverage Comparison")
    plt.xlim(0, 1.05)
    plt.ylim(0, 1.0)
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()

    risk_path = OUT_DIR / "risk_coverage_curve.png"
    plt.savefig(risk_path, dpi=200)
    plt.close()

    print(f"\nSaved: {risk_path}")

    # 单独做 Coverage 对比图
    baseline_coverages = {
        name: float(curves[name][0][0])
        for name in methods
    }
    baseline_coverages["Trust Layer"] = trust_coverage

    plt.figure(figsize=(8, 5))
    plt.bar(
        list(baseline_coverages.keys()),
        list(baseline_coverages.values())
    )
    plt.ylim(0, 1.05)
    plt.ylabel("Coverage")
    plt.title("Baseline Coverage Comparison")
    plt.xticks(rotation=15)
    plt.tight_layout()

    comparison_path = OUT_DIR / "baseline_final_comparison.png"
    plt.savefig(comparison_path, dpi=200)
    plt.close()

    print(f"Saved: {comparison_path}")
    print("\n✅ Final baseline experiment completed.")


if __name__ == "__main__":
    main()
