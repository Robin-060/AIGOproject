"""
DS4 自然故障危害率分析 — 数据证据罚分的自然校准

背景: 现有内部扣分 (8.6/10.7/9.9/27.4) 由注入故障错误率 × 30 分预算校准
      (28.6%/35.8%/32.8%/91.3%), 代码注明 "注入故障 vs 自然故障需声明"。
本分析用真实质量清单 (quality_manifest.csv) + 四模型冻结预测 + 真值,
计算四类自然故障的相位级"最好模型错误率", 与注入值对比。

错误率定义 (相位级, 对齐协议): 单元中没有任何模型给出容差内拾取 (含 no_pick)
→ 该单元"最好模型也失败" → 计 wrong。

输出: results/ds4_natural_hazard.json
用法: python -m src.experiments.ds4_natural_hazard
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
    PHASE_TOL,
    build_phase_units,
    load_records,
)

OUT_JSON = ROOT / "results" / "ds4_natural_hazard.json"
DATA_BUDGET = 30.0

INJECTED = {
    "channel_missing": 0.286,   # → 8.6
    "clipping": 0.358,          # → 10.7
    "gap": 0.328,               # → 9.9
    "strong_noise": 0.913,      # → 27.4
}


def load_quality():
    rows = {}
    with open(ROOT / "data" / "quality_manifest.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows[row["sample_id"]] = row
    return rows


def fault_conditions(quality_row):
    """样本 → 命中的自然故障集合 (含严重/中档)."""
    conds = set()
    missing = quality_row["missing_channels"] or ""
    if missing:
        conds.add("channel_missing")
    gap = float(quality_row["gap_ratio"]) if quality_row["gap_ratio"] else 0.0
    if gap > 0.10:
        conds.add("gap_severe")
    elif gap > 0.02:
        conds.add("gap_moderate")
    clip = float(quality_row["clipping_ratio"]) if quality_row["clipping_ratio"] else 0.0
    if clip > 0.10:
        conds.add("clipping_severe")
    elif clip > 0.02:
        conds.add("clipping_moderate")
    snr = quality_row["snr_db"]
    if snr and float(snr) < 3.0:
        conds.add("strong_noise")
    elif snr and float(snr) < 8.0:
        conds.add("moderate_signal")
    return conds


def main():
    records = load_records()
    quality_map = load_quality()
    units = [u for u in build_phase_units(records) if u["primary_inclusion"]]

    # 每单元: 最好模型是否失败 (无任何模型容差内)
    for u in units:
        tol = PHASE_TOL[u["phase"]]
        any_correct = any(
            pick is not None and abs(pick - u["reference_time_s"]) <= tol
            for pick in u["predictions"].values()
        )
        u["best_model_wrong"] = 0 if any_correct else 1

    conditions = {}
    for u in units:
        conds = fault_conditions(quality_map[u["sample_id"]])
        if not conds:
            conds = {"no_fault"}
        for c in conds:
            conditions.setdefault(c, {"n": 0, "wrong": 0})
            conditions[c]["n"] += 1
            conditions[c]["wrong"] += u["best_model_wrong"]

    print(f"{'条件':>18} {'n':>5} {'最好模型错误率':>14} {'注入错误率':>12} {'注入扣分':>8} {'自然扣分(预算30)':>14}")
    print("-" * 76)
    report = {"natural": {}, "injected": INJECTED, "data_budget": DATA_BUDGET}
    for name, stat in sorted(conditions.items()):
        rate = stat["wrong"] / stat["n"]
        report["natural"][name] = {
            "n": stat["n"], "wrong": stat["wrong"], "rate": round(rate, 3),
            "score": round(DATA_BUDGET * rate, 1),
        }
        inj = INJECTED.get(name, "")
        inj_score = round(DATA_BUDGET * inj, 1) if isinstance(inj, float) else ""
        print(f"{name:>18} {stat['n']:>5} {rate:>13.1%} {inj if isinstance(inj, float) else '—':>11} "
              f"{inj_score if inj_score != '' else '—':>7} {DATA_BUDGET * rate:>13.1f}")

    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\n✓ {OUT_JSON}")


if __name__ == "__main__":
    main()
