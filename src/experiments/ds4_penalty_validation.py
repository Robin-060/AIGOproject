"""
数据证据罚分候选验证 — DS4 自然重校准的 validation 程序

候选 A: CALIBRATED_PENALTIES (注入校准, 当前默认)
候选 B: NATURAL_PENALTIES   (DS4 自然危害率 × 30 预算, results/ds4_natural_hazard.json)

准则 (预注册, 同 STA/LTA 程序): main 上 50% 覆盖率点 Unsafe 更低者胜
程序: main 比较 → 胜者 holdout 确认 → 全表留痕

用法: python -m src.experiments.ds4_penalty_validation
"""

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import warnings  # noqa: E402
warnings.filterwarnings("ignore")

from src.experiments.phase_evaluation import build_phase_units, load_records  # noqa: E402
from src.experiments.run_main_experiment import (  # noqa: E402
    PROFILE_CANDIDATES,
    build_unit_rows,
    load_quality,
    load_split,
)
from src.trust_engine.data_evidence import (  # noqa: E402
    CALIBRATED_PENALTIES,
    NATURAL_PENALTIES,
)
from src.trust_engine.schema import TrustConfig  # noqa: E402

OUT_CSV = ROOT / "results" / "ds4_penalty_grid.csv"
SELECT_PCT = 50.0


def unsafe_at(rows, target_pct):
    out_rows = [r for r in rows if r["verdict"] in ("correct", "wrong")]
    out_sorted = sorted(out_rows,
                        key=lambda r: (r["risk"], r["sample_id"], r["phase"]))
    k = int(round(target_pct / 100 * len(rows)))
    k = min(k, len(out_sorted))
    accepted = {(r["sample_id"], r["phase"]) for r in out_sorted[:k]}
    wrong = total = 0
    for r in rows:
        if (r["sample_id"], r["phase"]) in accepted:
            total += 1
            if r["verdict"] == "wrong":
                wrong += 1
    return wrong / total * 100 if total else float("nan"), total / len(rows) * 100


def main():
    records = load_records()
    quality_map = load_quality()
    split_map = load_split()
    units = build_phase_units(records)
    for u in units:
        u["split"] = split_map.get((u["sample_id"], u["phase"]), "main")
    record_map = {r["sample_id"]: r for r in records}
    config = TrustConfig()
    config.automatic_risk_threshold = 100.0
    profiles = PROFILE_CANDIDATES["hydrophone_v2"]

    main_units = [u for u in units if u["split"] == "main" and u["primary_inclusion"]]
    hold_units = [u for u in units if u["split"] == "holdout" and u["primary_inclusion"]]
    print(f"main={len(main_units)} | holdout={len(hold_units)} | "
          f"选择点 {SELECT_PCT}% | 准则: Unsafe 低者胜")

    results = {}
    for name, penalties in (("A_injected", CALIBRATED_PENALTIES),
                            ("B_natural", NATURAL_PENALTIES)):
        print(f"\n候选 {name} (main)...")
        rows = build_unit_rows(records, main_units, quality_map, profiles, config,
                               record_map, penalties=penalties)
        unsafe, cov = unsafe_at(rows, SELECT_PCT)
        results[name] = {"unsafe": unsafe, "cov": cov, "rows": rows}
        print(f"  {name}: 50%点 Unsafe = {unsafe:.2f}% (实际Cov {cov:.1f}%)")

    winner = "A_injected" if results["A_injected"]["unsafe"] <= results["B_natural"]["unsafe"] else "B_natural"
    w = results[winner]
    print(f"\n==> main 上胜者: {winner} (Unsafe = {w['unsafe']:.2f}%)")

    # holdout 确认 (胜者与败者都报, 看方向一致性)
    for name, penalties in (("A_injected", CALIBRATED_PENALTIES),
                            ("B_natural", NATURAL_PENALTIES)):
        rows = build_unit_rows(records, hold_units, quality_map, profiles, config,
                               record_map, penalties=penalties)
        unsafe, cov = unsafe_at(rows, SELECT_PCT)
        print(f"holdout {name}: Unsafe@50% = {unsafe:.2f}% (实际Cov {cov:.1f}%)")

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate", "main_unsafe_pct_50",
                         "main_cov_pct"])
        for name in results:
            writer.writerow([name, round(results[name]["unsafe"], 2),
                             round(results[name]["cov"], 2)])
    print(f"\n✓ {OUT_CSV}")


if __name__ == "__main__":
    main()
