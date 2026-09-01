"""
exp17_policy_refinement.py — EXP17 第二阶段干预执行器 (预注册判据)

按 docs/experiments/exp17_preregistration.md 执行单变量干预:
  --intervention A  consensus_route   (第 4.5 步 Consensus Route)
  --intervention B  only_usable_survivor (预留, 尚未实现)
每个干预独立验收, 输出全部使用 _exp17 后缀新文件, 不覆盖 v1.5.1 产物。

验收判据 (钉死):
  1) 覆盖率天花板 ≥ 50%
  2) Unsafe@50% 与 v1.5.1 天花板点 6.04% 的差值, cluster paired bootstrap
     (60 台站 × 1000 次, seed 42) 单侧 95% 上界 < +2.0pp
  3) holdout 一致性 (覆盖率不下降, Unsafe 方向不矛盾) — 辅助报告
  4) Error Interception@50% 复核预算 — 仅报告

用法:
  python -m src.experiments.exp17_policy_refinement --intervention A
"""

import argparse
import csv
import json
import os
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
from src.experiments.run_main_experiment import (  # noqa: E402
    build_unit_rows,
    load_quality,
    load_split,
)
from src.trust_engine.config_loader import load_frozen_config  # noqa: E402

FROZEN_REF_UNSAFE_PP = 6.04     # v1.5.1 天花板点 Unsafe (bootstrap ALL_ceiling_supplementary)
MAX_DELTA_UPPER_PP = 2.0        # 预注册: 单侧 95% 上界 < +2.0pp 视为不显著恶化
N_ITER = 1000
SEED = 42
ENV_POLICIES = {"A": "consensus_route", "B": "only_usable_survivor",
                "AB": "consensus_route,only_usable_survivor"}


def chain_rows(env_value):
    """跑冻结链, 返回逐单元行 (env_value=None = v1.5.1 默认路径)."""
    if env_value:
        os.environ["OBS_EXP17_POLICY"] = env_value
    else:
        os.environ.pop("OBS_EXP17_POLICY", None)
    frozen = load_frozen_config()
    config = frozen.trust_config(ranking_mode=True)
    profiles = frozen.model_profiles()
    records = load_records()
    quality_map = load_quality()
    split_map = load_split()
    units = [u for u in build_phase_units(records) if u["primary_inclusion"]]
    for u in units:
        u["split"] = split_map.get((u["sample_id"], u["phase"]), "main")
    record_map = {r["sample_id"]: r for r in records}
    return build_unit_rows(records, units, quality_map, profiles, config,
                           record_map), frozen


def evaluate(rows):
    """主判据 1/2/4 的指标计算 (50% 点 + 天花板 + 截获)."""
    n = len(rows)
    output = [r for r in rows if r["verdict"] in ("correct", "wrong")]
    ceiling = len(output) / n * 100
    errors = [r for r in rows if r["verdict"] in ("wrong", "no_pick")]
    by_risk = sorted(rows, key=lambda r: (r["risk"], r["sample_id"], r["phase"]))
    out_by_risk = sorted(output, key=lambda r: (r["risk"], r["sample_id"],
                                                r["phase"]))
    k50 = int(round(0.5 * n))
    feasible = k50 <= len(out_by_risk)
    if feasible:
        accepted = {(r["sample_id"], r["phase"]) for r in out_by_risk[:k50]}
        auto = wrong = 0
        for r in output:
            if (r["sample_id"], r["phase"]) in accepted:
                auto += 1
                if r["verdict"] == "wrong":
                    wrong += 1
        unsafe50 = wrong / auto * 100 if auto else float("nan")
    else:
        unsafe50 = None
    # 复核队列 = 风险最高者优先 (与 EXP16 同口径)
    reviewed = {(r["sample_id"], r["phase"]) for r in by_risk[-k50:]}
    inter50 = (sum(1 for r in errors if (r["sample_id"], r["phase"]) in reviewed)
               / len(errors) * 100) if errors else 0.0
    return {"n": n, "ceiling_pct": ceiling, "feasible_50": feasible,
            "unsafe_50_pct": (round(unsafe50, 2) if unsafe50 is not None else None),
            "review_burden_50_pct": round((n - k50) / n * 100, 2),
            "interception_50_budget_pct": round(inter50, 2)}


def holdout_stats(rows):
    ho = [r for r in rows if r["split"] == "holdout"]
    n = len(ho)
    output = [r for r in ho if r["verdict"] in ("correct", "wrong")]
    ceiling = len(output) / n * 100 if n else 0.0
    wrong = sum(1 for r in output if r["verdict"] == "wrong")
    unsafe = wrong / len(output) * 100 if output else float("nan")
    return {"n_holdout": n, "holdout_ceiling_pct": round(ceiling, 2),
            "holdout_unsafe_at_ceiling_pct": round(unsafe, 2)}


def bootstrap_unsafe_delta(rows, n_iter=N_ITER, seed=SEED):
    """60 台站有放回重采样, 每轮算 Unsafe@50%, 返回相对 6.04% 的差值分布."""
    stations = sorted({r["station"] for r in rows})
    station_idx = {st: [] for st in stations}
    for i, r in enumerate(rows):
        station_idx[r["station"]].append(i)
    output_mask = np.array([r["verdict"] in ("correct", "wrong") for r in rows])
    risk = np.array([r["risk"] for r in rows])
    rng = np.random.default_rng(seed)
    deltas = np.empty(n_iter)
    for it in range(n_iter):
        idx = []
        for st in rng.choice(stations, size=len(stations), replace=True):
            idx.extend(station_idx[st])
        idx = np.asarray(idx)
        n_boot = len(idx)
        k = int(round(0.5 * n_boot))
        out_idx = idx[output_mask[idx]]
        if k > len(out_idx):
            deltas[it] = np.nan
            continue
        order = out_idx[np.argsort(risk[out_idx], kind="stable")][:k]
        wrong = sum(1 for i in order if rows[i]["verdict"] == "wrong")
        unsafe_boot = wrong / k * 100
        deltas[it] = unsafe_boot - FROZEN_REF_UNSAFE_PP
    valid = deltas[~np.isnan(deltas)]
    return {"delta_mean_pp": round(float(np.nanmean(deltas)), 2),
            "ci95_lo_pp": round(float(np.percentile(valid, 2.5)), 2),
            "ci95_hi_pp": round(float(np.percentile(valid, 97.5)), 2),
            "one_sided_upper95_pp": round(float(np.percentile(valid, 95)), 2),
            "n_valid_resamples": int(len(valid))}


def baseline_parity_check(rows, frozen_ref_csv):
    """默认路径 (env 未设) 与 v1.5.1 冻结结果逐单元对账."""
    ref = list(csv.DictReader(open(frozen_ref_csv, encoding="utf-8")))
    ref_map = {(r["sample_id"], r["phase"]): r for r in ref}
    diffs = 0
    for r in rows:
        rr = ref_map.get((r["sample_id"], r["phase"]))
        if rr is None:
            diffs += 1
            continue
        if (rr["action"] != r["action"] or rr["verdict"] != r["verdict"]
                or abs(float(rr["risk"]) - float(r["risk"])) > 0.005):
            diffs += 1
    return diffs, len(ref)


def run_intervention(tag, env_value, frozen):
    rows, _frozen = chain_rows(env_value)
    out_csv = ROOT / "results" / f"main_results_exp17_{tag}.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    m = evaluate(rows)
    ho = holdout_stats(rows)
    boot = bootstrap_unsafe_delta(rows)

    crit1 = m["ceiling_pct"] >= 50.0
    crit2 = (m["feasible_50"] and boot["one_sided_upper95_pp"] < MAX_DELTA_UPPER_PP)
    verdict = "PASS" if (crit1 and crit2) else "FAIL"

    summary = {
        "intervention": f"EXP17-{tag}",
        "policy": env_value,
        "config_version": frozen.version, "config_hash": frozen.sha256,
        "metrics": m, "holdout": ho, "unsafe_delta_bootstrap": boot,
        "criteria": {
            "c1_ceiling_ge_50": {"pass": bool(crit1),
                                 "value_pct": round(m["ceiling_pct"], 2)},
            "c2_unsafe_not_significantly_worse": {
                "pass": bool(crit2),
                "one_sided_upper95_pp": boot["one_sided_upper95_pp"],
                "threshold_pp": MAX_DELTA_UPPER_PP,
                "reference_unsafe_pp": FROZEN_REF_UNSAFE_PP},
        },
        "verdict": verdict,
    }
    out_summary = ROOT / "results" / f"exp17_summary_{tag}.json"
    out_summary.write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                           encoding="utf-8")

    print(f"[{tag}] 天花板 {m['ceiling_pct']:.2f}% | "
          f"50% 点 Unsafe {m['unsafe_50_pct']} (feasible={m['feasible_50']}) | "
          f"截获@50%预算 {m['interception_50_budget_pct']}%")
    print(f"      ΔUnsafe 单侧95%上界 {boot['one_sided_upper95_pp']:+.2f}pp "
          f"(阈值 +{MAX_DELTA_UPPER_PP}pp) | CI[{boot['ci95_lo_pp']:+.2f}, "
          f"{boot['ci95_hi_pp']:+.2f}]")
    print(f"      holdout 天花板 {ho['holdout_ceiling_pct']}% | Unsafe@天花板 "
          f"{ho['holdout_unsafe_at_ceiling_pct']}%")
    print(f"      判据: c1={crit1} c2={crit2} → **{verdict}**")
    print(f"✓ {out_csv}")
    print(f"✓ {out_summary}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--intervention", choices=["A", "B"], default="A")
    args = parser.parse_args()

    # 0) v1.5.1 默认路径对账 (改动不得影响冻结行为)
    rows_base, frozen = chain_rows(None)
    diffs, n_ref = baseline_parity_check(
        rows_base, ROOT / "results" / "main_results.csv")
    print(f"[0] v1.5.1 默认路径对账: {n_ref} 单元, 差异 {diffs} 个 "
          f"{'✓' if diffs == 0 else '✗ FAIL'}")

    if args.intervention == "A":
        run_intervention("A", ENV_POLICIES["A"], frozen)
    else:
        # B: 单独验收 + 按预注册顺序累加 A+B 后复验
        run_intervention("B", ENV_POLICIES["B"], frozen)
        run_intervention("AB", ENV_POLICIES["AB"], frozen)


if __name__ == "__main__":
    main()
