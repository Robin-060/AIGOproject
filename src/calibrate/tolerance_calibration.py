"""
容差校准 — 用 P3 的真实标注数据统计"双模型都正确时的时间差"

方法:
  对每条有真值的样本, 找"两个模型都拾取正确"的情况,
  记录两模型时间差。用 95% 分位作为有数据背书的容差建议值。

数据源:
  data/phase3/noise_predictions_seisbench.json  (真实三模型预测)
  data/phase3/noise_records_seisbench.csv       (官方 P/S 标注)

用法:
    python -m src.calibrate.tolerance_calibration
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

PRED_PATH = Path("data/phase3/noise_predictions_seisbench.json")
TRUTH_PATH = Path("data/phase3/noise_records_seisbench.csv")

# 判定"单个拾取是否正确"的容差 (沿用 P3 评估标准)
CORRECT_TOL = {"P": 0.5, "S": 1.0}

MODEL_PAIRS = [
    ("PhaseNet", "PickBlue"),
    ("PhaseNet", "OBSTransformer"),
    ("PickBlue", "OBSTransformer"),
]


def load_truth():
    """(sample_id, noise_level) → {P: truth_p, S: truth_s}"""
    truth_map = {}
    with open(TRUTH_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (row["sample_id"], row["noise_level"])
            if key in truth_map:
                continue
            truth_map[key] = {
                "P": float(row["truth_p_s"]) if row["truth_p_s"] else None,
                "S": float(row["truth_s_s"]) if row["truth_s_s"] else None,
            }
    return truth_map


def load_predictions():
    """(sample_id, noise_level) → {model: {phase: time}}"""
    pred_map = defaultdict(lambda: defaultdict(dict))
    with open(PRED_PATH, encoding="utf-8") as f:
        for p in json.load(f):
            key = (p["sample_id"], p["noise_level"])
            pred_map[key][p["model_name"]][p["phase"]] = p["time_s"]
    return pred_map


def main():
    truth = load_truth()
    preds = load_predictions()

    print(f"真值样本: {len(truth)}, 有预测的样本: {len(preds)}\n")

    # 收集 (phase, 模型对) 的"双双正确"时间差
    diffs = {"P": defaultdict(list), "S": defaultdict(list)}
    pair_stats = defaultdict(lambda: {"both_correct": 0, "pairs": 0})

    for key, gt in truth.items():
        if key not in preds:
            continue
        if gt["P"] is None or gt["S"] is None:
            continue

        for phase in ("P", "S"):
            gt_time = gt[phase]
            models_with_phase = {
                m: times.get(phase)
                for m, times in preds[key].items()
                if phase in times
            }

            for m1, m2 in MODEL_PAIRS:
                t1, t2 = models_with_phase.get(m1), models_with_phase.get(m2)
                if t1 is None or t2 is None:
                    continue
                pair_stats[(m1, m2)]["pairs"] += 1
                c1 = abs(t1 - gt_time) <= CORRECT_TOL[phase]
                c2 = abs(t2 - gt_time) <= CORRECT_TOL[phase]
                if c1 and c2:
                    pair_stats[(m1, m2)]["both_correct"] += 1
                    diffs[phase][(m1, m2)].append(abs(t1 - t2))

    # 统计
    print("=" * 60)
    print("双模型都正确时的时间差分布 (按模型对)")
    print("=" * 60)
    all_diffs = {"P": [], "S": []}
    for phase in ("P", "S"):
        print(f"\n【{phase} 波】")
        for pair in MODEL_PAIRS:
            ds = diffs[phase].get(pair, [])
            all_diffs[phase].extend(ds)
            if ds:
                arr = np.array(ds)
                print(f"  {pair[0]:15s} × {pair[1]:15s}: "
                      f"n={len(ds):3d}  中位={np.median(arr):.3f}s  "
                      f"95%分位={np.percentile(arr, 95):.3f}s  max={arr.max():.3f}s")
            else:
                print(f"  {pair[0]:15s} × {pair[1]:15s}: 无双双正确样本")

    # 汇总建议值
    print("\n" + "=" * 60)
    print("容差建议值 (95% 分位, 有真实标注背书)")
    print("=" * 60)
    suggestions = {}
    for phase in ("P", "S"):
        arr = np.array(all_diffs[phase])
        if len(arr) == 0:
            print(f"  {phase}: 数据不足")
            continue
        p95 = np.percentile(arr, 95)
        suggestions[phase] = round(float(p95), 3)
        print(f"  {phase} 波: 95% 分位 = {p95:.3f}s  "
              f"(n={len(arr)}, 中位={np.median(arr):.3f}s)")

    print(f"\n对比当前启发式值:")
    print(f"  P: 当前 0.30s  vs  实测 95% {suggestions.get('P', 'N/A')}s")
    print(f"  S: 当前 0.50s  vs  实测 95% {suggestions.get('S', 'N/A')}s")

    # 保存
    out = Path("docs/experiments/tolerance_calibration.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "method": "both-correct-difference 95th percentile",
            "data": "SeisBench OBS test split, 20 windows, official P/S labels",
            "n_both_correct_pairs": {
                "P": int(len(all_diffs["P"])),
                "S": int(len(all_diffs["S"])),
            },
            "suggested_tolerance_s": suggestions,
            "current_heuristic_s": {"P": 0.30, "S": 0.50},
        }, f, indent=2, ensure_ascii=False)
    print(f"\n✅ 结果已保存 → {out}")


if __name__ == "__main__":
    main()
