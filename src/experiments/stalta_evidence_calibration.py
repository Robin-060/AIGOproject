"""
STA/LTA 第五证据 — 12 组合 validation 校准 (预注册)

依据: docs/experiments/sta_lta_evidence_design.md
  - 证据: 拾取时间 ±W 秒内无 STA/LTA 触发支持 → 风险 +X
  - 网格: W ∈ {0.5, 1.0, 1.5} × X ∈ {0, 5, 8, 10}
  - 准则(预声明): main 上 50% 覆盖率点 Unsafe 更低者胜; 并列取更小 X
  - 实现等价性: Trust 全链在 main 上只跑一次, 组合间仅风险重排
    (STA/LTA 证据只影响 top-k 排序风险, 不影响路由决策)

输出: results/stalta_evidence_grid.csv
用法: python -m src.experiments.stalta_evidence_calibration
"""

import csv
import json
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
from src.trust_engine.schema import TrustConfig  # noqa: E402

OUT_CSV = ROOT / "results" / "stalta_evidence_grid.csv"
WINDOWS = [0.5, 1.0, 1.5]
PENALTIES = [0, 5, 8, 10]
SELECT_PCT = 50.0


def load_stalta_triggers() -> dict:
    triggers = {}
    with open(ROOT / "data" / "sta_lta_picks.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            onsets = [float(v) for v in (row["p_onset_s"], row["s_onset_s"]) if v]
            triggers[row["sample_id"]] = onsets
    return triggers


def effective_risk(row: dict, triggers: dict, window_s: float, penalty: float) -> float:
    """STA/LTA 支持度: 拾取 ±W 内有触发 → 原风险; 否则 +X."""
    t = row["selected_time_s"]
    if not t:
        return row["risk"]
    onsets = triggers.get(row["sample_id"], [])
    if any(abs(o - float(t)) <= window_s for o in onsets):
        return row["risk"]
    return row["risk"] + penalty


def unsafe_at(rows, risk_fn, target_pct):
    out_rows = [r for r in rows if r["verdict"] in ("correct", "wrong")]
    for r in out_rows:
        r["eff_risk"] = risk_fn(r)
    out_sorted = sorted(out_rows,
                        key=lambda r: (r["eff_risk"], r["sample_id"], r["phase"]))
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

    main_units = [u for u in units if u["split"] == "main" and u["primary_inclusion"]]
    hold_units = [u for u in units if u["split"] == "holdout" and u["primary_inclusion"]]
    print(f"main={len(main_units)} 单元 | holdout={len(hold_units)} | "
          f"选择点 {SELECT_PCT}% | 准则: Unsafe 低者胜, 并列取更小 X")

    print("\nTrust 全链跑 main (一次, 四模型 v1.3)...")
    main_rows = build_unit_rows(records, main_units, quality_map,
                                PROFILE_CANDIDATES["hydrophone_v2"], config, record_map)
    print("Trust 全链跑 holdout (一次)...")
    hold_rows = build_unit_rows(records, hold_units, quality_map,
                                PROFILE_CANDIDATES["hydrophone_v2"], config, record_map)
    triggers = load_stalta_triggers()

    print(f"\n{'W':>4} {'X':>4} | {'main Unsafe@50%':>14} | {'实际Cov':>7}")
    print("-" * 40)
    grid = []
    for w in WINDOWS:
        for x in PENALTIES:
            fn = lambda r, w=w, x=x: effective_risk(r, triggers, w, x)
            unsafe, cov = unsafe_at(main_rows, fn, SELECT_PCT)
            grid.append({"W": w, "X": x, "main_unsafe_pct": round(unsafe, 2),
                         "main_cov_pct": round(cov, 2)})
            print(f"{w:>4} {x:>4} | {unsafe:>12.1f}% | {cov:>6.1f}%")

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(grid[0].keys()))
        writer.writeheader()
        writer.writerows(grid)

    # 胜者: Unsafe 最低; 并列取更小 X
    winner = min(grid, key=lambda g: (g["main_unsafe_pct"], g["X"]))
    print(f"\n==> main 上胜者: W={winner['W']}, X={winner['X']} "
          f"(Unsafe@50% = {winner['main_unsafe_pct']}%)")

    # holdout 确认
    fn = lambda r, w=winner["W"], x=winner["X"]: effective_risk(r, triggers, w, x)
    h_unsafe, h_cov = unsafe_at(hold_rows, fn, SELECT_PCT)
    print(f"holdout 确认: Unsafe@50% = {h_unsafe:.1f}% (实际Cov {h_cov:.1f}%)")

    # 基线对照 (X=0)
    base = [g for g in grid if g["X"] == 0][0]
    print(f"\n基线对照 (X=0, 无证据): {base['main_unsafe_pct']}%")
    print(f"✓ {OUT_CSV} (12 组合全表)")


if __name__ == "__main__":
    main()
