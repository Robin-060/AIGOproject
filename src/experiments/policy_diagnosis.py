"""
policy_diagnosis.py — v1.5.1 路由决策分解诊断 (EXP17 第一阶段, 只诊断不改逻辑)

对全部 1306 个相位单元跑冻结引擎 (ranking_mode, 与主实验同口径),
按路由停止步骤对未自动输出的单元做 reason decomposition:

  - NO_ELIGIBLE_MODELS / NO_SURVIVING_MODELS
  - NO_DECISIVE_EVIDENCE_BETWEEN_MODELS (分歧)
  - CONSENSUS_WITHOUT_ADMISSIBLE_FUSION (第 4.5 步 fail-closed)
  - INSUFFICIENT_EVIDENCE_FOR_SELECTION (第 5 步)
  - FUSE/ONLY_SURVIVOR 风险超阈 (ranking_mode 下基本不触发)
  - NO_PREDICTIONS (该相位无任何模型拾取)
每类附: 存在 ≥1 个容差内正确拾取的单元数; 全部拾取都正确的单元数; P/S 分开。
另对 4.5 步单元给 fusion floor 敏感度: 有多少单元有 ≥2 个模型的校准置信度
分别 ≥ 0.70/0.65/0.60/0.55 (回答 floor sweep 的一阶价值)。

输出:
  results/policy_diagnosis.json
  results/policy_diagnosis.csv (逐单元分解, 供 C/B)

用法: python -m src.experiments.policy_diagnosis
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
from src.experiments.run_main_experiment import (  # noqa: E402
    load_quality,
    load_split,
    trust_per_record,
)
from src.trust_engine.confidence_calibration import calibrated_prob  # noqa: E402
from src.trust_engine.config_loader import load_frozen_config  # noqa: E402

OUT_JSON = ROOT / "results" / "policy_diagnosis.json"
OUT_CSV = ROOT / "results" / "policy_diagnosis.csv"

CATEGORIES = [
    "NO_ELIGIBLE_MODELS",
    "NO_SURVIVING_MODELS",
    "NO_DECISIVE_EVIDENCE_BETWEEN_MODELS",
    "CONSENSUS_WITHOUT_ADMISSIBLE_FUSION",
    "INSUFFICIENT_EVIDENCE_FOR_SELECTION",
    "RISK_ABOVE_AUTO_THRESHOLD",
    "NO_PREDICTIONS",
]


def classify(reason_codes):
    if not reason_codes:
        return "NO_PREDICTIONS"
    if "NO_ELIGIBLE_MODELS" in reason_codes:
        return "NO_ELIGIBLE_MODELS"
    if "NO_SURVIVING_MODELS" in reason_codes:
        return "NO_SURVIVING_MODELS"
    if "NO_DECISIVE_EVIDENCE_BETWEEN_MODELS" in reason_codes:
        return "NO_DECISIVE_EVIDENCE_BETWEEN_MODELS"
    if "CONSENSUS_WITHOUT_ADMISSIBLE_FUSION" in reason_codes:
        return "CONSENSUS_WITHOUT_ADMISSIBLE_FUSION"
    if "INSUFFICIENT_EVIDENCE_FOR_SELECTION" in reason_codes:
        return "INSUFFICIENT_EVIDENCE_FOR_SELECTION"
    if any("RISK_ABOVE" in c for c in reason_codes):
        return "RISK_ABOVE_AUTO_THRESHOLD"
    return "OTHER_AUTO"


def main():
    frozen = load_frozen_config()
    config = frozen.trust_config(ranking_mode=True)
    profiles = frozen.model_profiles()
    records = load_records()
    quality_map = load_quality()
    split_map = load_split()
    units = [u for u in build_phase_units(records) if u["primary_inclusion"]]
    for u in units:
        u["split"] = split_map.get((u["sample_id"], u["phase"]), "main")

    per_record = {}
    record_map = {}
    for i, record in enumerate(records):
        record_map[record["sample_id"]] = record
        per_record[record["sample_id"]] = trust_per_record(
            record, quality_map[record["sample_id"]], config, profiles)
        if (i + 1) % 300 == 0:
            print(f"  Trust 链进度 {i + 1}/{len(records)}", flush=True)

    stats = {c: {"n": 0, "P": 0, "S": 0, "with_correct_pick": 0,
                 "all_picks_correct": 0} for c in CATEGORIES}
    floor_hist = {0.70: 0, 0.65: 0, 0.60: 0, 0.55: 0}
    rows = []
    n_auto = 0

    for u in units:
        sid, phase = u["sample_id"], u["phase"]
        record = record_map[sid]
        result = per_record[sid]
        decision = (result.phase_decisions.get(phase) if result else None)
        action = decision.action if decision else "ABSTAIN"
        reasons = list(decision.reason_codes) if decision else []
        tol = PHASE_TOL[phase]
        picks = [(m, t) for m, t in u["predictions"].items() if t is not None]
        n_picks = len(picks)
        correct_picks = [abs(t - u["reference_time_s"]) <= tol for _, t in picks]
        has_correct = any(correct_picks)
        all_correct = bool(picks) and all(correct_picks)

        cal_confs = []
        for m, _t in picks:
            raw = (record["predictions"][m] or {}).get("confidence")
            cal_confs.append(calibrated_prob(m, raw))
        cal_confs = [c for c in cal_confs if c is not None]

        if action in ("ACCEPT", "ROUTE", "FUSE"):
            n_auto += 1
            category = "AUTO_" + action
        else:
            category = classify(reasons)
        if category not in stats:
            stats[category] = {"n": 0, "P": 0, "S": 0,
                               "with_correct_pick": 0, "all_picks_correct": 0}
        stats[category]["n"] += 1
        stats[category][phase] += 1
        if has_correct:
            stats[category]["with_correct_pick"] += 1
        if all_correct:
            stats[category]["all_picks_correct"] += 1

        if category == "CONSENSUS_WITHOUT_ADMISSIBLE_FUSION":
            above = sum(1 for c in cal_confs if c >= 0.55)
            for th in (0.70, 0.65, 0.60, 0.55):
                if sum(1 for c in cal_confs if c >= th) >= 2:
                    floor_hist[th] += 1

        rows.append({
            "sample_id": sid, "phase": phase, "split": u["split"],
            "action": action, "category": category,
            "n_picks": n_picks, "has_correct_pick": has_correct,
            "all_picks_correct": all_correct,
            "min_cal_conf": round(min(cal_confs), 3) if cal_confs else "",
            "max_cal_conf": round(max(cal_confs), 3) if cal_confs else "",
            "reason_codes": "|".join(reasons),
        })

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n自动输出 {n_auto} | 未自动输出 {len(units) - n_auto} "
          f"| 总 {len(units)}")
    print(f"{'类别':>38} {'n':>5} {'P':>5} {'S':>5} {'有正确pick':>9} "
          f"{'全对':>5}")
    for c in CATEGORIES + sorted(
            [k for k in stats if k.startswith("AUTO_")]):
        s = stats[c]
        print(f"{c:>38} {s['n']:>5} {s['P']:>5} {s['S']:>5} "
              f"{s['with_correct_pick']:>9} {s['all_picks_correct']:>5}")

    print(f"\n4.5 步单元 floor 敏感度 (≥2 模型校准置信度过门槛的单元数):")
    for th in (0.70, 0.65, 0.60, 0.55):
        print(f"  floor {th:.2f}: {floor_hist[th]}")

    report = {
        "config_version": frozen.version, "config_hash": frozen.sha256,
        "n_units": len(units), "n_auto": n_auto,
        "categories": stats,
        "consensus_without_fusion_floor_hist": floor_hist,
    }
    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\n✓ {OUT_JSON}")
    print(f"✓ {OUT_CSV}")


if __name__ == "__main__":
    main()
