"""
主流程 — 串联 P1+P2+P3+P4

负责人: P4

用法:
    python -m src.trust_engine.pipeline

当前状态: P1/P2/P3 待实现，Demo Fixture 已清除，等组员交付后接入
"""

from src.trust_engine.schema import (
    SampleMetadata, QualityReport, ModelProfile, ModelPrediction,
    TrustConfig, ReliabilityResult,
    ModelSuitability, PhysicsCheck, ConsensusResult, FusedPickCandidate,
    SingleModelEvidence, DEMO_MODEL_PROFILES, DEMO_CONFIG,
)
from src.trust_engine.reliability import evaluate_reliability


def analyze_sample(
    metadata: SampleMetadata,
    quality: QualityReport,
    model_profiles: list,
    predictions: list,
    config: TrustConfig,
    suitabilities: list = None,
    single_evidences: list = None,
    physics_checks: list = None,
    consensus_results: list = None,
    fusion_candidates: list = None,
) -> ReliabilityResult:
    """
    完整分析流程:
    1. Schema 校验 (P4)
    2. P1 数据/适配/单模型证据
    3. P2 单模型物理检查
    4. P3 共识分析与融合候选
    5. P4 汇总 → 路由 → 最终P/S成对检查
    """
    return evaluate_reliability(
        metadata=metadata,
        quality=quality,
        model_profiles=model_profiles,
        predictions=predictions,
        config=config,
        suitabilities=suitabilities,
        single_evidences=single_evidences,
        physics_checks=physics_checks,
        consensus_results=consensus_results,
        fusion_candidates=fusion_candidates,
    )


# ═══════════════════════════════════════
# P1/P2/P3 接入点（待组员交付后填写）
# ═══════════════════════════════════════

def run_pipeline(sample_id: str, quality: QualityReport,
                 predictions: list) -> ReliabilityResult:
    """
    正式入口 — 等 P1/P2/P3 交付后取消注释
    """
    metadata = SampleMetadata(sample_id=sample_id)
    # ── 模拟配置，等数据组交付真实参数后替换 ──────
    config = DEMO_CONFIG
    profiles = list(DEMO_MODEL_PROFILES.values())

    # ── P1 ──────────────────────────────────────
    # suitabilities = p1.check_model_suitability(quality, profiles, predictions)
    # single_evidences = p1.evaluate_single_models(predictions)
    suitabilities = None
    single_evidences = None

    # ── P2 ──────────────────────────────────────
    # physics_checks = p2.check_all_models(predictions, config)
    physics_checks = None

    # ── P3 ──────────────────────────────────────
    # consensus_results = p3.evaluate_consensus(predictions, suitabilities, physics_checks)
    # fusion_candidates = p3.generate_fusion_candidates(consensus_results)
    consensus_results = None
    fusion_candidates = None

    return analyze_sample(
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
    print("Trust Engine pipeline ready.")
    print("P1/P2/P3 待实现。届时取消 run_pipeline() 中的注释即可接入。")
    print()
    print("当前可用: schema.py / reliability.py / policy_router.py / pipeline.py")
