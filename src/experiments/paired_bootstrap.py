"""
paired_bootstrap.py — EXP17 ΔUnsafe 配对 cluster bootstrap (C Gate 2 严格版)

非配对版把 Voting@50% (4.59%) 当作固定常数, 只对 EXP 侧重采样;
本脚本在每轮重采样中对同一批台站单元同时计算 EXP 与 Voting 的
Unsafe@50%, 取差值分布 — 公共台站波动在相减时抵消, CI 更诚实。

口径:
  - 60 台站有放回重采样 × 1000 次, seed 42
  - EXP: main_results_exp17_{tag}.csv 冻结风险分 top-k 接受 (k=50%×n_boot)
  - Voting: 基线同口径 (中位数输出; risk=clip(spread/severe,0,1),
    severe 来自冻结配置 baseline_parameters)
  - 每轮要求双方输出数均 ≥ k, 否则跳过该轮 (计入 n_valid)
  - 判据: 差值单侧 95% 上界 < +2.0pp

用法: python -m src.experiments.paired_bootstrap --tag A
"""

import argparse
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
    MODELS,
    PHASE_TOL,
    build_phase_units,
    load_records,
)
from src.trust_engine.config_loader import load_frozen_config  # noqa: E402

N_ITER = 1000
SEED = 42
MAX_DELTA_UPPER_PP = 2.0


def voting_per_unit(units):
    """每个单元: voting_output (拾取或 None), voting_risk, voting_verdict."""
    frozen = load_frozen_config()
    severe = {k: float(v) for k, v in
              frozen.raw["baseline_parameters"]["voting_severe_threshold_s"].items()}
    out = {}
    for u in units:
        picks = [t for t in u["predictions"].values() if t is not None]
        if not picks:
            out[(u["sample_id"], u["phase"])] = (None, 1.0, "no_output")
            continue
        median = float(np.median(picks))
        risk = 1.0
        if len(picks) >= 2:
            spread = max(picks) - min(picks)
            risk = float(np.clip(spread / severe[u["phase"]], 0.0, 1.0))
        tol = PHASE_TOL[u["phase"]]
        verdict = ("correct" if abs(median - u["reference_time_s"]) <= tol
                   else "wrong")
        out[(u["sample_id"], u["phase"])] = (median, risk, verdict)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="A")
    args = parser.parse_args()
    tag = args.tag

    frozen = load_frozen_config()
    records = load_records()
    units = [u for u in build_phase_units(records) if u["primary_inclusion"]]
    stations = sorted({u["station"] for u in units})
    station_idx = {st: [] for st in stations}
    for i, u in enumerate(units):
        station_idx[u["station"]].append(i)

    # EXP 侧冻结风险分与 verdict (来自干预结果 CSV)
    exp_rows = list(csv.DictReader(
        open(ROOT / "results" / f"main_results_exp17_{tag}.csv",
             encoding="utf-8")))
    exp_map = {(r["sample_id"], r["phase"]): r for r in exp_rows}
    exp_risk = np.array([float(exp_map[(u["sample_id"], u["phase"])]["risk"])
                         for u in units])
    exp_verdict = np.array(
        [exp_map[(u["sample_id"], u["phase"])]["verdict"] for u in units])
    exp_out = exp_verdict == "correct"
    exp_out |= exp_verdict == "wrong"

    vote = voting_per_unit(units)
    vote_out = np.array(
        [vote[(u["sample_id"], u["phase"])][0] is not None for u in units])
    vote_risk = np.array(
        [vote[(u["sample_id"], u["phase"])][1] for u in units])
    vote_verdict = np.array(
        [vote[(u["sample_id"], u["phase"])][2] for u in units])

    rng = np.random.default_rng(SEED)
    deltas = np.empty(N_ITER)
    n_valid = 0
    for it in range(N_ITER):
        idx = []
        for st in rng.choice(stations, size=len(stations), replace=True):
            idx.extend(station_idx[st])
        idx = np.asarray(idx)
        n_boot = len(idx)
        k = int(round(0.5 * n_boot))
        e_out_idx = idx[exp_out[idx]]
        v_out_idx = idx[vote_out[idx]]
        if k > len(e_out_idx) or k > len(v_out_idx):
            deltas[it] = np.nan
            continue
        e_order = e_out_idx[np.argsort(exp_risk[e_out_idx], kind="stable")][:k]
        v_order = v_out_idx[np.argsort(vote_risk[v_out_idx], kind="stable")][:k]
        u_exp = sum(1 for i in e_order if exp_verdict[i] == "wrong") / k * 100
        u_vote = sum(1 for i in v_order if vote_verdict[i] == "wrong") / k * 100
        deltas[it] = u_exp - u_vote
        n_valid += 1

    valid = deltas[~np.isnan(deltas)]
    # 全数据点估计
    n_full = len(units)
    k_full = int(round(0.5 * n_full))
    e_idx = np.where(exp_out)[0]
    v_idx = np.where(vote_out)[0]
    e_top = e_idx[np.argsort(exp_risk[e_idx], kind="stable")][:k_full]
    v_top = v_idx[np.argsort(vote_risk[v_idx], kind="stable")][:k_full]
    p_exp = sum(1 for i in e_top if exp_verdict[i] == "wrong") / k_full * 100
    p_vote = sum(1 for i in v_top if vote_verdict[i] == "wrong") / k_full * 100

    report = {
        "tag": f"EXP17-{tag}",
        "config_version": frozen.version, "config_hash": frozen.sha256,
        "n_units": n_full, "n_stations": len(stations),
        "n_iterations": N_ITER, "seed": SEED,
        "n_valid_resamples": int(n_valid),
        "point_unsafe_exp_50_pct": round(p_exp, 2),
        "point_unsafe_voting_50_pct": round(p_vote, 2),
        "point_delta_pp": round(p_exp - p_vote, 2),
        "bootstrap_mean_delta_pp": round(float(np.mean(valid)), 2),
        "ci95_lo_pp": round(float(np.percentile(valid, 2.5)), 2),
        "ci95_hi_pp": round(float(np.percentile(valid, 97.5)), 2),
        "one_sided_upper95_pp": round(float(np.percentile(valid, 95)), 2),
        "threshold_pp": MAX_DELTA_UPPER_PP,
        "verdict": ("NON-INFERIOR (单侧95%上界 < +2.0pp)"
                    if np.percentile(valid, 95) < MAX_DELTA_UPPER_PP
                    else "NOT_NON-INFERIOR (单侧95%上界 ≥ +2.0pp)"),
    }
    out = ROOT / "results" / f"paired_bootstrap_{tag}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print(f"配对 bootstrap ({tag}): 点估计 Δ={report['point_delta_pp']:+.2f}pp | "
          f"CI[{report['ci95_lo_pp']:+.2f}, {report['ci95_hi_pp']:+.2f}] | "
          f"单侧95%上界 {report['one_sided_upper95_pp']:+.2f}pp "
          f"(阈值 +{MAX_DELTA_UPPER_PP}pp) → {report['verdict']}")
    print(f"有效重采样 {n_valid}/{N_ITER}")
    print(f"✓ {out}")


if __name__ == "__main__":
    main()
