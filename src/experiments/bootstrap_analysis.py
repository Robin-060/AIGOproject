"""
Cluster paired-bootstrap — C 契约 8.4 统计硬要求 (v1.5 NOT_EVALUABLE 纪律)

设计:
  - cluster 单元: station (60 个台站, 冻结于 semifinal_v1.5)
  - paired: 同一重采样站集上同时算 Trust 与对比策略的 Unsafe
  - 声明点位: 50% (预注册); 若 Trust 天花板 < 点位 → 该点位 NOT_EVALUABLE
    (不等覆盖比较不给出显著性结论, C 纪律)
  - 补充比较: 在天花板点位做 paired bootstrap, 标注 supplementary (非声明点位)
  - seed = 42, 1000 次重采样; P、S 分相位报告

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
DECLARED_PCT = 50.0   # 预注册声明点位
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


def method_stats(units_subset, trust, voting_output, voting_risk, target_pct):
    """同一单元集上: Trust 与 Voting 各自 top-k 对齐后的 Unsafe (%)."""
    n = len(units_subset)
    k = int(round(target_pct / 100 * n))

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

    trust_wrong = trust_correct = vote_wrong = vote_correct = 0
    for key in trust_accept:
        if trust[key]["verdict"] == "wrong":
            trust_wrong += 1
        else:
            trust_correct += 1
    for u in units_subset:
        key = (u["sample_id"], u["phase"])
        if key in vote_accept:
            out = voting_output[u["sample_id"], u["phase"]]
            if out is None:
                continue
            verdict = phase_verdict(out, u["reference_time_s"], u["phase"])
            if verdict == "wrong":
                vote_wrong += 1
            elif verdict == "correct":
                vote_correct += 1
    t_unsafe = (trust_wrong / (trust_wrong + trust_correct) * 100
                if (trust_wrong + trust_correct) else float("nan"))
    v_unsafe = (vote_wrong / (vote_wrong + vote_correct) * 100
                if (vote_wrong + vote_correct) else float("nan"))
    return t_unsafe, v_unsafe


def run_phase_bootstrap(base_units, trust, voting_output, voting_risk,
                        target_pct, stations, units_by_station, filt, rng):
    """单相位 × 单覆盖率点的 paired bootstrap."""
    t0, v0 = method_stats(base_units, trust, voting_output, voting_risk, target_pct)
    deltas = []
    for _ in range(N_REPLICATES):
        sample_stations = rng.choice(stations, size=len(stations), replace=True)
        subset = []
        for st in sample_stations:
            subset.extend(units_by_station.get(st, []))
        subset = [u for u in subset if filt is None or u["phase"] == filt]
        if not subset:
            continue
        t, v = method_stats(subset, trust, voting_output, voting_risk, target_pct)
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
    return {
        "target_coverage_pct": target_pct,
        "point_delta_pp": round(t0 - v0, 2),
        "trust_unsafe_pp": round(t0, 2),
        "voting_unsafe_pp": round(v0, 2),
        "ci95_lo": round(float(lo), 2),
        "ci95_hi": round(float(hi), 2),
        "one_sided_upper95": round(float(upper95), 2),
        "n_replicates": int(len(deltas)),
        "verdict": verdict,
    }


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

    # Trust 覆盖率天花板 (输出有效单元占比)
    primary = [u for u in units if u["primary_inclusion"]]
    trust_ceiling = (
        sum(1 for u in primary
            if trust[(u["sample_id"], u["phase"])]["verdict"] in ("correct", "wrong"))
        / len(primary) * 100
    )
    declared_feasible = trust_ceiling + 1e-9 >= DECLARED_PCT
    print(f"cluster 单元: {len(stations)} 台站 | 声明点位 {DECLARED_PCT}% | "
          f"Trust 天花板 {trust_ceiling:.1f}% | {N_REPLICATES} 次重采样 | seed {SEED}")
    if not declared_feasible:
        print(f"⚠ 声明点位 {DECLARED_PCT}% 不可达 → 该点位 NOT_EVALUABLE"
              f" (不等覆盖比较不给出显著性结论); 另做天花板点位补充比较")

    rng = np.random.default_rng(SEED)
    report = {"trust_ceiling_pct": round(trust_ceiling, 2),
              "declared_point": DECLARED_PCT,
              "declared_feasible": bool(declared_feasible)}

    for phase_label, filt in (("ALL", None), ("P", "P"), ("S", "S")):
        base_units = [u for u in primary
                      if filt is None or u["phase"] == filt]
        if declared_feasible:
            entry = run_phase_bootstrap(
                base_units, trust, voting_output, voting_risk,
                DECLARED_PCT, stations, units_by_station, filt, rng)
            report[f"{phase_label}"] = entry
            print(f"\n[{phase_label}] 声明点位 {DECLARED_PCT}%: "
                  f"Trust {entry['trust_unsafe_pp']:.1f}% vs Voting {entry['voting_unsafe_pp']:.1f}% "
                  f"(Δ={entry['point_delta_pp']:+.1f}pp)")
            print(f"    95% CI: [{entry['ci95_lo']:+.1f}, {entry['ci95_hi']:+.1f}]pp | "
                  f"判定: {entry['verdict']}")
        else:
            report[f"{phase_label}"] = {
                "target_coverage_pct": DECLARED_PCT,
                "verdict": "NOT_EVALUABLE",
                "reason": f"Trust ceiling {trust_ceiling:.1f}% < declared {DECLARED_PCT}%",
            }
            print(f"\n[{phase_label}] 声明点位 {DECLARED_PCT}%: NOT_EVALUABLE"
                  f" (天花板 {trust_ceiling:.1f}%)")
            # 天花板点位补充比较 (非声明点位, 仅作证据)
            ceil = round(trust_ceiling, 1)
            entry = run_phase_bootstrap(
                base_units, trust, voting_output, voting_risk,
                ceil, stations, units_by_station, filt, rng)
            report[f"{phase_label}_ceiling_supplementary"] = entry
            print(f"[{phase_label}] 补充(天花板 {ceil}%): Trust {entry['trust_unsafe_pp']:.1f}% "
                  f"vs Voting {entry['voting_unsafe_pp']:.1f}% "
                  f"(Δ={entry['point_delta_pp']:+.1f}pp, {entry['verdict']})")

    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\n✓ {OUT_JSON}")


if __name__ == "__main__":
    main()
