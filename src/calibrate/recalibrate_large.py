"""
小样本参数重校准 — 用 895 条大样本重算容差/物理边界/风险分界

之前小样本 (n=14~80) 校准的参数在大样本下可能不稳。
本脚本用 data/batch_calibration/records_all.json (895 条) 重算:
  1. P/S 一致性容差: 双模型正确时间差 95% 分位
  2. 物理边界 min_sp/max_sp: S-P 时间差 2.5%/97.5% 分位
  3. 风险分界: 网格扫描

用法:
    python -m src.calibrate.recalibrate_large
"""

import json
from collections import defaultdict
from pathlib import Path

import numpy as np

RECORDS_PATH = Path("data/batch_calibration/records_all.json")
OUT_PATH = Path("docs/experiments/recalibration_large.json")

P_TOL = 0.5
S_TOL = 1.0


def load_records():
    with open(RECORDS_PATH, encoding="utf-8") as f:
        return json.load(f)


def calibrate_tolerance(records):
    """双模型都正确时的时间差分布 (n 大幅增加)"""
    diffs = {"P": [], "S": []}

    for r in records:
        truth_p, truth_s = r["truth_p_s"], r["truth_s_s"]
        preds = r["predictions"]
        models = list(preds.keys())

        for phase, tol, truth in [("P", P_TOL, truth_p), ("S", S_TOL, truth_s)]:
            if truth is None:
                continue
            # 收集该相位各模型的拾取
            picks = []
            for m in models:
                t = preds[m][f"{phase}_pick"]
                if t is not None:
                    picks.append((m, t))
            # 两两组合: 都正确才记录差值
            for i in range(len(picks)):
                for j in range(i + 1, len(picks)):
                    m1, t1 = picks[i]
                    m2, t2 = picks[j]
                    if abs(t1 - truth) <= tol and abs(t2 - truth) <= tol:
                        diffs[phase].append(abs(t1 - t2))

    result = {}
    for phase in ("P", "S"):
        arr = np.array(diffs[phase])
        result[phase] = {
            "n": int(len(arr)),
            "p95": round(float(np.percentile(arr, 95)), 3),
            "median": round(float(np.median(arr)), 3),
        }
        print(f"[容差] {phase}: n={len(arr)}, 95%分位={result[phase]['p95']}s")
    return result


def calibrate_physics(records):
    """S-P 时间差分布"""
    sp = []
    for r in records:
        tp, ts = r["truth_p_s"], r["truth_s_s"]
        if tp is not None and ts is not None and ts > tp:
            sp.append(ts - tp)
    arr = np.array(sp)
    result = {
        "n": int(len(arr)),
        "min_sp_2p5": round(float(np.percentile(arr, 2.5)), 2),
        "max_sp_97p5": round(float(np.percentile(arr, 97.5)), 2),
        "median": round(float(np.median(arr)), 2),
    }
    print(f"[物理边界] n={result['n']}, min={result['min_sp_2p5']}s, "
          f"max={result['max_sp_97p5']}s")
    return result


def main():
    records = load_records()
    print(f"大样本: {len(records)} 条\n")

    tol = calibrate_tolerance(records)
    physics = calibrate_physics(records)

    print("\n对比小样本校准值:")
    print(f"  P 容差: 旧 0.578 (n=14) vs 新 {tol['P']['p95']} (n={tol['P']['n']})")
    print(f"  S 容差: 旧 0.340 (n=36) vs 新 {tol['S']['p95']} (n={tol['S']['n']})")
    print(f"  min_sp: 旧 5.11 (n=80) vs 新 {physics['min_sp_2p5']} (n={physics['n']})")
    print(f"  max_sp: 旧 30.21 (n=80) vs 新 {physics['max_sp_97p5']} (n={physics['n']})")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "n_samples": len(records),
            "tolerance": tol,
            "physics_boundary": physics,
            "old_values": {
                "p_tol": 0.578, "s_tol": 0.340,
                "min_sp": 5.11, "max_sp": 30.21,
            },
        }, f, indent=2, ensure_ascii=False)
    print(f"\n✅ 结果 → {OUT_PATH}")


if __name__ == "__main__":
    main()
