import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

from src.calibrate.grid_search import load_labels, simulate_predictions


OUT_DIR = Path("docs/experiments")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def phase_error(pred, truth):
    if pred.phase == "P":
        gt = truth["P_time_s"]
        tolerance = 0.5
    else:
        gt = truth["S_time_s"]
        tolerance = 1.0

    if gt is None or gt < 0:
        return None, None

    error = abs(pred.time_s - gt)
    correct = error <= tolerance
    return error, correct


def baseline_single_model(preds, model_name="OBSTransformer"):
    selected = [p for p in preds if p.model_name == model_name]
    return selected


def baseline_highest_confidence(preds):
    result = []

    for phase in ["P", "S"]:
        candidates = [p for p in preds if p.phase == phase and p.score is not None]

        if candidates:
            best = max(candidates, key=lambda p: p.score)
            result.append(best)

    return result


def baseline_simple_vote(preds):
    result = []

    for phase in ["P", "S"]:
        candidates = [p for p in preds if p.phase == phase]

        if len(candidates) < 2:
            result.extend(candidates)
            continue

        times = np.array([p.time_s for p in candidates])
        median_time = np.median(times)

        best = min(
            candidates,
            key=lambda p: abs(p.time_s - median_time)
        )

        result.append(best)

    return result


def evaluate_method(method_name, selector, labels):
    total = 0
    correct = 0
    confidences = []

    for truth in labels:
        if truth["label"] != "EARTHQUAKE":
            continue

        preds = simulate_predictions(truth, disagreement=False)
        selected = selector(preds)

        for pred in selected:
            error, is_correct = phase_error(pred, truth)

            if is_correct is None:
                continue

            total += 1

            if is_correct:
                correct += 1

            if pred.score is not None:
                confidences.append(pred.score)

    accuracy = correct / total if total else 0
    avg_conf = np.mean(confidences) if confidences else 0

    print(
        f"{method_name}: "
        f"accuracy={accuracy:.3f}, "
        f"avg_confidence={avg_conf:.3f}, "
        f"n={total}"
    )

    return accuracy


def main():
    labels = load_labels()

    results = {}

    results["Single Model"] = evaluate_method(
        "Single Model",
        lambda preds: baseline_single_model(preds, "OBSTransformer"),
        labels,
    )

    results["Highest Confidence"] = evaluate_method(
        "Highest Confidence",
        baseline_highest_confidence,
        labels,
    )

    results["Simple Vote"] = evaluate_method(
        "Simple Vote",
        baseline_simple_vote,
        labels,
    )

    print("\nBaseline first version completed.")

    names = list(results.keys())
    values = list(results.values())

    plt.figure(figsize=(8, 5))
    plt.bar(names, values)
    plt.ylim(0, 1)
    plt.ylabel("Accuracy")
    plt.title("Baseline Comparison")
    plt.tight_layout()

    out_path = OUT_DIR / "baseline_comparison.png"
    plt.savefig(out_path, dpi=200)

    print(f"Saved figure to: {out_path}")


if __name__ == "__main__":
    main()
