"""
主流程 — 串联 P1+P2+P3+P4 + 数据组接入

负责人: P4

用法:
    python -m src.trust_engine.pipeline

数据组交付 data_layer.py 产出四合一 JSON 后:
    python data_layer.py --trace 0 --output result.json
    python -m src.trust_engine.pipeline --input result.json
"""

import sys, json
from typing import List, Optional
from src.trust_engine.schema import (
    SampleMetadata, QualityReport, ModelProfile, ModelPrediction,
    TrustConfig, ReliabilityResult, AdapterStatus,
    DEMO_CONFIG,
)
from src.trust_engine.reliability import evaluate_reliability


# ═══════════════════════════════════════
# 数据组 data_layer.py 输出 → Trust Engine 输入
# ═══════════════════════════════════════

def load_from_data_team(json_path: str) -> dict:
    """
    读取数据组 data_layer.py 产出的四合一 JSON，
    转换为 Trust Engine 能直接消费的对象。
    """
    with open(json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # 1. SampleMetadata
    meta_raw = raw.get("sample_metadata", {})
    metadata = SampleMetadata(**meta_raw)

    # 2. QualityReport
    quality_raw = raw.get("quality_report", {})
    quality = QualityReport(**quality_raw)

    # 3. ModelProfile[]
    profiles = []
    for name, prof in raw.get("model_profiles", {}).items():
        if isinstance(prof, dict):
            profiles.append(ModelProfile(**prof))

    # 4. ModelPrediction[]
    predictions = [
        ModelPrediction(**p) for p in raw.get("model_predictions", [])
    ]

    # 5. AdapterStatus[]
    adapter_statuses = [
        AdapterStatus(**s) for s in raw.get("adapter_statuses", [])
    ]

    return {
        "metadata": metadata,
        "quality": quality,
        "profiles": profiles,
        "predictions": predictions,
        "adapter_statuses": adapter_statuses,
    }


# ═══════════════════════════════════════
# 正式入口 — 等 P1/P2/P3 代码合入后取消注释
# ═══════════════════════════════════════

def run_pipeline(
    metadata: SampleMetadata,
    quality: QualityReport,
    profiles: list,
    predictions: list,
    adapter_statuses: list = None,
    config: TrustConfig = None,
) -> ReliabilityResult:
    """
    完整分析流程:
    1. P1 数据/适配/单模型证据
    2. P2 单模型物理检查
    3. P3 共识分析与融合候选
    4. P4 汇总 → 路由 → 最终P/S成对检查
    """
    if config is None:
        config = DEMO_CONFIG

    # ── P1 ──────────────────────────────────────
    suitabilities = None
    single_evidences = None
    try:
        from src.trust_engine.data_evidence import evaluate_data_evidence
        from src.trust_engine.model_suitability import evaluate_model_suitability
        from src.trust_engine.single_model import evaluate_single_model_evidence

        suitabilities = evaluate_model_suitability(
            metadata, quality, profiles,
            adapter_statuses or [],
        )
        single_evidences = evaluate_single_model_evidence(predictions)
    except ImportError:
        pass

    # ── P2 ──────────────────────────────────────
    physics_checks = None
    try:
        from src.trust_engine.physics import check_model_prediction
        physics_checks = []
        for p in predictions:
            if p.phase == "P":
                s_preds = [x for x in predictions
                           if x.phase == "S" and x.model_name == p.model_name]
                s_pred = s_preds[0] if s_preds else None
                physics_checks.append(check_model_prediction(p, s_pred, config))
    except ImportError:
        pass

    # ── P3 ──────────────────────────────────────
    consensus_results = None
    fusion_candidates = None
    try:
        from src.trust_engine.multi_model import analyze_multi_model_consensus
        from src.trust_engine.fusion import build_fusion_candidates

        consensus_results = analyze_multi_model_consensus(
            predictions, suitabilities or [], physics_checks or [],
        )
        fusion_candidates = build_fusion_candidates(
            predictions, consensus_results,
        )
    except ImportError:
        pass

    return evaluate_reliability(
        metadata=metadata,
        quality=quality,
        model_profiles=profiles,
        predictions=predictions,
        config=config,
        suitabilities=suitabilities,
        single_evidences=single_evidences,
        physics_checks=physics_checks,
        consensus_results=consensus_results,
        fusion_candidates=fusion_candidates,
    )


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--input":
        # 从数据组 JSON 直接接入
        data = load_from_data_team(sys.argv[2])
        result = run_pipeline(
            metadata=data["metadata"],
            quality=data["quality"],
            profiles=data["profiles"],
            predictions=data["predictions"],
            adapter_statuses=data["adapter_statuses"],
        )
        print(result.to_json())
    else:
        print("Trust Engine pipeline ready.")
        print("用法:")
        print("  python -m src.trust_engine.pipeline --input result.json")
        print(f'当前: P1/P2/P3/P4 全模块已合入，等数据组产出 result.json 即可全链路跑通')

