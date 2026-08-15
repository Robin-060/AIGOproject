"""
放宽口径下的参数识别 — 风险分界 + 证据权重

背景: 系统保守全拒, 参数测不出差异。
方法: 放宽评估口径 —— 只要 P 或 S 任一相位有输出 (PARTIAL) 就算"放行",
      不再要求完整 P/S 对。在这个口径下重新网格搜索。

注意: 这是实验性口径, 用于参数识别, 不代表最终产品行为。

用法:
    python -m src.calibrate.identify_parameters
"""

import csv
import itertools
import json
from collections import defaultdict
from pathlib import Path

from src.trust_engine.schema import (
    SampleMetadata, QualityReport, ModelPrediction, ModelProfile,
    AdapterStatus, TrustConfig,
)
from src.trust_engine.reliability import evaluate_reliability
from src.trust_engine.data_evidence import evaluate_data_evidence
from src.trust_engine.model_suitability import evaluate_model_suitability
from src.trust_engine.single_model import evaluate_single_model_evidence
from src.trust_engine.physics import check_model_prediction
from src.trust_engine.multi_model import analyze_multi_model_consensus
from src.trust_engine.fusion import build_fusion_candidates

PRED_PATH = Path("data/phase3/noise_predictions_seisbench.json")
TRUTH_PATH = Path("data/phase3/noise_records_seisbench.csv")
OUT_PATH = Path("docs/experiments/param_identification.json")

PROFILES = [
    ModelProfile(model_name="PhaseNet", required_channels=["Z", "N", "E"],
                 accepted_sampling_rates_hz=[100.0], resampling_supported=True,
                 required_preprocessing_version="seisbench_v0.12"),
    ModelProfile(model_name="PickBlue", required_channels=["Z", "N", "E", "H"],
                 accepted_sampling_rates_hz=[100.0], resampling_supported=True,
                 required_preprocessing_version="seisbench_v0.12"),
    ModelProfile(model_name="OBSTransformer", required_channels=["H"],
                 preferred_channels=["Z", "N", "E"],
                 accepted_sampling_rates_hz=[100.0], resampling_supported=True,
                 required_preprocessing_version="seisbench_v0.12"),
]
ADAPTERS = [
    AdapterStatus(model_name=m, loaded=True, run_succeeded=True, output_comparable=True)
    for m in ("PhaseNet", "PickBlue", "OBSTransformer")
]


def load_data():
    truth_map = {}
    with open(TRUTH_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (row["sample_id"], row["noise_level"])
            if key in truth_map:
                continue
            truth_map[key] = {
                "P": float(row["truth_p_s"]) if row["truth_p_s"] else None,
                "S": float(row["truth_s_s"]) if row["truth_s_s"] else None,
            }
    pred_map = defaultdict(list)
    with open(PRED_PATH, encoding="utf-8") as f:
        for p in json.load(f):
            pred_map[(p["sample_id"], p["noise_level"])].append(
                ModelPrediction(**{k: v for k, v in p.items() if k != "noise_level"})
            )
    samples = []
    for key, gt in truth_map.items():
        if key not in pred_map or gt["P"] is None or gt["S"] is None:
            continue
        noise = key[1]
        meta = SampleMetadata(
            sample_id=key[0], data_source="REAL",
            preprocessing_version="seisbench_v0.12",
        )
        quality = QualityReport(
            available_channels=["Z", "N", "E", "H"], missing_channels=[],
            snr_db={"L0": 20.0, "L1": 10.0, "L2": 5.0, "L3": 2.0}[noise],
            source="REAL_CALCULATION",
        )
        samples.append((meta, quality, pred_map[key], gt))
    return samples


def run_trust(meta, quality, preds, config, enable=None):
    data_ev = evaluate_data_evidence(quality)
    suits = evaluate_model_suitability(meta, quality, PROFILES, ADAPTERS)
    singles = evaluate_single_model_evidence(preds)
    physics = []
    seen = set()
    for p in preds:
        if p.model_name in seen:
            continue
        seen.add(p.model_name)
        p_ps = [x for x in preds if x.model_name == p.model_name and x.phase == "P"]
        s_ps = [x for x in preds if x.model_name == p.model_name and x.phase == "S"]
        physics.append(check_model_prediction(
            p_ps[0] if p_ps else None, s_ps[0] if s_ps else None,
            config, target_id=p.model_name,
        ))
    cons = analyze_multi_model_consensus(preds, suits, physics)
    fusions = build_fusion_candidates(preds, cons)
    return evaluate_reliability(
        meta, quality, PROFILES, preds,
        config, data_ev, suits, singles, physics, cons, fusions,
        enable=enable,
    )


def relaxed_verdict(gt, result):
    """
    放宽口径:
    - 正确: 任一相位 (P 或 S) 输出且在容差内
    - 错误: 任一相位输出且超出容差
    - 拒绝: 两相位都 ABSTAIN
    """
    p_d = result.phase_decisions.get("P")
    s_d = result.phase_decisions.get("S")

    verdicts = []
    for d, phase in [(p_d, "P"), (s_d, "S")]:
        if not d or d.action == "ABSTAIN" or d.selected_time_s is None:
            continue
        tol = 0.5 if phase == "P" else 1.0
        verdicts.append(
            "correct" if abs(d.selected_time_s - gt[phase]) <= tol else "wrong"
        )
    if not verdicts:
        return "reject"
    return "wrong" if "wrong" in verdicts else "correct"


def main():
    samples = load_data()
    print(f"有效样本: {len(samples)} (放宽口径: 单相位也计)\n")

    # ── 1. 风险分界识别 ──
    print("[1] 风险分界网格扫描 (放宽口径)")
    results = []
    for low in [20, 30, 40, 50, 60]:
        for medium in [60, 70, 80, 90, 100]:
            config = TrustConfig(
                risk_low_max=low, risk_medium_max=medium,
                automatic_risk_threshold=medium,  # 自动阈值跟 medium 同步放宽
            )
            stats = {"correct": 0, "wrong": 0, "reject": 0}
            for meta, quality, preds, gt in samples:
                r = run_trust(meta, quality, preds, config)
                stats[relaxed_verdict(gt, r)] += 1
            total = sum(stats.values())
            wrong_rate = stats["wrong"] / total if total else 0
            coverage = (stats["correct"] + stats["wrong"]) / total if total else 0
            results.append((wrong_rate, -coverage, low, medium, stats))

    # 错误放行率优先最低, 其次覆盖率最高
    results.sort(key=lambda x: (x[0], x[1]))
    best = results[0]
    print(f"  最优: low={best[2]}, medium={best[3]}")
    print(f"  错误放行率={best[0]:.1%}, 覆盖率={-best[1]:.1%}")
    print(f"  (正确={best[4]['correct']} 错误={best[4]['wrong']} 拒绝={best[4]['reject']})")

    # 打印前5名, 看是否可识别
    print("  top5 组合:")
    for wr, cov, low, medium, stats in results[:5]:
        print(f"    low={low} medium={medium}: wrong={wr:.1%} coverage={-cov:.1%}")

    best_config = TrustConfig(
        risk_low_max=best[2], risk_medium_max=best[3],
        automatic_risk_threshold=best[3],
    )

    # ── 2. 证据权重识别 (用最优风险分界) ──
    print("\n[2] 证据消融 (用最优风险分界, 放宽口径)")
    enable_names = ["data", "single_model", "multi_model", "physics"]
    ablation = {}
    for name in enable_names:
        enable = {"data": True, "single_model": True, "multi_model": True, "physics": True}
        enable[name] = False
        stats = {"correct": 0, "wrong": 0, "reject": 0}
        for meta, quality, preds, gt in samples:
            r = run_trust(meta, quality, preds, best_config, enable)
            stats[relaxed_verdict(gt, r)] += 1
        total = sum(stats.values())
        wr = stats["wrong"] / total if total else 0
        ablation[name] = {"wrong_rate": wr,
                          "correct": stats["correct"],
                          "wrong": stats["wrong"],
                          "reject": stats["reject"]}
        print(f"  关 {name:12s}: 错误放行率={wr:.1%} "
              f"(正确={stats['correct']} 错误={stats['wrong']} 拒绝={stats['reject']})")

    # 完整系统基准
    stats = {"correct": 0, "wrong": 0, "reject": 0}
    for meta, quality, preds, gt in samples:
        r = run_trust(meta, quality, preds, best_config)
        stats[relaxed_verdict(gt, r)] += 1
    total = sum(stats.values())
    ablation["full"] = {"wrong_rate": stats["wrong"] / total if total else 0,
                        "correct": stats["correct"], "wrong": stats["wrong"],
                        "reject": stats["reject"]}
    print(f"  完整系统    : 错误放行率={ablation['full']['wrong_rate']:.1%} "
          f"(正确={stats['correct']} 错误={stats['wrong']} 拒绝={stats['reject']})")

    # 保存
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "note": "放宽口径(单相位也计), 仅用于参数识别, 不代表产品行为",
        "best_risk_thresholds": {"risk_low_max": best[2], "risk_medium_max": best[3]},
        "best_wrong_rate": best[0],
        "best_coverage": -best[1],
        "ablation": ablation,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n✅ 结果 → {OUT_PATH}")


if __name__ == "__main__":
    main()
