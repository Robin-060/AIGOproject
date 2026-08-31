"""
三张主图最终版 + failure raw data 导出

主图 1: figures/coverage_vs_unsafe.png       (run_main_experiment 已生成, v1.5)
主图 2: figures/risk_vs_actual_error.png     (本脚本, 风险分箱 vs 实际错误率)
主图 3: figures/phase_unsafe_comparison.png  (本脚本, P/S 相位级 Unsafe 对比, 天花板补充口径)
主表 1: results/equal_coverage_table.csv     (本脚本, 全部策略 × 5 覆盖率点)
附加:   results/failure_raw.csv              (Trust 错误单元明细, 供 C 分类)

用法: python -m src.experiments.final_figures
"""

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import warnings  # noqa: E402
warnings.filterwarnings("ignore")

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from src.trust_engine.config_loader import load_frozen_config  # noqa: E402

FIG2 = ROOT / "figures" / "risk_vs_actual_error.png"
FIG3 = ROOT / "figures" / "phase_unsafe_comparison.png"
TABLE = ROOT / "results" / "equal_coverage_table.csv"
FAILURE = ROOT / "results" / "failure_raw.csv"


def main():
    frozen = load_frozen_config()
    # ── 主图 2: 风险分箱 vs 实际错误率 ──
    bins = []
    with open(ROOT / "results" / "risk_bins.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            bins.append(row)
    labels = [row["risk_bin"] for row in bins]
    rates = [float(row["error_rate_pct"]) if row["error_rate_pct"] else 0.0
             for row in bins]
    counts = [int(row["n"]) for row in bins]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(labels, rates, color="#4CAF50", width=0.55)
    for bar, rate, n in zip(bars, rates, counts):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.8,
                f"{rate:.1f}%\n(n={n})", ha="center", fontsize=10)
    ax.set_xlabel("Risk Score Bin")
    ax.set_ylabel("Actual Error Rate (%)")
    ax.set_title(f"Risk Score vs Actual Error Rate ({frozen.version}, "
                 "output-capable units)")
    ax.set_ylim(0, max(rates) * 1.4 + 5)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG2, dpi=150)
    plt.close(fig)
    print(f"✓ 主图 2: {FIG2}")

    # ── 主表 1: Equal-Coverage 全表 (NOT_EVALUABLE 纪律) ──
    points = [str(point) for point in frozen.coverage_points]
    strategies = {}
    with open(ROOT / "results" / "baseline_results.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row["strategy"]
            if name == "Random":
                continue
            feasible = row.get("feasible", "true").lower() == "true"
            strategies.setdefault(name, {})[row["target_coverage_pct"]] = (
                float(row["unsafe_output_rate_pct"]) if feasible else None
            )
    trust_row = {}
    trust_ceiling = 0.0
    trust_50_feasible = False
    trust_threshold = None
    with open(ROOT / "results" / "equal_coverage_trust.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            feasible = row.get("feasible", "false").lower() == "true"
            trust_row[row["target_coverage_pct"]] = (
                float(row["unsafe_output_rate_pct"]) if feasible else None
            )
            trust_ceiling = max(trust_ceiling, float(row["coverage_pct"]))
            if row["target_coverage_pct"] == "50":
                trust_50_feasible = feasible
                if feasible:
                    trust_threshold = float(row["risk_threshold"])
    strategies[f"TrustLayer({frozen.version})"] = trust_row

    with open(TABLE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["strategy"] + [f"{p}%_unsafe" for p in points] + [
            "ceiling_pct", "config_version", "config_hash"
        ])
        for name in strategies:
            ceiling = round(trust_ceiling, 2) if name.startswith("TrustLayer") else ""
            writer.writerow([name] + [
                f"{strategies[name].get(p, ''):.1f}" if strategies[name].get(p) is not None
                else "" for p in points] + [ceiling, frozen.version, frozen.sha256])
    print(f"✓ 主表 1: {TABLE}")

    # ── 主图 3: P/S 相位级 Unsafe 对比 (天花板补充口径) ──
    import json
    with open(ROOT / "results" / "bootstrap_ci.json", encoding="utf-8") as f:
        boot = json.load(f)
    groups = [("ALL", "ALL"), ("P", "P phase"), ("S", "S phase")]
    trust_vals, voting_vals, deltas, ci_los, ci_his = [], [], [], [], []
    for key, _label in groups:
        s = boot[f"{key}_ceiling_supplementary"]
        trust_vals.append(s["trust_unsafe_pp"])
        voting_vals.append(s["voting_unsafe_pp"])
        deltas.append(s["point_delta_pp"])
        ci_los.append(s["ci95_lo"])
        ci_his.append(s["ci95_hi"])

    x = np.arange(len(groups))
    w = 0.35
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.bar(x - w / 2, trust_vals, w, label="Trust Layer", color="#4CAF50")
    ax.bar(x + w / 2, voting_vals, w, label="Voting", color="#2196F3")
    for i in range(len(groups)):
        ax.text(i, max(trust_vals[i], voting_vals[i]) + 0.35,
                f"Δ={deltas[i]:+.1f}pp\nCI[{ci_los[i]:.1f}, {ci_his[i]:.1f}]",
                ha="center", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels([label for _key, label in groups])
    ax.set_ylabel("Unsafe Output Rate (%)")
    ax.set_title(f"Phase-level Unsafe at Phase-specific Trust Ceilings "
                 f"({frozen.version}, supplementary)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.text(0.5, 0.01,
             "Declared point 50%: NOT_EVALUABLE. Each phase uses its own Trust "
             "ceiling; P/S targets differ and are not directly comparable.",
             ha="center", fontsize=9, color="#555555")
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(FIG3, dpi=150)
    plt.close(fig)
    print(f"✓ 主图 3: {FIG3}")

    # ── failure raw data (Trust 错误单元, 供 C 分类) ──
    op_threshold = trust_threshold if trust_50_feasible else None
    quality = {}
    with open(ROOT / "data" / "quality_manifest.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            quality[row["sample_id"]] = row

    out_rows = []
    with open(ROOT / "results" / "main_results.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["verdict"] not in ("wrong", "no_pick"):
                continue
            q = quality.get(row["sample_id"], {})
            out_rows.append({
                "sample_id": row["sample_id"],
                "phase": row["phase"],
                "station": row["station"],
                "split": row["split"],
                "truth_s": row["reference_time_s"],
                "selected_time_s": row["selected_time_s"],
                "action": row["action"],
                "risk": row["risk"],
                "verdict": row["verdict"],
                "auto_at_50pct": (
                    "NOT_EVALUABLE" if not trust_50_feasible
                    else "yes" if (
                        row["verdict"] == "wrong"
                        and row["auto_capable"] == "True"
                        and float(row["risk"]) <= op_threshold
                    ) else "no"
                ),
                "snr_db": q.get("snr_db", ""),
                "gap_ratio": q.get("gap_ratio", ""),
                "clipping_ratio": q.get("clipping_ratio", ""),
                "missing_channels": q.get("missing_channels", ""),
                "config_version": frozen.version,
                "config_hash": frozen.sha256,
            })
    with open(FAILURE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=list(out_rows[0].keys()), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(out_rows)
    n_uncaught = sum(1 for r in out_rows if r["auto_at_50pct"] == "yes")
    if trust_50_feasible:
        suffix = f"50% 点位未拦住 {n_uncaught} 个, 阈值 {op_threshold}"
    else:
        suffix = f"50% 点位 NOT_EVALUABLE, Trust 天花板 {trust_ceiling:.2f}%"
    print(f"✓ failure raw: {FAILURE} ({len(out_rows)} 个错误/无拾取单元, {suffix})")


if __name__ == "__main__":
    main()
