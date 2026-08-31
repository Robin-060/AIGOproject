"""
全方法对比表 (v2 规则) — 相位级 Equal-Coverage

Trust Layer 用冻结档案 (hydrophone_v2); 基线不受档案影响 (直接用冻结预测)。
比较点位 (v1.5.1): Trust 覆盖率天花板点 (动态取 main_results.csv, 当前 45.6%)
与 50% (标准点)。不可达点位按 NOT_EVALUABLE 纪律留空 Unsafe。
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
    records = load_records()
    units = with_confidence(build_phase_units(records), records)

    # Trust 天花板先行计算: 决定本表比较点位 (v1.5.1: 不再硬编码历史点 46.7)
    import csv as _csv
    trust_rows = list(_csv.DictReader(
        open(ROOT / "results" / "main_results.csv", encoding="utf-8")))
    output_rows = [r for r in trust_rows if r["verdict"] in ("correct", "wrong")]
    trust_ceiling = len(output_rows) / len(trust_rows) * 100
    ceiling_point = round(trust_ceiling, 1)
    points = [ceiling_point, 50.0]
    col_c = str(ceiling_point)

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
    print(f"{'方法':>22} | {f'{ceiling_point}% Unsafe':>12} | {'实际Cov':>7} | "
          f"{'50% Unsafe':>9} | {'实际Cov':>7}")
    print("-" * 72)
    for name, (out_fn, risk_fn) in strategies.items():
        cells = {point: unsafe_at(units, out_fn, risk_fn, point)
                 for point in points}
        c, f = cells[ceiling_point], cells[50.0]
        rows.append({
            "method": name,
            f"unsafe_{col_c}": (round(c[0], 2) if c[2] else ""),
            f"cov_{col_c}": round(c[1], 2),
            f"status_{col_c}": "COMPARABLE" if c[2] else "NOT_COMPARABLE_AT_TARGET",
            "unsafe_50": (round(f[0], 2) if f[2] else ""),
            "cov_50": round(f[1], 2),
            "status_50": "COMPARABLE" if f[2] else "NOT_COMPARABLE_AT_TARGET",
        })
        print(f"{name:>22} | {c[0]:>12.1f}% | {c[1]:>7.1f}% | "
              f"{f[0]:>9.1f}% | {f[1]:>7.1f}%")

    # Random (多种子)
    rand_cells = {}
    for point in points:
        p = random_find_p(units, point)
        stat = random_across_seeds(units, p)
        rand_cells[point] = (stat["unsafe_output_rate"] * 100,
                             stat["coverage"] * 100)
    rc, rf = rand_cells[ceiling_point], rand_cells[50.0]
    rows.append({
        "method": "Random",
        f"unsafe_{col_c}": round(rc[0], 2),
        f"cov_{col_c}": round(rc[1], 2),
        f"status_{col_c}": "COMPARABLE",
        "unsafe_50": round(rf[0], 2),
        "cov_50": round(rf[1], 2),
        "status_50": "COMPARABLE",
    })
    print(f"{'Random':>22} | {rc[0]:>12.1f}% | {rc[1]:>7.1f}% | "
          f"{rf[0]:>9.1f}% | {rf[1]:>7.1f}%")

    # Trust v1.5 (从 main_results.csv 直接算, 与基线同口径 + NOT_EVALUABLE 纪律)
    output_sorted = sorted(output_rows,
                           key=lambda r: (float(r["risk"]), r["sample_id"], r["phase"]))

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

    tc, t50 = trust_cell(ceiling_point), trust_cell(50.0)
    rows.append({
        "method": "TrustLayer(v1.5)",
        f"unsafe_{col_c}": round(tc[0], 2) if tc[2] else "",
        f"cov_{col_c}": round(tc[1], 2),
        f"status_{col_c}": "COMPARABLE" if tc[2] else "NOT_COMPARABLE_AT_TARGET",
        "unsafe_50": round(t50[0], 2) if t50[2] else "",
        "cov_50": round(t50[1], 2),
        "status_50": "COMPARABLE" if t50[2] else "NOT_COMPARABLE_AT_TARGET",
        "ceiling_pct": round(trust_ceiling, 2),
    })
    # 行字段统一: 为基线行补 ceiling 空值
    for row in rows:
        row.setdefault("ceiling_pct", "")
    print("-" * 72)
    print(f"{'TrustLayer(v1.5)':>22} | {tc[0]:>12.1f}% | {tc[1]:>7.1f}% | "
          f"{t50[0]:>9.1f}% | {t50[1]:>7.1f}%")
    print(f"Trust 天花板 {trust_ceiling:.2f}% — 天花板点 {ceiling_point}%: "
          f"{'COMPARABLE' if tc[2] else 'NOT_EVALUABLE'}; 50%: "
          f"{'COMPARABLE' if t50[2] else 'NOT_EVALUABLE'} (不等覆盖不报 Unsafe)")

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n✓ {OUT_CSV}")


if __name__ == "__main__":
    main()
