"""
内部扣分校准 — 用故障危害率反推每个故障该扣多少分

原理:
  内部扣分应与"该故障让模型错多少"成正比。
  故障注入实验已测得四类故障的模型错误率:
    channel_missing: 28.6%
    clipping:        35.8%
    gap:             32.8%
    strong_noise:    91.3%

校准公式:
  扣分 = 数据证据总分上限 × 该故障的模型错误率

用法:
    python -m src.calibrate.internal_score_calibration
"""

import json
from pathlib import Path

FAULT_INJ_PATH = Path("docs/experiments/data_weight_calibration.json")
OUT_PATH = Path("docs/experiments/internal_score_calibration.json")

# 数据证据总分上限 (来自 TrustConfig.data_weight)
DATA_BUDGET = 30.0


def calibrate():
    with open(FAULT_INJ_PATH, encoding="utf-8") as f:
        data = json.load(f)

    stats = data["per_fault_stats"]

    # 故障 → 模型错误率
    error_rates = {
        fault: s["wrong"] / s["n"]
        for fault, s in stats.items()
    }

    # 扣分 = 预算 × 错误率
    calibrated_scores = {
        fault: round(DATA_BUDGET * rate, 1)
        for fault, rate in error_rates.items()
    }

    # 当前启发式扣分 (data_evidence.py 里的值)
    current_scores = {
        "channel_missing": 12.0,   # 缺1通道 +12
        "clipping": 10.0,          # 严重削波 +10
        "gap": 15.0,               # 严重断点 +15
        "strong_noise": 15.0,      # 低SNR +15
    }

    print("=" * 60)
    print("内部扣分校准结果 (数据证据预算 30 分)")
    print("=" * 60)
    print(f"{'故障':16s} {'错误率':>8s} {'当前扣分':>10s} {'校准扣分':>10s}")
    for fault in error_rates:
        print(f"{fault:16s} {error_rates[fault]:7.1%} "
              f"{current_scores[fault]:9.1f} {calibrated_scores[fault]:9.1f}")

    # 保存
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "method": "fault harm rate × data evidence budget",
            "data_budget": DATA_BUDGET,
            "fault_error_rates": error_rates,
            "current_scores": current_scores,
            "calibrated_scores": calibrated_scores,
            "caveat": "注入故障 vs 自然故障的边界需声明",
        }, f, indent=2, ensure_ascii=False)
    print(f"\n✅ 结果 → {OUT_PATH}")


if __name__ == "__main__":
    calibrate()
