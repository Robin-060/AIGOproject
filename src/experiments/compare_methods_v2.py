"""
全方法对比表 (v2 规则) — 相位级 Equal-Coverage

Trust Layer 用 v2 档案 (hydrophone_v2); 基线不受档案影响 (直接用冻结预测)。
比较点位: 46.7% (Trust 覆盖率天花板) 与 50% (标准点)。
输出: results/method_comparison_v2.csv + stdout 摘要表

用法:
    python -m src.experiments.compare_methods_v2
"""

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import warnings  # noqa: E402
warnings.filterwarnings("ignore")

from src.experiments.phase_evaluation import (  # noqa: E402
    build_phase_units,
    load_records,
)
from src.experiments.random_baseline import (  # noqa: E402
    evaluate_across_seeds as random_across_seeds,
    find_p_for_coverage as random_find_p,
)
from src.experiments.run_baselines import (  # noqa: E402
    strat_maxconf,
    strat_single,
    strat_traditional,
    strat_vote,
    top_k_gate,
    with_confidence,
)

OUT_CSV = ROOT / "results" / "method_comparison_v2.csv"
POINTS = [46.7, 50.0]


def unsafe_at(units, output_fn, risk_fn, target_pct):
    primary = [u for u in units if u["primary_inclusion"]]
    risks = {(u["sample_id"], u["phase"]): risk_fn(u) for u in primary}
    gate = top_k_gate(units, risks, target_pct / 100.0)
    correct = wrong = 0
    for u in primary:
        if not gate(u):
            continue
        out = output_fn(u)
        if out is None:
            continue
        truth = u["reference_time_s"]
        tol = 0.5 if u["phase"] == "P" else 1.0
        if abs(out - truth) <= tol:
            correct += 1
        else:
            wrong += 1
    auto = correct + wrong
    return wrong / auto * 100 if auto else float("nan"), auto / len(primary) * 100


def main():
    records = load_records()
    units = with_confidence(build_phase_units(records), records)
    strategies = {
        "Single-PickBlue": strat_single("PickBlue"),
        "Single-OBSTransformer": strat_single("OBSTransformer"),
        "Single-PhaseNet": strat_single("PhaseNet"),
        "MaxConf": strat_maxconf(),
        "Voting": strat_vote(),
        "Traditional-STA/LTA": strat_traditional(),
    }
    rows = []
    print(f"{'方法':>22} | {'46.7% Unsafe':>11} | {'实际Cov':>7} | {'50% Unsafe':>9} | {'实际Cov':>7}")
    print("-" * 72)
    for name, (out_fn, risk_fn) in strategies.items():
        cell = {}
        for point in POINTS:
            unsafe, cov = unsafe_at(units, out_fn, risk_fn, point)
            cell[point] = (unsafe, cov)
        rows.append({
            "method": name,
            "unsafe_46.7": round(cell[46.7][0], 2), "cov_46.7": round(cell[46.7][1], 2),
            "unsafe_50": round(cell[50.0][0], 2), "cov_50": round(cell[50.0][1], 2),
        })
        print(f"{name:>22} | {cell[46.7][0]:>9.1f}% | {cell[46.7][1]:>6.1f}% | "
              f"{cell[50.0][0]:>8.1f}% | {cell[50.0][1]:>6.1f}%")

    # Random (多种子)
    rand_cells = {}
    for point in POINTS:
        p = random_find_p(units, point)
        stat = random_across_seeds(units, p)
        rand_cells[point] = (stat["unsafe_output_rate"] * 100, stat["coverage"] * 100)
    rows.append({
        "method": "Random",
        "unsafe_46.7": round(rand_cells[46.7][0], 2), "cov_46.7": round(rand_cells[46.7][1], 2),
        "unsafe_50": round(rand_cells[50.0][0], 2), "cov_50": round(rand_cells[50.0][1], 2),
    })
    print(f"{'Random':>22} | {rand_cells[46.7][0]:>9.1f}% | {rand_cells[46.7][1]:>6.1f}% | "
          f"{rand_cells[50.0][0]:>8.1f}% | {rand_cells[50.0][1]:>6.1f}%")

    # Trust v2 (from v2 主实验结果)
    trust = {}
    with open(ROOT / "results" / "equal_coverage_trust.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            trust[row["target_coverage_pct"]] = (
                float(row["unsafe_output_rate_pct"]),
                float(row["coverage_pct"]),
            )
    t_unsafe, t_cov = trust["50"]  # v2 全部点位都落在天花板 46.7%
    rows.append({
        "method": "TrustLayer(v2)",
        "unsafe_46.7": round(t_unsafe, 2), "cov_46.7": round(t_cov, 2),
        "unsafe_50": "", "cov_50": "不可达",
    })
    print("-" * 72)
    print(f"{'TrustLayer(v2)':>22} | {t_unsafe:>9.1f}% | {t_cov:>6.1f}% | "
          f"{'(覆盖率天花板 46.7%)':>8}")

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n✓ {OUT_CSV}")


if __name__ == "__main__":
    main()
