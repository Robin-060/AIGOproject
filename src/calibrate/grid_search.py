"""
网格搜索 — 阈值校准脚本

读取仿真数据标签 → 生成模拟模型预测 → 遍历候选参数
→ 记录错误拦截率 + 自动覆盖率 → 输出最优参数

用法:
    python -m src.calibrate.grid_search
"""

import csv
import itertools
import json
import numpy as np
from pathlib import Path
from typing import List, Dict

from src.trust_engine.schema import (
    QualityReport, ModelPrediction, ReliabilityResult,
    ModelSuitability, PhysicsCheck, ConsensusResult, FusedPickCandidate,
    SingleModelEvidence, TrustConfig, SampleMetadata, ModelProfile,
)
from src.trust_engine.reliability import evaluate_reliability

LABELS_PATH = Path("data/synthetic/labels.csv")
OUTPUT_PATH = Path("src/calibrate/thresholds_calibrated.json")

# 候选参数
CANDIDATES = {
    "consensus_tolerance_p_s": [0.1, 0.2, 0.3, 0.5, 1.0],
    "consensus_tolerance_s_s": [0.2, 0.3, 0.5, 1.0, 1.5],
    "risk_low_max": [20, 25, 30, 35, 40],
    "risk_medium_max": [50, 55, 60, 65, 70],
}

# 模型 Profile (模拟)
DEMO_PROFILES = [
    ModelProfile(model_name="PhaseNet", required_channels=["Z","N","E"],
                 accepted_sampling_rates_hz=[100.0], resampling_supported=True,
                 required_preprocessing_version="obs_raw_v1", profile_source="REAL_ADAPTER",
                 validation_domain_known=True),
    ModelProfile(model_name="PickBlue", required_channels=["Z","N","E","H"],
                 accepted_sampling_rates_hz=[100.0], resampling_supported=True,
                 required_preprocessing_version="obs_raw_v1", profile_source="REAL_ADAPTER",
                 validation_domain_known=True),
    ModelProfile(model_name="OBSTransformer", required_channels=["H"],
                 preferred_channels=["Z","N","E"],
                 accepted_sampling_rates_hz=[100.0], resampling_supported=True,
                 required_preprocessing_version="obs_raw_v1", profile_source="REAL_ADAPTER",
                 validation_domain_known=True),
]


def load_labels() -> List[Dict]:
    """读取仿真数据标签"""
    rows = []
    with open(LABELS_PATH, "r") as f:
        reader = csv.DictReader(f)
        for r in reader:
            r["P_time_s"] = float(r["P_time_s"]) if r["P_time_s"] else -1
            r["S_time_s"] = float(r["S_time_s"]) if r["S_time_s"] else -1
            rows.append(r)
    return rows


def simulate_predictions(truth: Dict, disagreement: bool = False) -> List[ModelPrediction]:
    """
    根据真值标签生成模拟模型预测

    Args:
        truth: 标签行 {"sample_id", "P_time_s", "S_time_s", "label", "noise_level", "channels"}
        disagreement: True=生成不一致的预测(模拟模型打架)

    Returns:
        List[ModelPrediction]
    """
    sid = truth["sample_id"]
    is_earthquake = truth["label"] == "EARTHQUAKE"
    has_h = "H" in truth.get("channels", "")

    preds = []

    if is_earthquake and truth["P_time_s"] > 0:
        # PhaseNet: 接近真值, 但加入小量噪声
        p_pn = truth["P_time_s"] + np.random.normal(0, 0.05)
        s_pn = truth["S_time_s"] + np.random.normal(0, 0.08)
        # PickBlue: 也接近真值
        p_pb = truth["P_time_s"] + np.random.normal(0, 0.06)
        s_pb = truth["S_time_s"] + np.random.normal(0, 0.10)
        # OBSTransformer: 如果 disagreement, 偏离很远
        if disagreement:
            p_ob = truth["P_time_s"] + np.random.normal(5, 1)
            s_ob = truth["S_time_s"] + np.random.normal(4, 1)
        else:
            p_ob = truth["P_time_s"] + np.random.normal(0, 0.07)
            s_ob = truth["S_time_s"] + np.random.normal(0, 0.12)

        models_ok = ["PhaseNet", "PickBlue", "OBSTransformer"]
        scores_ok = [0.88, 0.85, 0.90]

        # 如果缺 H, PickBlue 不兼容 → 不给预测
        if not has_h:
            models_ok = ["PhaseNet", "OBSTransformer"]
            scores_ok = [0.88, 0.90]

        for model, score, p_t, s_t in zip(
            models_ok,
            scores_ok,
            [p_pn, p_pb, p_ob][:len(models_ok)],
            [s_pn, s_pb, s_ob][:len(models_ok)],
        ):
            preds.append(ModelPrediction(
                sample_id=sid, model_name=model, phase="P",
                time_s=round(p_t, 2), score=round(score + np.random.uniform(-0.05, 0.05), 3),
                adapter_status="OK", prediction_source="REAL_MODEL",
            ))
            preds.append(ModelPrediction(
                sample_id=sid, model_name=model, phase="S",
                time_s=round(s_t, 2), score=round(score + np.random.uniform(-0.05, 0.05), 3),
                adapter_status="OK", prediction_source="REAL_MODEL",
            ))

    return preds


def run_one_config(
    config: TrustConfig,
    labels: List[Dict],
    noise_levels: List[str] = None,
    enable_data: bool = True,
    enable_single: bool = True,
    enable_multi: bool = True,
    enable_physics: bool = True,
) -> Dict[str, float]:
    """
    用一组配置跑全部仿真数据，统计指标
    """
    total = 0
    errors_total = 0
    errors_caught = 0
    auto_count = 0

    for i, truth in enumerate(labels):
        if noise_levels and truth.get("noise_level") not in noise_levels:
            continue

        total += 1
        is_earthquake = truth["label"] == "EARTHQUAKE"

        # 60% 样本正常, 20% 缺通道, 20% 模型打架
        r = i % 5
        disagreement = (r >= 3) and is_earthquake
        preds = simulate_predictions(truth, disagreement=disagreement)

        # 构造 QualityReport
        has_h = "H" in truth.get("channels", "")
        missing = [] if has_h else ["H"]
        quality = QualityReport(
            available_channels=["Z","N","E","H"] if has_h else ["Z","N","E"],
            missing_channels=missing,
            snr_db={"L0": 20.0, "L1": 10.0, "L2": 5.0, "L3": 2.0}.get(
                truth.get("noise_level", "L0"), 20.0),
        )

        # 构造简单的 P1/P2/P3 证据
        suits = [
            ModelSuitability(m, eligible=(m != "PickBlue" or has_h),
                             suitability_level="COMPATIBLE")
            for m in ["PhaseNet", "PickBlue", "OBSTransformer"]
        ]
        physics = [PhysicsCheck(target_type="MODEL", target_id=m, status="PASS")
                   for m in ["PhaseNet", "PickBlue", "OBSTransformer"]]

        metadata = SampleMetadata(sample_id=truth["sample_id"])

        # 跑 Trust Engine
        # 模拟 P3 证据 (简化版: 看模型间是否一致)
        p_preds = [p for p in preds if p.phase == "P" and p.time_s > 0]
        s_preds = [p for p in preds if p.phase == "S" and p.time_s > 0]

        consensus = []
        for phase, pred_list in [("P", p_preds), ("S", s_preds)]:
            if len(pred_list) >= 2:
                times = [p.time_s for p in pred_list]
                spread = max(times) - min(times)
                tol = config.consensus_tolerance_p_s if phase == "P" else config.consensus_tolerance_s_s
                if spread <= tol:
                    consensus.append(ConsensusResult(
                        phase=phase, status="CONSENSUS",
                        eligible_models=[p.model_name for p in pred_list],
                        inlier_models=[p.model_name for p in pred_list],
                        center_time_s=sum(times)/len(times), spread_s=spread, score=0,
                    ))
                else:
                    consensus.append(ConsensusResult(
                        phase=phase, status="DISAGREEMENT",
                        eligible_models=[p.model_name for p in pred_list],
                        inlier_models=[], outlier_models=[], score=20,
                    ))
            elif len(pred_list) == 1:
                consensus.append(ConsensusResult(
                    phase=phase, status="INSUFFICIENT",
                    eligible_models=[pred_list[0].model_name],
                    inlier_models=[pred_list[0].model_name],
                    center_time_s=pred_list[0].time_s, spread_s=0, score=5,
                ))

        # 模拟单模型证据
        single_ev = []
        for p in preds:
            single_ev.append(SingleModelEvidence(
                model_name=p.model_name, phase=p.phase,
                score=0 if (p.score or 0) >= 0.3 else 5,
                reasons=["CONFIDENCE_AVAILABLE"] if (p.score or 0) >= 0.3 else ["LOW_CONFIDENCE"],
                status="AVAILABLE",
            ))

       result = evaluate_reliability(
    metadata=metadata,
    quality=quality,
    model_profiles=DEMO_PROFILES,
    predictions=preds,
    config=config,
    suitabilities=suits,
    physics_checks=physics,
    consensus_results=consensus,
    single_evidences=single_ev,
    enable_data=enable_data,
    enable_single=enable_single,
    enable_multi=enable_multi,
    enable_physics=enable_physics,
)
        action = result.phase_decisions.get("P")
        if action:
            is_auto = action.action != "ABSTAIN"
            if is_auto:
                auto_count += 1

            # 判断是否正确
            is_auto = action.action in ("ACCEPT", "FUSE", "ROUTE")
            if is_auto:
                auto_count += 1

            if not is_earthquake and preds:
                errors_total += 1
                if not is_auto:
                    errors_caught += 1
            elif disagreement and is_earthquake:
                p_times = [p.time_s for p in preds if p.phase == "P" and p.time_s > 0]
                if p_times:
                    max_diff = max(p_times) - min(p_times)
                    if max_diff > 0.5:
                        errors_total += 1
                        if not is_auto:
                            errors_caught += 1
            elif is_earthquake and not disagreement:
                # 正常地震 + 正常预测 → 没问题
                pass

    error_rate = errors_caught / errors_total if errors_total > 0 else 0
    coverage = auto_count / total if total > 0 else 0
    return {
        "error_detection_rate": round(error_rate, 3),
        "auto_coverage": round(coverage, 3),
        "total_samples": total,
        "error_count": errors_total,
    }


def main():
    labels = load_labels()
    print(f"加载 {len(labels)} 条标签")

    keys = list(CANDIDATES.keys())
    values = list(CANDIDATES.values())
    total_combos = 1
    for v in values:
        total_combos *= len(v)
    print(f"候选参数组合: {total_combos}")

    best = None
    best_score = -1

    count = 0
    for combo in itertools.product(*values):
        params = dict(zip(keys, combo))
        config = TrustConfig(
            consensus_tolerance_p_s=params["consensus_tolerance_p_s"],
            consensus_tolerance_s_s=params["consensus_tolerance_s_s"],
            risk_low_max=params["risk_low_max"],
            risk_medium_max=params["risk_medium_max"],
            config_version="calibrated_v1.0",
        )

        result = run_one_config(config, labels)
        count += 1

        # 综合评分: 拦截率为主, 覆盖率次之
        score = result["error_detection_rate"] * 0.7 + result["auto_coverage"] * 0.3
        if score > best_score:
            best_score = score
            best = {"params": params, "result": result}

        if count % 50 == 0:
            print(f"  已试 {count}/{total_combos} 组... 当前最优: {best_score:.3f}")

    print(f"\n✅ 最优参数:")
    for k, v in best["params"].items():
        print(f"  {k}: {v}")
    print(f"  拦截率: {best['result']['error_detection_rate']:.1%}")
    print(f"  覆盖率: {best['result']['auto_coverage']:.1%}")

    # 输出 JSON
    output = {
        "version": "calibrated_v1.0",
        "source": "grid_search_on_synthetic",
        "parameters": best["params"],
        "performance": {k: float(v) for k, v in best["result"].items()},
    }
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n✅ 已写入 {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
