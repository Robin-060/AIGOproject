"""
统一 baseline 运行器 — 8/30 交付物 (提前开工)

在 1306 个相位级评估单元上, 按 Equal-Coverage 协议 (semifinal_v1.1) 运行:
  - Random            (已实现于 random_baseline.py, 此处复用)
  - Single-PhaseNet / Single-PickBlue / Single-OBSTransformer  (C 契约: 三模型分别作基线)
  - MaxConf           (risk = 1 - max raw score)
  - Voting            (中位数 + risk=clip(spread/severe_threshold,0,1))
  - Traditional STA/LTA (单独脚本 sta_lta_baseline.py, 需本地波形)

各策略通过风险排序门控对齐 Coverage = 50/60/70/80/90%;
无法达到目标点时报告其 max achievable coverage。

输出: results/baseline_results.csv + figures/coverage_vs_unsafe.png

用法:
    python -m src.experiments.run_baselines
"""

import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.experiments.phase_evaluation import (
    MODELS,
    build_phase_units,
    evaluate_units,
    load_records,
)
from src.experiments.random_baseline import (
    evaluate_across_seeds as random_across_seeds,
    find_p_for_coverage as random_find_p,
    make_gate as random_gate,
    underlying_output as random_output,
)

ROOT = Path(__file__).resolve().parents[2]
OUT_CSV = ROOT / "results" / "baseline_results.csv"
OUT_FIG = ROOT / "figures" / "coverage_vs_unsafe.png"

COVERAGE_POINTS = [50, 60, 70, 80, 90]
SEVERE_THRESHOLD = {"P": 1.0, "S": 2.0}   # 暂用候选值, validation 冻结前标记 provisional


def conf_of(unit, model):
    """冻结记录中该模型的置信度 (P/S 共用, 冻结字段)."""
    return unit.get("confidence", {}).get(model)


def with_confidence(units, records):
    """把冻结置信度挂到每个单元上."""
    conf = {}
    for record in records:
        preds = record["predictions"]
        conf[record["sample_id"]] = {
            m: (preds.get(m) or {}).get("confidence") or 0.0 for m in MODELS
        }
    for unit in units:
        unit["confidence"] = conf[unit["sample_id"]]
    return units


# ── 各策略的输出与风险 ──

def strat_single(model):
    def output(unit):
        return unit["predictions"].get(model)
    def risk(unit):
        pick = unit["predictions"].get(model)
        if pick is None:
            return 1.0
        return 1.0 - min(max(conf_of(unit, model), 0.0), 1.0)
    return output, risk


def strat_maxconf():
    def output(unit):
        best_model, best_pick, best_conf = None, None, -1.0
        for model in MODELS:
            pick = unit["predictions"].get(model)
            if pick is None:
                continue
            c = conf_of(unit, model)
            if c > best_conf:
                best_model, best_pick, best_conf = model, pick, c
        return best_pick
    def risk(unit):
        confs = [conf_of(unit, m) for m in MODELS
                 if unit["predictions"].get(m) is not None]
        return 1.0 - min(max(max(confs), 0.0), 1.0) if confs else 1.0
    return output, risk


def strat_vote():
    def output(unit):
        picks = [unit["predictions"][m] for m in MODELS
                 if unit["predictions"].get(m) is not None]
        if not picks:
            return None
        return float(np.median(picks))
    def risk(unit):
        picks = [unit["predictions"][m] for m in MODELS
                 if unit["predictions"].get(m) is not None]
        if len(picks) < 2:
            return 1.0
        spread = max(picks) - min(picks)
        severe = SEVERE_THRESHOLD[unit["phase"]]
        return float(np.clip(spread / severe, 0.0, 1.0))
    return output, risk


def strat_traditional():
    """STA/LTA 传统基线 (协议见 sta_lta_baseline.py)."""
    picks_path = ROOT / "data" / "sta_lta_picks.csv"
    rows = {row["sample_id"]: row
            for row in csv.DictReader(picks_path.read_text(encoding="utf-8").splitlines())}

    def output(unit):
        row = rows.get(unit["sample_id"])
        if row is None:
            return None
        value = row["p_onset_s"] if unit["phase"] == "P" else row["s_onset_s"]
        return float(value) if value else None

    def risk(unit):
        row = rows.get(unit["sample_id"])
        if row is None:
            return 1.0
        ratio = row["p_peak_ratio"] if unit["phase"] == "P" else row["s_peak_ratio"]
        if not ratio:
            return 1.0
        return float(1.0 / (1.0 + float(ratio)))

    return output, risk


# ── 风险排序门控对齐 coverage ──

def top_k_gate(units, risks, target_frac):
    """按 (risk, sample_id, phase) 排序, 接受前 k 个单元 (确定性 tie-break)."""
    primary = [u for u in units if u["primary_inclusion"]]
    ordered = sorted(primary, key=lambda u: (risks[u["sample_id"], u["phase"]],
                                             u["sample_id"], u["phase"]))
    k = int(round(target_frac * len(primary)))
    accepted = {(u["sample_id"], u["phase"]) for u in ordered[:k]}
    return lambda unit: (unit["sample_id"], unit["phase"]) in accepted


def run_gated(units, output_fn, risk_fn, target_pct):
    risks = {(u["sample_id"], u["phase"]): risk_fn(u)
             for u in units if u["primary_inclusion"]}
    gate = top_k_gate(units, risks, target_pct / 100.0)
    stats = evaluate_units(units, output_fn, gate)
    stats["max_coverage"] = sum(
        1 for u in units if u["primary_inclusion"]
        and output_fn(u) is not None
    ) / sum(1 for u in units if u["primary_inclusion"])
    return stats


def main():
    records = load_records()
    units = with_confidence(build_phase_units(records), records)
    n_eval = sum(1 for u in units if u["primary_inclusion"])
    print(f"评估单元: {n_eval} | 覆盖率点: {COVERAGE_POINTS}")

    strategies = {
        "Single-PhaseNet": strat_single("PhaseNet"),
        "Single-PickBlue": strat_single("PickBlue"),
        "Single-OBSTransformer": strat_single("OBSTransformer"),
        "MaxConf": strat_maxconf(),
        "Voting": strat_vote(),
        "Traditional-STA/LTA": strat_traditional(),
    }

    rows = []
    chart = {name: {"cov": [], "unsafe": []} for name in strategies}
    print(f"\n{'策略':>22} {'目标Cov':>7} {'实际Cov':>8} {'Unsafe':>8} {'Burden':>8} {'拦截率':>8}")
    for name, (output_fn, risk_fn) in strategies.items():
        for target in COVERAGE_POINTS:
            stats = run_gated(units, output_fn, risk_fn, target)
            rows.append({
                "strategy": name, "target_coverage_pct": target,
                "coverage_pct": round(stats["coverage"] * 100, 2),
                "unsafe_output_rate_pct": round(stats["unsafe_output_rate"] * 100, 2),
                "review_burden_pct": round(stats["review_burden"] * 100, 2),
                "error_interception_rate_pct": round(stats["error_interception_rate"] * 100, 2),
                "max_coverage_pct": round(stats["max_coverage"] * 100, 2),
            })
            chart[name]["cov"].append(stats["coverage"] * 100)
            chart[name]["unsafe"].append(stats["unsafe_output_rate"] * 100)
            print(f"{name:>22} {target:>6}% {stats['coverage']*100:>7.1f}% "
                  f"{stats['unsafe_output_rate']*100:>7.1f}% "
                  f"{stats['review_burden']*100:>7.1f}% "
                  f"{stats['error_interception_rate']*100:>7.1f}%")

    # Random (多种子, 独立协议); 随机拒绝与错误独立 → 拦截率 = 1 - coverage
    chart["Random"] = {"cov": [], "unsafe": []}
    obst_pick_frac = sum(
        1 for u in units
        if u["primary_inclusion"] and random_output(u) is not None
    ) / sum(1 for u in units if u["primary_inclusion"])
    for target in COVERAGE_POINTS:
        p = random_find_p(units, target)
        stat = random_across_seeds(units, p)
        rows.append({
            "strategy": "Random", "target_coverage_pct": target,
            "coverage_pct": round(stat["coverage"] * 100, 2),
            "unsafe_output_rate_pct": round(stat["unsafe_output_rate"] * 100, 2),
            "review_burden_pct": round((1 - stat["coverage"]) * 100, 2),
            "error_interception_rate_pct": round((1 - stat["coverage"]) * 100, 2),
            "max_coverage_pct": round(obst_pick_frac * 100, 2),
        })
        chart["Random"]["cov"].append(stat["coverage"] * 100)
        chart["Random"]["unsafe"].append(stat["unsafe_output_rate"] * 100)
        print(f"{'Random':>22} {target:>6}% {stat['coverage']*100:>7.1f}% "
              f"{stat['unsafe_output_rate']*100:>7.1f}% (100 seeds)")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    # 图: Coverage vs Unsafe (所有策略)
    colors = {
        "Single-PhaseNet": "#9E9E9E", "Single-PickBlue": "#9E9E9E",
        "Single-OBSTransformer": "#607D8B", "MaxConf": "#FF9800",
        "Voting": "#2196F3", "Random": "#F44336",
        "Traditional-STA/LTA": "#795548",
    }
    fig, ax = plt.subplots(figsize=(10, 6))
    for name, data in chart.items():
        ax.plot(data["cov"], data["unsafe"], "o-", label=name,
                color=colors[name], linewidth=2, markersize=6)
    ax.set_xlabel("Coverage (%)")
    ax.set_ylabel("Unsafe Output Rate (%)")
    ax.set_title("Equal-Coverage Comparison on 1306 Phase Units (semifinal_v1.1)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    OUT_FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_FIG, dpi=150)
    plt.close(fig)
    print(f"\n✓ {OUT_CSV}")
    print(f"✓ {OUT_FIG}")


if __name__ == "__main__":
    main()
