"""
模型间不安全输出率对比 — 四模型原始精度 + P/S 分相位 + 排序后 50% 点位

口径 (semifinal_v1.4): 相位级, 容差 P 0.5s / S 1.0s, N_eval=1306
输出: results/model_comparison.csv + stdout 摘要
用法: python -m src.experiments.model_comparison
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

from src.experiments.phase_evaluation import (  # noqa: E402
    MODELS,
    PHASE_TOL,
    build_phase_units,
    load_records,
)

OUT_CSV = ROOT / "results" / "model_comparison.csv"


def main():
    records = load_records()
    units = [u for u in build_phase_units(records) if u["primary_inclusion"]]
    conf = {}
    for r in records:
        conf[r["sample_id"]] = {
            m: (r["predictions"].get(m) or {}).get("confidence") or 0.0
            for m in MODELS
        }

    rows = []
    print(f"{'模型':>20} {'P拾取':>5} {'P容差内':>7} {'S拾取':>5} {'S容差内':>7} "
          f"{'原始错误率':>9} {'排序50% Unsafe':>12}")
    print("-" * 78)
    for model in MODELS:
        p_total = p_hit = s_total = s_hit = 0
        ranked = []
        for u in units:
            pick = u["predictions"].get(model)
            tol = PHASE_TOL[u["phase"]]
            if u["phase"] == "P":
                if pick is not None:
                    p_total += 1
                    if abs(pick - u["reference_time_s"]) <= tol:
                        p_hit += 1
                        ranked.append((1.0 - conf[u["sample_id"]][model],
                                       (u["sample_id"], u["phase"]), "correct"))
                    else:
                        ranked.append((1.0 - conf[u["sample_id"]][model],
                                       (u["sample_id"], u["phase"]), "wrong"))
                else:
                    ranked.append((1.0, (u["sample_id"], u["phase"]), "no_pick"))
            else:
                if pick is not None:
                    s_total += 1
                    if abs(pick - u["reference_time_s"]) <= tol:
                        s_hit += 1
                        ranked.append((1.0 - conf[u["sample_id"]][model],
                                       (u["sample_id"], u["phase"]), "correct"))
                    else:
                        ranked.append((1.0 - conf[u["sample_id"]][model],
                                       (u["sample_id"], u["phase"]), "wrong"))
                else:
                    ranked.append((1.0, (u["sample_id"], u["phase"]), "no_pick"))
        raw_wrong = (p_total - p_hit) + (s_total - s_hit)
        raw_total = p_total + s_total
        raw_rate = raw_wrong / raw_total * 100 if raw_total else float("nan")

        # 排序后 50% 点位: 按 1-conf 升序取前 50% 单元
        ranked.sort(key=lambda x: (x[0], x[1]))
        k = int(round(50 / 100 * len(units)))
        accepted = set(item[1] for item in ranked[:k])
        # no_pick 单元不计入 auto (按协议), 只统计 accepted 且有拾取的
        auto = total_wrong = 0
        for risk, key, verdict in ranked:
            if key in accepted and verdict != "no_pick":
                auto += 1
                if verdict == "wrong":
                    total_wrong += 1
        ranked50 = total_wrong / auto * 100 if auto else float("nan")

        rows.append({
            "model": model,
            "p_picks": p_total, "p_hit_pct": round(p_hit / p_total * 100, 1) if p_total else "",
            "s_picks": s_total, "s_hit_pct": round(s_hit / s_total * 100, 1) if s_total else "",
            "raw_error_pct": round(raw_rate, 1),
            "ranked50_unsafe_pct": round(ranked50, 1),
        })
        print(f"{model:>20} {p_total:>5} {p_hit / p_total * 100 if p_total else 0:>6.1f}% "
              f"{s_total:>5} {s_hit / s_total * 100 if s_total else 0:>6.1f}% "
              f"{raw_rate:>8.1f}% {ranked50:>11.1f}%")

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n✓ {OUT_CSV}")


if __name__ == "__main__":
    main()
