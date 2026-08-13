"""
可靠性引擎 — 汇总 P1/P2/P3 证据 → 风险评估

负责人: P4
支持消融实验: enable 开关可单独关闭 data / single_model / multi_model / physics
"""

from typing import List, Optional, Dict
from src.trust_engine.schema import (
    SampleMetadata, QualityReport, ModelProfile, ModelPrediction,
    TrustConfig, ReliabilityResult, ModelAssessment,
    ModelSuitability, PhysicsCheck, ConsensusResult, FusedPickCandidate,
    SingleModelEvidence, PhaseDecision, FinalPairStatus,
)
from src.trust_engine.policy_router import route_phase

# 消融实验开关默认值: 全开
ALL_ENABLED = {
    "data": True,
    "single_model": True,
    "multi_model": True,
    "physics": True,
}


def evaluate_reliability(
    metadata: SampleMetadata,
    quality: QualityReport,
    model_profiles: List[ModelProfile],
    predictions: List[ModelPrediction],
    config: TrustConfig,
    # P1 产出
    suitabilities: Optional[List[ModelSuitability]] = None,
    single_evidences: Optional[List[SingleModelEvidence]] = None,
    # P2 产出
    physics_checks: Optional[List[PhysicsCheck]] = None,
    # P3 产出
    consensus_results: Optional[List[ConsensusResult]] = None,
    fusion_candidates: Optional[List[FusedPickCandidate]] = None,
    # 消融开关
    enable: Optional[Dict[str, bool]] = None,
) -> ReliabilityResult:
    """
    主入口: 汇总 P1/P2/P3 证据 → 可靠性与决策

    Args:
        enable: 消融实验开关，如 {"multi_model": False} 关闭多模型证据。
                关闭的证据不参与风险评分，也不参与模型筛选。
    """
    if enable is None:
        enable = dict(ALL_ENABLED)

    result = ReliabilityResult(
        sample_id=metadata.sample_id,
        config_version=config.config_version,
        data_source=metadata.data_source,
    )
    reasons = []

    # 1. 证据完整性检查 (关闭的证据不检查)
    missing = _check_evidence_completeness(
        suitabilities, single_evidences, physics_checks,
        consensus_results, enable,
    )
    if missing:
        result.evidence_status = "INCOMPLETE"
        result.reason_codes = [f"MISSING_{m}" for m in missing]
        return result

    suitabilities = suitabilities or []
    physics_checks = physics_checks or []
    consensus_results = consensus_results or []
    fusion_candidates = fusion_candidates or []
    single_evidences = single_evidences or []

    # 2. 模型评估 (每个模型一张评估卡)
    assessments = _build_model_assessments(
        suitabilities, physics_checks, consensus_results, config, enable
    )
    result.model_assessments = assessments

    # 3. 逐 phase 决策
    consensus_map = {c.phase: c for c in consensus_results}
    fusion_map = {f.phase: f for f in fusion_candidates}

    for phase in ["P", "S"]:
        phase_single = [s for s in single_evidences if s.phase == phase]

        # 计算该 phase 的风险分数 (四证据加权, 关闭的不计)
        phase_risk = _compute_phase_risk(
            suitabilities, phase_single,
            consensus_map.get(phase), physics_checks, enable,
        )

        decision = route_phase(
            phase=phase,
            suitabilities=suitabilities,
            physics_checks=physics_checks,
            consensus=consensus_map.get(phase) if enable["multi_model"] else None,
            fusion_candidate=fusion_map.get(phase) if enable["multi_model"] else None,
            single_model_evidences=phase_single,
            config=config,
            enable=enable,
            phase_risk=phase_risk,
        )
        result.phase_decisions[phase] = decision

    # 4. 整体风险
    all_scores = [d.risk_score for d in result.phase_decisions.values()]
    if all_scores:
        result.overall_risk_score = round(sum(all_scores) / len(all_scores), 1)
    result.overall_risk_level = _risk_level_from_config(
        result.overall_risk_score, config
    )

    # 5. P/S 成对状态
    result.final_pair_status = _pair_status(result.phase_decisions)

    # 6. 收集所有原因码
    for d in result.phase_decisions.values():
        reasons.extend(d.reason_codes)
    result.reason_codes = reasons

    result.evidence_status = "COMPLETE"
    return result


def _compute_phase_risk(
    suitabilities: List[ModelSuitability],
    phase_single: List[SingleModelEvidence],
    consensus: Optional[ConsensusResult],
    physics_checks: List[PhysicsCheck],
    enable: Dict[str, bool],
) -> float:
    """四类证据加权求和 (0-100)，关闭的证据记 0"""
    risk = 0.0

    # 数据证据 (0-30): 模型适配惩罚
    if enable["data"]:
        risk += min(sum(s.penalty for s in suitabilities), 30)

    # 单模型证据 (0-15): 低置信度惩罚
    if enable["single_model"]:
        risk += min(sum(sv.score or 0 for sv in phase_single), 15)

    # 多模型证据 (0-40): 分歧分数
    if enable["multi_model"] and consensus:
        risk += min(consensus.score or 0, 40)

    # 物理证据 (0-15): hard fail 分数
    if enable["physics"]:
        risk += min(sum(pc.score for pc in physics_checks if pc.hard_fail), 15)

    return min(risk, 100)


def _check_evidence_completeness(
    suitabilities: Optional[List],
    single_evidences: Optional[List],
    physics_checks: Optional[List],
    consensus_results: Optional[List],
    enable: Dict[str, bool],
) -> List[str]:
    """检查证据模块是否齐全 (关闭的证据不检查)"""
    missing = []
    if enable["data"] and suitabilities is None:
        missing.append("P1_SUITABILITY")
    if enable["single_model"] and single_evidences is None:
        missing.append("P1_SINGLE_MODEL")
    if enable["physics"] and physics_checks is None:
        missing.append("P2_PHYSICS")
    if enable["multi_model"] and consensus_results is None:
        missing.append("P3_CONSENSUS")
    return missing


def _build_model_assessments(
    suitabilities: List[ModelSuitability],
    physics_checks: List[PhysicsCheck],
    consensus_results: List[ConsensusResult],
    config: TrustConfig,
    enable: Dict[str, bool],
) -> List[ModelAssessment]:
    """为每个模型建立评估卡"""
    assessments = []
    physics_map = {}
    if enable["physics"]:
        for pc in physics_checks:
            if pc.target_type == "MODEL":
                physics_map[pc.target_id] = pc

    consensus_roles = {}
    if enable["multi_model"]:
        for cr in consensus_results:
            for m in cr.inlier_models:
                consensus_roles[m] = "INLIER"
            for m in cr.outlier_models:
                consensus_roles[m] = "OUTLIER"

    for s in suitabilities:
        pc = physics_map.get(s.model_name)
        hard_fail = pc.hard_fail if pc else False
        risk = s.penalty if enable["data"] else 0.0
        if hard_fail:
            risk += 30

        assessments.append(ModelAssessment(
            model_name=s.model_name,
            eligible=s.eligible if enable["data"] else True,
            suitability_level=s.suitability_level,
            model_risk_score=risk,
            hard_fail=hard_fail,
            consensus_role=consensus_roles.get(s.model_name, "NOT_COMPARABLE"),
            reasons=s.reasons,
            selection_supported=(s.eligible if enable["data"] else True) and not hard_fail,
        ))
    return assessments


def _risk_level_from_config(score: float, config: TrustConfig) -> str:
    if score <= config.risk_low_max:
        return "LOW"
    if score <= config.risk_medium_max:
        return "MEDIUM"
    return "HIGH"


def _pair_status(decisions: Dict[str, PhaseDecision]) -> str:
    """判断 P/S 成对状态"""
    p_ok = decisions.get("P") and decisions["P"].action not in ("ABSTAIN",)
    s_ok = decisions.get("S") and decisions["S"].action not in ("ABSTAIN",)
    if p_ok and s_ok:
        return FinalPairStatus.COMPLETE.value
    elif p_ok or s_ok:
        return FinalPairStatus.PARTIAL.value
    return FinalPairStatus.FAILED.value
