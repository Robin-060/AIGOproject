"""
置信度校准脚本

统计: 模型 score=X 时, 实际正确率=?
画校准曲线 + Platt Scaling 修正

用法:
    python -m src.calibrate.calibrate_confidence
"""

import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

from src.calibrate.grid_search import load_labels, simulate_predictions

OUT_DIR = Path("docs/experiments")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def collect_scores(labels, n_runs: int = 3):
    """
    多次运行模拟预测, 收集 (model_score, is_correct) 对
    """
    data = []
    for _ in range(n_runs):
        for truth in labels:
            is_earthquake = truth["label"] == "EARTHQUAKE"
            if not is_earthquake:
                continue
            gt_p, gt_s = truth["P_time_s"], truth["S_time_s"]
            if gt_p <= 0 or gt_s <= 0:
                continue

            # 生成多种情况: 正常 + 弱 + 分歧
            for mode in ["normal", "weak", "disagree"]:
                if mode == "disagree":
                    preds = simulate_predictions(truth, disagreement=True)
                else:
                    preds = simulate_predictions(truth, disagreement=False)

                for p in preds:
                    if p.score is None:
                        continue
                    gt = gt_p if p.phase == "P" else gt_s
                    error = abs(p.time_s - gt)
                    correct = error <= 0.5  # P 容差 0.5s
                    if p.phase == "S":
                        correct = error <= 1.0  # S 容差 1.0s
                    data.append((p.score, int(correct), p.model_name, p.phase))

    return data


def plot_calibration_curve(data, out_path):
    """画校准曲线: X=模型score, Y=实际正确率"""
    scores = np.array([d[0] for d in data])
    correct = np.array([d[1] for d in data])

    # 分桶
    bins = np.arange(0, 1.05, 0.1)
    bin_centers = []
    bin_acc = []

    for i in range(len(bins) - 1):
        mask = (scores >= bins[i]) & (scores < bins[i + 1])
        if mask.sum() >= 3:
            bin_centers.append((bins[i] + bins[i + 1]) / 2)
            bin_acc.append(correct[mask].mean())

    bin_centers = np.array(bin_centers)
    bin_acc = np.array(bin_acc)

    x_cal = np.linspace(0, 1, 100)

    # Platt Scaling (简化: sigmoid 拟合)
    def sigmoid(x, a, b):
        return 1 / (1 + np.exp(-(a * x + b)))

    from scipy.optimize import curve_fit
    try:
        popt, _ = curve_fit(sigmoid, scores, correct, p0=[5, -2.5], maxfev=5000)
        y_cal = sigmoid(x_cal, *popt)
        has_cal = True
    except Exception:
        y_cal = x_cal
        has_cal = False

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot([0, 1], [0, 1], "k--", alpha=0.3, label="Perfect (score=accuracy)")
    ax.plot(bin_centers, bin_acc, "o-", color="#2196F3", linewidth=2,
            markersize=8, label="Raw (binned)")
    ax.plot(x_cal, y_cal, "-", color="#F44336", linewidth=2,
            label="Platt Scaling (calibrated)")
    ax.fill_between(x_cal, y_cal - 0.05, y_cal + 0.05, alpha=0.1, color="#F44336")
    ax.set_xlabel("Model Confidence Score", fontsize=12)
    ax.set_ylabel("Actual Accuracy", fontsize=12)
    ax.set_title("Confidence Calibration Curve", fontsize=14)
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)

    # 输出校准质量
    ece = _expected_calibration_error(scores, correct, bins=10)
    print(f"  校准前 ECE: {ece:.4f}")
    try:
        y_pred = sigmoid(scores, *popt)
        ece_cal = _expected_calibration_error(y_pred, correct, bins=10)
        print(f"  校准后 ECE: {ece_cal:.4f}")
    except Exception:
        pass
    print(f"  ✅ 校准曲线已保存 → {out_path}")


def _expected_calibration_error(scores, correct, bins=10):
    """Expected Calibration Error (ECE)"""
    boundaries = np.linspace(0, 1, bins + 1)
    ece = 0.0
    for i in range(bins):
        mask = (scores >= boundaries[i]) & (scores < boundaries[i + 1])
        if mask.sum() == 0:
            continue
        acc = correct[mask].mean()
        conf = scores[mask].mean()
        ece += (mask.sum() / len(scores)) * abs(acc - conf)
    return ece


def main():
    labels = load_labels()
    print(f"加载 {len(labels)} 条标签, 收集模型分数...")
    data = collect_scores(labels, n_runs=3)
    print(f"  收集 {len(data)} 个 (score, correct) 对")

    out_path = OUT_DIR / "calibration_curve.png"
    plot_calibration_curve(data, out_path)


if __name__ == "__main__":
    main()
