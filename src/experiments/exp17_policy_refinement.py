"""
exp17_policy_refinement.py — EXP17 第二阶段干预执行器 (预注册判据)

按 docs/experiments/exp17_preregistration.md 执行单变量干预:
  --intervention A  consensus_route   (第 4.5 步 Consensus Route)
  --intervention B  only_usable_survivor (预留, 尚未实现)
每个干预独立验收, 输出全部使用 _exp17 后缀新文件, 不覆盖 v1.5.1 产物。

验收判据 (钉死, 最终裁决口径):
  1) 覆盖率天花板 ≥ 50%
  2) Unsafe@50% 相对 Voting@50% 冻结锚点 (4.59%) 的差值, 配对 cluster
     bootstrap (60 台站 × 1000 次, seed 42) 单侧 95% 上界 < +2.0pp
     (配对产物 paired_bootstrap_{tag}.json 存在时以其为准; 内置非配对版只作留存)
  3) Review Budget 曲线保持 (截获@50%预算 ≥ v1.5.1 冻结值)
  4) 风险分箱排序保持单调 (可靠箱 n≥10)
  另: holdout 一致性仅作辅助报告, 不参与 PASS/FAIL

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

FROZEN_REF_UNSAFE_PP = 6.04     # v1.5.1 天花板点 Unsafe (留档引用)
MAX_DELTA_UPPER_PP = 2.0        # C 冻结: 相对 Voting@50% 的单侧 95% 上界 < +2.0pp 视为非劣
GREEN_LIGHT_POINT_PP = 1.0      # C 内部绿灯: 点估计 ΔUnsafe ≤ +1.0pp
N_ITER = 1000
SEED = 42
ENV_POLICIES = {"A": "consensus_route", "B": "only_usable_survivor",
                "AB": "consensus_route,only_usable_survivor"}


def voting_reference_unsafe50():
    """C Gate 2 锚点: Voting@50% 的冻结 Unsafe (baseline_results.csv)."""
    rows = list(csv.DictReader(
        open(ROOT / "results" / "baseline_results.csv", encoding="utf-8")))
    for r in rows:
        if r["strategy"] == "Voting" and r["target_coverage_pct"] == "50":
            return float(r["unsafe_output_rate_pct"])
    raise ValueError("Voting@50% 参照缺失于 baseline_results.csv")


def chain_rows(env_value, floor_override=None):
    """跑冻结链, 返回逐单元行 (env_value=None = v1.5.1 默认路径).

    floor_override: EXP17-C floor sweep 用, 运行时覆盖 fusion_confidence_floor
    (不改冻结配置本身)。
    """
    if env_value:
        os.environ["OBS_EXP17_POLICY"] = env_value
    else:
        os.environ.pop("OBS_EXP17_POLICY", None)
    frozen = load_frozen_config()
    config = frozen.trust_config(ranking_mode=True)
    if floor_override is not None:
        config.fusion_confidence_floor = float(floor_override)
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


def bootstrap_unsafe_delta(rows, reference_pp, n_iter=N_ITER, seed=SEED):
    """60 台站有放回重采样, 每轮算 Unsafe@50%, 返回相对参照点的差值分布."""
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
        deltas[it] = unsafe_boot - reference_pp
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


def risk_bins_evaluate(rows):
    """判据 4: 风险分箱排序保持 (与主实验同口径, 可靠箱 n≥10)."""
    out = [r for r in rows if r["verdict"] in ("correct", "wrong")]
    edges = [(0, 10), (10, 20), (20, 30), (30, 40), (40, 51)]
    result = []
    for lo, hi in edges:
        m = [r for r in out if lo <= float(r["risk"]) < hi]
        if not m:
            result.append({"bin": f"{lo}-{hi-1}", "n": 0,
                           "error_rate_pct": None, "reliable": False})
            continue
        w = sum(1 for r in m if r["verdict"] == "wrong")
        result.append({"bin": f"{lo}-{hi-1}", "n": len(m),
                       "error_rate_pct": round(w / len(m) * 100, 2),
                       "reliable": len(m) >= 10})
    reliable = [r["error_rate_pct"] for r in result if r["reliable"]
                and r["error_rate_pct"] is not None]
    monotonic = all(a <= b for a, b in zip(reliable, reliable[1:]))
    return {"bins": result, "monotonic_reliable_bins": bool(monotonic)}


def review_curve_reference():
    """v1.5.1 冻结的 Review Budget 截获@50% 预算 (EXP16 冻结产物)."""
    import json as _json
    with open(ROOT / "results" / "review_budget_summary.json",
              encoding="utf-8") as f:
        ref = _json.load(f)["fixed_budget_interception_pct"]["50"]["TrustRisk"]
    return float(ref)


def paired_bootstrap_reference(tag):
    """C Gate 2 最终裁定口径: 读配对 cluster bootstrap 冻结产物.

    paired_bootstrap_{tag}.json 若存在, 以其单侧 95% 上界作为 c2 门禁数值;
    内置 bootstrap_unsafe_delta (参照点固定) 只作诊断留存, 不参与门禁。
    """
    p = ROOT / "results" / f"paired_bootstrap_{tag}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def run_intervention(tag, env_value, frozen):
    rows, _frozen = chain_rows(env_value)
    out_csv = ROOT / "results" / f"main_results_exp17_{tag}.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    m = evaluate(rows)
    ho = holdout_stats(rows)
    voting_ref = voting_reference_unsafe50()
    boot = bootstrap_unsafe_delta(rows, voting_ref)
    paired = paired_bootstrap_reference(tag)
    gate_boot = paired if paired is not None else boot
    bootstrap_source = (f"paired_bootstrap_{tag}.json"
                        if paired is not None else "in-runner non-paired")
    bins = risk_bins_evaluate(rows)
    ref_inter = review_curve_reference()

    crit1 = m["ceiling_pct"] >= 50.0
    crit2 = (m["feasible_50"]
             and gate_boot["one_sided_upper95_pp"] < MAX_DELTA_UPPER_PP)
    green_light = (m["unsafe_50_pct"] is not None
                   and (m["unsafe_50_pct"] - voting_ref) <= GREEN_LIGHT_POINT_PP)
    # 判据 3 (C 指示): Review Budget 曲线保持 — 截获@50%预算不低于 v1.5.1 冻结值
    crit3 = m["interception_50_budget_pct"] >= ref_inter - 1e-9
    # 判据 4 (C 指示): 风险分箱排序保持单调 (可靠箱 n≥10)
    crit4 = bins["monotonic_reliable_bins"]
    verdict = "PASS" if all((crit1, crit2, crit3, crit4)) else "FAIL"

    summary = {
        "intervention": f"EXP17-{tag}",
        "policy": env_value,
        "config_version": frozen.version, "config_hash": frozen.sha256,
        "metrics": m, "holdout": ho, "unsafe_delta_bootstrap": boot,
        "unsafe_delta_bootstrap_paired": paired,
        "risk_bins": bins,
        "review_curve_reference_interception_50_pct": ref_inter,
        "criteria": {
            "c1_ceiling_ge_50": {"pass": bool(crit1),
                                 "value_pct": round(m["ceiling_pct"], 2)},
            "c2_non_inferiority_vs_voting_2pp": {
                "pass": bool(crit2),
                "voting_unsafe_50_pct": voting_ref,
                "point_delta_pp": (round(m["unsafe_50_pct"] - voting_ref, 2)
                                   if m["unsafe_50_pct"] is not None else None),
                "one_sided_upper95_pp": gate_boot["one_sided_upper95_pp"],
                "bootstrap_source": bootstrap_source,
                "threshold_pp": MAX_DELTA_UPPER_PP,
                "green_light_point_le_1pp": bool(green_light)},
            "c3_review_curve_preserved": {
                "pass": bool(crit3),
                "interception_50_budget_pct":
                    m["interception_50_budget_pct"],
                "reference_pct": ref_inter},
            "c4_risk_bin_ordering_preserved": {
                "pass": bool(crit4),
                "monotonic": bins["monotonic_reliable_bins"]},
        },
        "verdict": verdict,
    }
    out_summary = ROOT / "results" / f"exp17_summary_{tag}.json"
    out_summary.write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                           encoding="utf-8")

    print(f"[{tag}] 天花板 {m['ceiling_pct']:.2f}% | "
          f"50% 点 Unsafe {m['unsafe_50_pct']} (feasible={m['feasible_50']}) | "
          f"截获@50%预算 {m['interception_50_budget_pct']}%")
    print(f"      ΔUnsafe 单侧95%上界 {gate_boot['one_sided_upper95_pp']:+.2f}pp "
          f"(阈值 +{MAX_DELTA_UPPER_PP}pp, 来源 {bootstrap_source}) | "
          f"CI[{gate_boot['ci95_lo_pp']:+.2f}, "
          f"{gate_boot['ci95_hi_pp']:+.2f}]")
    print(f"      holdout 天花板 {ho['holdout_ceiling_pct']}% | Unsafe@天花板 "
          f"{ho['holdout_unsafe_at_ceiling_pct']}%")
    print(f"      风险分箱: {[b['error_rate_pct'] for b in bins['bins'] if b['reliable']]} "
          f"(单调={bins['monotonic_reliable_bins']}) | 截获@50%预算 "
          f"{m['interception_50_budget_pct']}% (冻结参照 {ref_inter}%)")
    print(f"      判据: c1={crit1} c2={crit2} c3={crit3} c4={crit4} → **{verdict}**")
    print(f"✓ {out_csv}")
    print(f"✓ {out_summary}")


def run_floor_sweep(frozen):
    """EXP17-C: fusion floor sweep 留档实验 (0.70→0.65→0.60→0.55).

    只改运行时的 fusion_confidence_floor, 不改冻结配置; 逐级完整报告
    Coverage/Unsafe/截获/分箱; 只有达到 50% 的级别才补 bootstrap
    (预注册: sweep 为留档实验, 不自动升级任何级别为正式参数)。
    """
    levels = [0.70, 0.65, 0.60, 0.55]
    ref_inter = review_curve_reference()
    report = {"config_version": frozen.version, "config_hash": frozen.sha256,
              "levels": {}}
    print(f"{'floor':>6} {'天花板':>8} {'Unsafe@50':>10} {'截获@50预算':>11} "
          f"{'分箱单调':>8} {'c1':>4}")
    for lv in levels:
        rows, _frozen = chain_rows(None, floor_override=lv)
        tag = f"floorsweep_{lv}"
        out_csv = ROOT / "results" / f"main_results_{tag}.csv"
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        m = evaluate(rows)
        bins = risk_bins_evaluate(rows)
        c1 = m["ceiling_pct"] >= 50.0
        c3 = m["interception_50_budget_pct"] >= ref_inter - 1e-9
        c4 = bins["monotonic_reliable_bins"]
        entry = {
            "floor": lv, "metrics": m, "risk_bins": bins,
            "criteria": {"c1_ceiling_ge_50": bool(c1),
                         "c3_review_curve_preserved": bool(c3),
                         "c4_risk_bin_ordering_preserved": bool(c4)},
        }
        if c1 and m["feasible_50"]:
            boot = bootstrap_unsafe_delta(rows, voting_reference_unsafe50())
            entry["unsafe_delta_bootstrap"] = boot
            entry["criteria"]["c2_non_inferiority_vs_voting_2pp"] = (
                boot["one_sided_upper95_pp"] < MAX_DELTA_UPPER_PP)
        report["levels"][str(lv)] = entry
        print(f"{lv:>6} {m['ceiling_pct']:>7.2f}% "
              f"{str(m['unsafe_50_pct']):>10} "
              f"{m['interception_50_budget_pct']:>10.2f}% "
              f"{str(bins['monotonic_reliable_bins']):>8} {str(c1):>4}")
    out = ROOT / "results" / "floor_sweep.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print(f"✓ {out}")
    print("结论口径: 留档实验 — 若各级天花板均 <50%, 证明 coverage ceiling "
          "不是 confidence floor 造成的 (与诊断 101/112 静态证据一致)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--intervention", choices=["A", "B"], default="A")
    parser.add_argument("--floor-sweep", action="store_true")
    args = parser.parse_args()

    # 0) v1.5.1 默认路径对账 (改动不得影响冻结行为)
    rows_base, frozen = chain_rows(None)
    diffs, n_ref = baseline_parity_check(
        rows_base, ROOT / "results" / "main_results.csv")
    print(f"[0] v1.5.1 默认路径对账: {n_ref} 单元, 差异 {diffs} 个 "
          f"{'✓' if diffs == 0 else '✗ FAIL'}")

    if args.floor_sweep:
        run_floor_sweep(frozen)
        return
    if args.intervention == "A":
        run_intervention("A", ENV_POLICIES["A"], frozen)
    else:
        # B: 单独验收 + 按预注册顺序累加 A+B 后复验
        run_intervention("B", ENV_POLICIES["B"], frozen)
        run_intervention("AB", ENV_POLICIES["AB"], frozen)


if __name__ == "__main__":
    main()
