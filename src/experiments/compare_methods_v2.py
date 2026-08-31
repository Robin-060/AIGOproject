"""
全方法对比表 (v2 规则) — 相位级 Equal-Coverage

Trust Layer 用 v2 档案 (hydrophone_v2); 基线不受档案影响 (直接用冻结预测)。
比较点位: 当前 Trust 精确覆盖率天花板（补充）与 50%（声明点）。
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
from src.trust_engine.config_loader import load_frozen_config  # noqa: E402

OUT_CSV = ROOT / "results" / "method_comparison_v2.csv"


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
    coverage = auto / len(primary) * 100
    feasible = coverage + 1e-9 >= target_pct
    return (wrong / auto * 100 if auto else float("nan")), coverage, feasible


def main():
    frozen = load_frozen_config()
    records = load_records()
    units = with_confidence(build_phase_units(records), records)
    import csv as _csv
    trust_rows = list(_csv.DictReader(
        open(ROOT / "results" / "main_results.csv", encoding="utf-8")))
    output_rows = [r for r in trust_rows if r["verdict"] in ("correct", "wrong")]
    output_sorted = sorted(output_rows,
                           key=lambda r: (float(r["risk"]), r["sample_id"], r["phase"]))
    trust_ceiling = len(output_rows) / len(trust_rows) * 100
    points = [trust_ceiling, 50.0]
    strategies = {
        "Single-PickBlue": strat_single("PickBlue"),
        "Single-OBSTransformer": strat_single("OBSTransformer"),
        "Single-EQTransformer": strat_single("EQTransformer"),
        "Single-PhaseNet": strat_single("PhaseNet"),
        "MaxConf": strat_maxconf(),
        "Voting": strat_vote(),
        "Traditional-STA/LTA": strat_traditional(),
    }
    rows = []
    print(f"{'方法':>22} | {'天花板 Unsafe':>12} | {'实际Cov':>7} | {'50% Unsafe':>9} | {'实际Cov':>7}")
    print("-" * 72)
    for name, (out_fn, risk_fn) in strategies.items():
        cell = {}
        for point in points:
            unsafe, cov, feasible = unsafe_at(units, out_fn, risk_fn, point)
            cell[point] = (unsafe, cov, feasible)
        rows.append({
            "method": name,
            "supplementary_target_pct": round(trust_ceiling, 4),
            "unsafe_at_ceiling": (round(cell[trust_ceiling][0], 2)
                                   if cell[trust_ceiling][2] else ""),
            "cov_at_ceiling": round(cell[trust_ceiling][1], 2),
            "status_at_ceiling": ("COMPARABLE" if cell[trust_ceiling][2]
                                  else "NOT_COMPARABLE_AT_TARGET"),
            "unsafe_50": (round(cell[50.0][0], 2) if cell[50.0][2] else ""),
            "cov_50": round(cell[50.0][1], 2),
            "status_50": "COMPARABLE" if cell[50.0][2] else "NOT_COMPARABLE_AT_TARGET",
            "config_version": frozen.version,
            "config_hash": frozen.sha256,
        })
        print(f"{name:>22} | {cell[trust_ceiling][0]:>9.1f}% | {cell[trust_ceiling][1]:>6.1f}% | "
              f"{cell[50.0][0]:>8.1f}% | {cell[50.0][1]:>6.1f}%")

    # Random (多种子)
    rand_cells = {}
    for point in points:
        p = random_find_p(units, point)
        stat = random_across_seeds(units, p)
        rand_cells[point] = (stat["unsafe_output_rate"] * 100, stat["coverage"] * 100)
    rows.append({
        "method": "Random",
        "supplementary_target_pct": round(trust_ceiling, 4),
        "unsafe_at_ceiling": round(rand_cells[trust_ceiling][0], 2),
        "cov_at_ceiling": round(rand_cells[trust_ceiling][1], 2),
        "status_at_ceiling": "COMPARABLE",
        "unsafe_50": round(rand_cells[50.0][0], 2), "cov_50": round(rand_cells[50.0][1], 2),
        "status_50": "COMPARABLE",
        "config_version": frozen.version,
        "config_hash": frozen.sha256,
    })
    print(f"{'Random':>22} | {rand_cells[trust_ceiling][0]:>9.1f}% | {rand_cells[trust_ceiling][1]:>6.1f}% | "
          f"{rand_cells[50.0][0]:>8.1f}% | {rand_cells[50.0][1]:>6.1f}%")

    # Trust frozen config (从 main_results.csv 直接算 + NOT_EVALUABLE 纪律)

    def trust_cell(point):
        requested = int(round(point / 100 * len(trust_rows)))
        feasible = requested <= len(output_sorted)
        k = min(requested, len(output_sorted))
        accepted = {(r["sample_id"], r["phase"]) for r in output_sorted[:k]}
        wrong = total = 0
        for row in trust_rows:
            if (row["sample_id"], row["phase"]) in accepted:
                total += 1
                if row["verdict"] == "wrong":
                    wrong += 1
        unsafe = wrong / total * 100 if total else float("nan")
        return unsafe, total / len(trust_rows) * 100, feasible

    tceil = trust_cell(trust_ceiling)
    t50 = trust_cell(50.0)
    rows.append({
        "method": f"TrustLayer({frozen.version})",
        "supplementary_target_pct": round(trust_ceiling, 4),
        "unsafe_at_ceiling": round(tceil[0], 2) if tceil[2] else "",
        "cov_at_ceiling": round(tceil[1], 2),
        "status_at_ceiling": "COMPARABLE" if tceil[2] else "NOT_COMPARABLE_AT_TARGET",
        "unsafe_50": round(t50[0], 2) if t50[2] else "",
        "cov_50": round(t50[1], 2),
        "status_50": "COMPARABLE" if t50[2] else "NOT_COMPARABLE_AT_TARGET",
        "config_version": frozen.version,
        "config_hash": frozen.sha256,
    })
    print("-" * 72)
    print(f"{f'TrustLayer({frozen.version})':>22} | "
          f"{tceil[0]:>9.1f}% | {tceil[1]:>6.1f}% | "
          f"{t50[0]:>8.1f}% | {t50[1]:>6.1f}%")
    print(f"Trust 天花板 {trust_ceiling:.2f}% — 天花板/50 点位: "
          f"{'COMPARABLE' if tceil[2] else 'NOT_EVALUABLE'}/"
          f"{'COMPARABLE' if t50[2] else 'NOT_EVALUABLE'} (不等覆盖不报 Unsafe)")

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=list(rows[0].keys()), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n✓ {OUT_CSV}")


if __name__ == "__main__":
    main()
