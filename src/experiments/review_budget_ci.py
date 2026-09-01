"""
EXP16 统计背书 — cluster bootstrap CI + 同截获率预算反查表 (v1.5.1)

给 Review Budget 曲线的预算点对比提供统计依据 (C 契约 8.4 同款协议):
  - cluster paired-bootstrap: 60 台站有放回重采样 × 1000 次, seed 42
  - 每轮重算 ModelConf/Disagreement/TrustRisk 在各预算点的截获率,
    Random 取全体随机排序的期望值 (= 预算本身, 对角线), 报告差值 95% CI
  - 单侧 95% 下界 > 0 → "显著更优"; 否则 INCONCLUSIVE
  - 同截获率预算反查: 达到 50/60/70/80% 截获率各策略所需的复核预算 (%)

输出:
  results/review_budget_ci.json
  results/review_budget_interpolation.json

用法: python -m src.experiments.review_budget_ci
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import warnings  # noqa: E402
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402

from src.experiments.phase_evaluation import (  # noqa: E402
    build_phase_units,
    load_records,
)
from src.experiments.review_budget_curve import (  # noqa: E402
    build_signals,
    interception_at,
)
from src.trust_engine.config_loader import load_frozen_config  # noqa: E402

OUT_CI = ROOT / "results" / "review_budget_ci.json"
OUT_INTERP = ROOT / "results" / "review_budget_interpolation.json"

CI_BUDGETS = [5, 10, 20, 30, 50]
INTERP_TARGETS = [50, 60, 70, 80]
N_ITER = 1000
SEED = 42
STRATEGIES = ("ModelConf", "Disagreement", "TrustRisk")


def load_unit_stations():
    """返回与 build_signals() 同序的 station 数组."""
    import csv
    units = [u for u in build_phase_units(load_records())
             if u["primary_inclusion"]]
    station_map = {}
    with open(ROOT / "results" / "main_results.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            station_map[(r["sample_id"], r["phase"])] = r["station"]
    return np.array([station_map[(u["sample_id"], u["phase"])] for u in units])


def budget_for_target(suspicion, is_error, target_pct):
    """达到 target_pct% 截获率所需的最小复核预算 (%); 不可达返回 None."""
    for b in range(0, 101):
        inter, _ = interception_at(suspicion, is_error, b)
        if inter + 1e-9 >= target_pct:
            return b
    return None


def main():
    frozen = load_frozen_config()
    signals, is_error, _ = build_signals()
    stations = load_unit_stations()
    station_idx = {}
    for i, st in enumerate(stations):
        station_idx.setdefault(st, []).append(i)
    station_list = sorted(station_idx)
    n_stations = len(station_list)
    print(f"cluster 单元: {n_stations} 台站 | {N_ITER} 次重采样 | seed {SEED}")

    rng = np.random.default_rng(SEED)
    ci_report = {
        "config_version": frozen.version,
        "config_hash": frozen.sha256,
        "n_units": len(is_error),
        "total_errors": int(is_error.sum()),
        "cluster_unit": "station",
        "n_stations": n_stations,
        "n_iterations": N_ITER,
        "seed": SEED,
        "random_baseline": "期望值 (全体随机排序的平均 = 预算本身, 对角线)",
        "budgets_pct": CI_BUDGETS,
        "comparisons": {},
    }

    # 预计算每轮重采样的索引 (固定种子, 可复现)
    resamples = []
    for _ in range(N_ITER):
        idx = []
        for st in rng.choice(station_list, size=n_stations, replace=True):
            idx.extend(station_idx[st])
        resamples.append(np.asarray(idx, dtype=int))

    for b in CI_BUDGETS:
        comp = {}
        # ① 各策略 vs Random (期望 = 预算)
        for strategy in STRATEGIES:
            base = interception_at(signals[strategy], is_error, b)[0]
            diffs = np.empty(N_ITER)
            for it, idx in enumerate(resamples):
                inter = interception_at(
                    signals[strategy][idx], is_error[idx], b)[0]
                # Random 期望 = 预算; 差值 = inter - b
                diffs[it] = inter - b
            lo, hi = np.percentile(diffs, [2.5, 97.5])
            lower5 = np.percentile(diffs, 5)
            verdict = ("显著更优 (单侧 95% 下界 > 0)"
                       if lower5 > 0 else "INCONCLUSIVE (CI 含 0)")
            comp[f"{strategy}_minus_random"] = {
                "point_delta_pp": round(base - b, 2),
                "bootstrap_mean_delta_pp": round(float(diffs.mean()), 2),
                "ci95_lo_pp": round(float(lo), 2),
                "ci95_hi_pp": round(float(hi), 2),
                "one_sided_lower95_pp": round(float(lower5), 2),
                "verdict": verdict,
            }
            print(f"[{b}%] {strategy}-Random: Δ={base - b:+.1f}pp "
                  f"CI[{lo:+.1f},{hi:+.1f}] {verdict}")
        # ② Trust vs 单一信号 (ModelConf / Disagreement), 同重采样
        trust_base = interception_at(signals["TrustRisk"], is_error, b)[0]
        for other in ("ModelConf", "Disagreement"):
            other_base = interception_at(signals[other], is_error, b)[0]
            diffs = np.empty(N_ITER)
            for it, idx in enumerate(resamples):
                t = interception_at(signals["TrustRisk"][idx],
                                    is_error[idx], b)[0]
                o = interception_at(signals[other][idx],
                                    is_error[idx], b)[0]
                diffs[it] = t - o
            lo, hi = np.percentile(diffs, [2.5, 97.5])
            lower5 = np.percentile(diffs, 5)
            verdict = ("显著更优 (单侧 95% 下界 > 0)"
                       if lower5 > 0 else "INCONCLUSIVE (CI 含 0)")
            comp[f"trust_minus_{other.lower()}"] = {
                "point_delta_pp": round(trust_base - other_base, 2),
                "bootstrap_mean_delta_pp": round(float(diffs.mean()), 2),
                "ci95_lo_pp": round(float(lo), 2),
                "ci95_hi_pp": round(float(hi), 2),
                "one_sided_lower95_pp": round(float(lower5), 2),
                "verdict": verdict,
            }
            print(f"[{b}%] Trust-{other}: Δ={trust_base - other_base:+.1f}pp "
                  f"CI[{lo:+.1f},{hi:+.1f}] {verdict}")
        ci_report["comparisons"][str(b)] = comp
    OUT_CI.write_text(json.dumps(ci_report, indent=2, ensure_ascii=False),
                      encoding="utf-8")
    print(f"✓ {OUT_CI}")

    # ── 同截获率所需预算反查表 ──
    interp = {
        "config_version": frozen.version, "config_hash": frozen.sha256,
        "target_interception_pct": INTERP_TARGETS, "budget_needed_pct": {},
    }
    print(f"\n{'目标截获':>8} " + "".join(f"{s:>16}" for s in
          ("Random",) + STRATEGIES))
    for t in INTERP_TARGETS:
        row = {"Random": t}   # 随机排序: 截获率 = 预算 (期望)
        for strategy in STRATEGIES:
            row[strategy] = budget_for_target(signals[strategy], is_error, t)
        interp["budget_needed_pct"][str(t)] = row
        print(f"{t:>7}% " + "".join(
            f"{row[s] if row[s] is not None else '>100':>15}%" for s in
            ("Random",) + STRATEGIES))
    OUT_INTERP.write_text(json.dumps(interp, indent=2, ensure_ascii=False),
                          encoding="utf-8")
    print(f"✓ {OUT_INTERP}")


if __name__ == "__main__":
    main()
