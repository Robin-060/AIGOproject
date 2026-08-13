"""
可靠性引擎 — 汇总 P1/P2/P3 证据 → 风险评估

负责人: P4
v2 要求: 证据缺失必须报 INCOMPLETE，不能用占位函数返回 0
"""

from typing import List, Optional, Dict, Any
from dataclasses import replace
from src.trust_engine.schema import (
    SampleMetadata, QualityReport, ModelProfile, ModelPrediction,
    TrustConfig, ReliabilityResult, ModelAssessment,
    ModelSuitability, PhysicsCheck, ConsensusResult, FusedPickCandidate,
    SingleModelEvidence, PhaseDecision, FinalPairStatus, risk_level,
)
from src.trust_engine.policy_router import route_phase


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
) -> ReliabilityResult:
    """
    主入口: 汇总 P1/P2/P3 证据 → 可靠性与决策
    """
    result = ReliabilityResult(
        sample_id=metadata.sample_id,
        config_version=config.config_version,
        data_source=metadata.data_source,
    )
    reasons = []

    # 1. 证据完整性检查
    missing = _check_evidence_completeness(
        suitabilities, physics_checks, consensus_results
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
        suitabilities, physics_checks, consensus_results, config
    )
    result.model_assessments = assessments

    # 3. 逐 phase 决策
    consensus_map = {c.phase: c for c in consensus_results}
    fusion_map = {f.phase: f for f in fusion_candidates}

    for phase in ["P", "S"]:
        phase_preds = [p for p in predictions if p.phase == phase]

        # 找出该 phase 的单模型证据
        phase_single = [s for s in single_evidences if s.phase == phase]

        decision = route_phase(
            phase=phase,
            suitabilities=suitabilities,
            physics_checks=physics_checks,
            consensus=consensus_map.get(phase),
            fusion_candidate=fusion_map.get(phase),
            single_model_evidences=phase_single,
            config=config,
        )
        result.phase_decisions[phase] = decision

    # 4. 整体风险
    all_scores = []
    for d in result.phase_decisions.values():
        all_scores.append(d.risk_score)
    if all_scores:
        result.overall_risk_score = round(sum(all_scores) / len(all_scores), 1)
    result.overall_risk_level = risk_level(result.overall_risk_score)

    # 5. P/S 成对状态
    result.final_pair_status = _pair_status(result.phase_decisions)

    # 6. 收集所有原因码
    for d in result.phase_decisions.values():
        reasons.extend(d.reason_codes)
    result.reason_codes = reasons

    result.evidence_status = "COMPLETE"
    return result


def _check_evidence_completeness(
    suitabilities: Optional[List],
    physics_checks: Optional[List],
    consensus_results: Optional[List],
) -> List[str]:
    """检查证据模块是否齐全"""
    missing = []
    if suitabilities is None:
        missing.append("P1_SUITABILITY")
    if physics_checks is None:
        missing.append("P2_PHYSICS")
    if consensus_results is None:
        missing.append("P3_CONSENSUS")
    return missing


def _build_model_assessments(
    suitabilities: List[ModelSuitability],
    physics_checks: List[PhysicsCheck],
    consensus_results: List[ConsensusResult],
    config: TrustConfig,
) -> List[ModelAssessment]:
    """为每个模型建立评估卡"""
    assessments = []
    physics_map = {}
    for pc in physics_checks:
        if pc.target_type == "MODEL":
            physics_map[pc.target_id] = pc

    consensus_roles = {}
    for cr in consensus_results:
        for m in cr.inlier_models:
            consensus_roles[m] = "INLIER"
        for m in cr.outlier_models:
            consensus_roles[m] = "OUTLIER"

    for s in suitabilities:
        pc = physics_map.get(s.model_name)
        hard_fail = pc.hard_fail if pc else False
        risk = s.penalty
        if hard_fail:
            risk += 30

        assessments.append(ModelAssessment(
            model_name=s.model_name,
            eligible=s.eligible,
            suitability_level=s.suitability_level,
            model_risk_score=risk,
            hard_fail=hard_fail,
            consensus_role=consensus_roles.get(s.model_name, "NOT_COMPARABLE"),
            reasons=s.reasons,
            selection_supported=s.eligible and not hard_fail,
        ))
    return assessments


def _pair_status(decisions: Dict[str, PhaseDecision]) -> str:
    """判断 P/S 成对状态"""
    p_ok = decisions.get("P") and decisions["P"].action not in ("ABSTAIN",)
    s_ok = decisions.get("S") and decisions["S"].action not in ("ABSTAIN",)
    if p_ok and s_ok:
        return FinalPairStatus.COMPLETE.value
    elif p_ok or s_ok:
        return FinalPairStatus.PARTIAL.value
    return FinalPairStatus.FAILED.value
