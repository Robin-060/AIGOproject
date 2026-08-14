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
from pathlib import Path
from typing import Any, Mapping, Union
from src.trust_engine.schema import (
    SampleMetadata, QualityReport, ModelProfile, ModelPrediction,
    TrustConfig, ReliabilityResult, AdapterStatus,
    DEMO_CONFIG,
)
from src.trust_engine.reliability import evaluate_reliability


def _load_config() -> TrustConfig:
    """优先读校准后的参数，没有则用 Demo 默认值"""
    from pathlib import Path
    calib_path = Path("src/calibrate/thresholds_calibrated.json")
    if calib_path.exists():
        with open(calib_path, "r", encoding="utf-8") as f:
            calib = json.load(f)
        params = calib.get("parameters", {})
        return TrustConfig(**params, config_version="calibrated_v1.0")
    return DEMO_CONFIG


# ═══════════════════════════════════════
# 数据组 data_layer.py 输出 → Trust Engine 输入
# ═══════════════════════════════════════

def load_from_mapping(raw: Mapping[str, Any]) -> dict:
    """Convert a decoded data-team payload into Trust Engine inputs."""
    required_sections = (
        "sample_metadata",
        "quality_report",
        "model_profiles",
        "model_predictions",
    )
    missing = [section for section in required_sections if section not in raw]
    if missing:
        raise ValueError(f"Missing required section(s): {', '.join(missing)}")

    metadata = SampleMetadata(**raw["sample_metadata"])
    quality = QualityReport(**raw["quality_report"])

    profiles = []
    for profile in raw["model_profiles"].values():
        if isinstance(profile, dict):
            profiles.append(ModelProfile(**profile))

    predictions = [
        ModelPrediction(**prediction)
        for prediction in raw["model_predictions"]
    ]
    adapter_statuses = [
        AdapterStatus(**status)
        for status in raw.get("adapter_statuses", [])
    ]

    if not profiles:
        raise ValueError("model_profiles must contain at least one profile")
    if not predictions:
        raise ValueError("model_predictions must contain at least one prediction")

    return {
        "metadata": metadata,
        "quality": quality,
        "profiles": profiles,
        "predictions": predictions,
        "adapter_statuses": adapter_statuses,
    }


def load_from_data_team(json_path: Union[str, Path]) -> dict:
    """
    读取数据组 data_layer.py 产出的四合一 JSON，
    转换为 Trust Engine 能直接消费的对象。
    """
    with open(json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    return load_from_mapping(raw)


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
    enable_data: bool = True,
    enable_single: bool = True,
    enable_multi: bool = True,
    enable_physics: bool = True,
) -> ReliabilityResult:
    """
    完整分析流程:
    1. P1 数据/适配/单模型证据
    2. P2 单模型物理检查
    3. P3 共识分析与融合候选
    4. P4 汇总 → 路由 → 最终P/S成对检查
    """
    if config is None:
        config = _load_config()

    # ── P1 ──────────────────────────────────────
    suitabilities = None
    data_evidence = None
    single_evidences = None
    try:
        from src.trust_engine.data_evidence import evaluate_data_evidence
        from src.trust_engine.model_suitability import evaluate_model_suitability
        from src.trust_engine.single_model import evaluate_single_model_evidence

        data_evidence = evaluate_data_evidence(quality)
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
        data_evidence=data_evidence,
        suitabilities=suitabilities,
        single_evidences=single_evidences,
        physics_checks=physics_checks,
        consensus_results=consensus_results,
        fusion_candidates=fusion_candidates,
        enable={
            "data": enable_data,
            "single_model": enable_single,
            "multi_model": enable_multi,
            "physics": enable_physics,
        },
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
