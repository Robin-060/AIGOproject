"""
三张主图最终版 + failure raw data 导出

主图 1: figures/coverage_vs_unsafe.png       (run_main_experiment 已生成, v1.4)
主图 2: figures/risk_vs_actual_error.png     (本脚本, 风险分箱 vs 实际错误率)
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

FIG2 = ROOT / "figures" / "risk_vs_actual_error.png"
TABLE = ROOT / "results" / "equal_coverage_table.csv"
FAILURE = ROOT / "results" / "failure_raw.csv"


def main():
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
    ax.set_title("Risk Score vs Actual Error Rate (semifinal_v1.4, "
                 "output-capable units)")
    ax.set_ylim(0, max(rates) * 1.4 + 5)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG2, dpi=150)
    plt.close(fig)
    print(f"✓ 主图 2: {FIG2}")

    # ── 主表 1: Equal-Coverage 全表 ──
    points = ["50", "60", "70", "80", "90"]
    strategies = {}
    with open(ROOT / "results" / "baseline_results.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row["strategy"]
            if name == "Random":
                continue
            strategies.setdefault(name, {})[row["target_coverage_pct"]] = float(
                row["unsafe_output_rate_pct"])
    trust_row = {}
    with open(ROOT / "results" / "equal_coverage_trust.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            trust_row[row["target_coverage_pct"]] = float(row["unsafe_output_rate_pct"])
    # Trust 覆盖率天花板 (60-90% 点位不可达, 留空避免误导)
    trust_ceiling = 54.2
    strategies["TrustLayer(v1.4)"] = {p: (trust_row[p] if p == "50" else None)
                                      for p in points}

    with open(TABLE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["strategy"] + [f"{p}%_unsafe" for p in points] + ["ceiling_pct"])
        for name in strategies:
            ceiling = trust_ceiling if name.startswith("TrustLayer") else ""
            writer.writerow([name] + [
                f"{strategies[name].get(p, ''):.1f}" if strategies[name].get(p) is not None
                else "" for p in points] + [ceiling])
    print(f"✓ 主表 1: {TABLE}")

    # ── failure raw data (Trust 错误单元, 供 C 分类) ──
    op_threshold = trust_row.get("50", 17.3)
    # v1.4 50% 点位有效阈值从 equal_coverage_trust.csv 读取
    with open(ROOT / "results" / "equal_coverage_trust.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["target_coverage_pct"] == "50":
                op_threshold = float(row["risk_threshold"])
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
                "auto_at_50pct": "yes" if (row["verdict"] == "wrong"
                                            and row["auto_capable"] == "True"
                                            and float(row["risk"]) <= op_threshold) else "no",
                "snr_db": q.get("snr_db", ""),
                "gap_ratio": q.get("gap_ratio", ""),
                "clipping_ratio": q.get("clipping_ratio", ""),
                "missing_channels": q.get("missing_channels", ""),
            })
    with open(FAILURE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)
    n_uncaught = sum(1 for r in out_rows if r["auto_at_50pct"] == "yes")
    print(f"✓ failure raw: {FAILURE} ({len(out_rows)} 个错误/无拾取单元, "
          f"其中 50% 点位未拦住 {n_uncaught} 个, 阈值 {op_threshold})")


if __name__ == "__main__":
    main()
