"""
Cluster paired-bootstrap — C 契约 8.4 统计硬要求

设计:
  - cluster 单元: station (60 个台站, 冻结于 semifinal_v1.1)
  - paired: 同一重采样站集上同时算 Trust 与对比策略的 Unsafe
  - 覆盖率点: 46.7% (Trust v2 天花板), 重采样内各自 top-k 对齐
  - 确证条件 (C 契约): ΔUnsafe = Trust − comparator 的单侧 95% CI 上界 < 0
    → Trust 显著更优; CI 包含 0 → INCONCLUSIVE; CI 全正 → Trust 显著更差
  - P、S 分相位报告; 双相位同时声明时 Holm 校正
  - seed = 42, 1000 次重采样

用法:
    python -m src.experiments.bootstrap_analysis
"""

import csv
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
    phase_verdict,
)
from src.experiments.run_baselines import strat_vote, with_confidence  # noqa: E402

OUT_JSON = ROOT / "results" / "bootstrap_ci.json"
COVERAGE_PCT = 46.7
N_REPLICATES = 1000
SEED = 42

TRUST_CSV = ROOT / "results" / "main_results.csv"


def load_trust():
    trust = {}
    with open(TRUST_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (row["sample_id"], row["phase"])
            trust[key] = {
                "verdict": row["verdict"],
                "risk": float(row["risk"]),
                "station": row["station"],
            }
    return trust


def method_stats(units_subset, trust, voting_output, voting_risk):
    """同一单元集上: Trust 与 Voting 各自 top-k 对齐后的 Unsafe (%)."""
    n = len(units_subset)
    k = int(round(COVERAGE_PCT / 100 * n))

    trust_units = []
    for u in units_subset:
        key = (u["sample_id"], u["phase"])
        t = trust[key]
        if t["verdict"] in ("correct", "wrong"):
            trust_units.append((t["risk"], key, t["verdict"]))
    trust_units.sort(key=lambda x: (x[0], x[1]))
    trust_accept = set(entry[1] for entry in trust_units[: min(k, len(trust_units))])

    vote_units = []
    for u in units_subset:
        key = (u["sample_id"], u["phase"])
        out = voting_output[u["sample_id"], u["phase"]]
        if out is None:
            continue
        verdict = phase_verdict(out, u["reference_time_s"], u["phase"])
        if verdict in ("correct", "wrong"):
            vote_units.append((voting_risk[u["sample_id"], u["phase"]], key, verdict))
    vote_units.sort(key=lambda x: (x[0], x[1]))
    vote_accept = set(entry[1] for entry in vote_units[: min(k, len(vote_units))])

    # 统一判定: 用每个方法自己的 verdict
    trust_wrong = trust_correct = vote_wrong = vote_correct = 0
    for key in trust_accept:
        if trust[key]["verdict"] == "wrong":
            trust_wrong += 1
        else:
            trust_correct += 1
    for u in units_subset:
        key = (u["sample_id"], u["phase"])
        if key in vote_accept:
            out = voting_output[key]
            if out is None:
                continue
            verdict = phase_verdict(out, u["reference_time_s"], u["phase"])
            if verdict == "wrong":
                vote_wrong += 1
            elif verdict == "correct":
                vote_correct += 1
    t_unsafe = trust_wrong / (trust_wrong + trust_correct) * 100 if (trust_wrong + trust_correct) else float("nan")
    v_unsafe = vote_wrong / (vote_wrong + vote_correct) * 100 if (vote_wrong + vote_correct) else float("nan")
    return t_unsafe, v_unsafe


def main():
    records = load_records()
    units = with_confidence(build_phase_units(records), records)
    trust = load_trust()
    vote_output, vote_risk_fn = strat_vote()
    voting_output = {}
    voting_risk = {}
    for u in units:
        key = (u["sample_id"], u["phase"])
        voting_output[key] = vote_output(u)
        voting_risk[key] = vote_risk_fn(u)

    stations = sorted({u["station"] for u in units if u["primary_inclusion"]})
    units_by_station = {}
    for u in units:
        if not u["primary_inclusion"]:
            continue
        units_by_station.setdefault(u["station"], []).append(u)
    print(f"cluster 单元: {len(stations)} 个台站 | 覆盖率点 {COVERAGE_PCT}% "
          f"| {N_REPLICATES} 次重采样 | seed {SEED}")

    rng = np.random.default_rng(SEED)
    report = {}
    for phase_label, filt in (("ALL", None), ("P", "P"), ("S", "S")):
        base_units = [u for u in units
                      if u["primary_inclusion"] and (filt is None or u["phase"] == filt)]
        t0, v0 = method_stats(base_units, trust, voting_output, voting_risk)
        deltas = []
        for _ in range(N_REPLICATES):
            sample_stations = rng.choice(stations, size=len(stations), replace=True)
            subset = []
            for st in sample_stations:
                subset.extend(units_by_station.get(st, []))
            subset = [u for u in subset if filt is None or u["phase"] == filt]
            if not subset:
                continue
            t, v = method_stats(subset, trust, voting_output, voting_risk)
            if np.isfinite(t) and np.isfinite(v):
                deltas.append(t - v)
        deltas = np.array(deltas)
        lo, hi = np.percentile(deltas, [2.5, 97.5])
        upper95 = np.percentile(deltas, 95)
        lower5 = np.percentile(deltas, 5)
        if upper95 < 0:
            verdict = "Trust 显著更优 (单侧95%上界<0)"
        elif lower5 > 0:
            verdict = "Trust 显著更差 (Δ 全正)"
        else:
            verdict = "INCONCLUSIVE (CI 包含 0)"
        report[phase_label] = {
            "point_delta_pp": round(t0 - v0, 2),
            "trust_unsafe_pp": round(t0, 2),
            "voting_unsafe_pp": round(v0, 2),
            "ci95_lo": round(float(lo), 2),
            "ci95_hi": round(float(hi), 2),
            "one_sided_upper95": round(float(upper95), 2),
            "n_replicates": int(len(deltas)),
            "verdict": verdict,
        }
        print(f"\n[{phase_label}] 点估计: Trust {t0:.1f}% vs Voting {v0:.1f}% "
              f"(Δ={t0-v0:+.1f}pp)")
        print(f"    95% CI: [{lo:+.1f}, {hi:+.1f}]pp | 单侧上界 {upper95:+.1f}pp")
        print(f"    判定: {verdict}")

    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\n✓ {OUT_JSON}")


if __name__ == "__main__":
    main()
