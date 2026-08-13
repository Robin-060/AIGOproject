"""
可靠性引擎 — 汇总 P1/P2/P3 证据 → 风险评估

负责人: P4
v2 要求: 证据缺失必须报 INCOMPLETE，不能用占位函数返回 0
"""

from typing import List, Optional, Dict, Any
from src.trust_engine.schema import (
    SampleMetadata, QualityReport, ModelProfile, ModelPrediction,
    TrustConfig, ReliabilityResult, ModelAssessment,
    ModelSuitability, PhysicsCheck, ConsensusResult, FusedPickCandidate,
    SingleModelEvidence, PhaseDecision, FinalPairStatus, EvidenceScore,
)
from src.trust_engine.policy_router import route_phase


def evaluate_reliability(
    metadata: SampleMetadata,
    quality: QualityReport,
    model_profiles: List[ModelProfile],
    predictions: List[ModelPrediction],
    config: TrustConfig,
    data_evidence: Optional[EvidenceScore] = None,
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
        data_evidence, suitabilities, single_evidences,
        physics_checks, consensus_results
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
        # 找出该 phase 的单模型证据
        phase_single = [s for s in single_evidences if s.phase == phase]

        breakdown = _compute_phase_risk(
            data_evidence=data_evidence,
            single_evidences=phase_single,
            consensus=consensus_map.get(phase),
            physics_checks=physics_checks,
        )

        decision = route_phase(
            phase=phase,
            suitabilities=suitabilities,
            physics_checks=physics_checks,
            consensus=consensus_map.get(phase),
            fusion_candidate=fusion_map.get(phase),
            single_model_evidences=phase_single,
            config=config,
            phase_risk=breakdown["total"],
        )
        result.phase_decisions[phase] = decision
        result.evidence_breakdown[phase] = breakdown

    # 4. 整体风险
    all_scores = []
    for d in result.phase_decisions.values():
        all_scores.append(d.risk_score)
    if all_scores:
        result.overall_risk_score = round(sum(all_scores) / len(all_scores), 1)
    result.overall_risk_level = _risk_level_from_config(
        result.overall_risk_score, config
    )

    categories = ("data", "single_model", "multi_model", "physics")
    result.evidence_breakdown["overall"] = {
        category: round(
            sum(result.evidence_breakdown[p][category] for p in ("P", "S")) / 2,
            1,
        )
        for category in categories
    }

    # 5. P/S 成对状态
    result.final_pair_status = _pair_status(result.phase_decisions)

    # 6. 收集所有原因码
    for d in result.phase_decisions.values():
        reasons.extend(d.reason_codes)
    result.reason_codes = reasons

    result.evidence_status = "COMPLETE"
    return result


def _check_evidence_completeness(
    data_evidence: Optional[EvidenceScore],
    suitabilities: Optional[List],
    single_evidences: Optional[List],
    physics_checks: Optional[List],
    consensus_results: Optional[List],
) -> List[str]:
    """检查证据模块是否齐全"""
    missing = []
    if data_evidence is None:
        missing.append("P1_DATA")
    if suitabilities is None:
        missing.append("P1_SUITABILITY")
    if single_evidences is None:
        missing.append("P1_SINGLE_MODEL")
    if physics_checks is None:
        missing.append("P2_PHYSICS")
    if consensus_results is None:
        missing.append("P3_CONSENSUS")
    return missing


def _compute_phase_risk(
    data_evidence: EvidenceScore,
    single_evidences: List[SingleModelEvidence],
    consensus: Optional[ConsensusResult],
    physics_checks: List[PhysicsCheck],
) -> Dict[str, float]:
    """Return an auditable four-evidence risk decomposition (0-100)."""
    data_risk = min(float(data_evidence.score or 0.0), 30.0)
    single_risk = min(
        sum(float(item.score or 0.0) for item in single_evidences),
        15.0,
    )

    multi_risk = 20.0
    if consensus is not None:
        if consensus.status == "DISAGREEMENT":
            multi_risk = 40.0
        elif consensus.status == "INSUFFICIENT":
            multi_risk = 20.0
        else:
            # consensus.score is the fraction of usable models in the inlier set.
            multi_risk = min(max((1.0 - consensus.score) * 40.0, 0.0), 40.0)

    physics_risk = min(
        sum(float(check.score or 0.0) for check in physics_checks),
        15.0,
    )
    total = min(data_risk + single_risk + multi_risk + physics_risk, 100.0)

    return {
        "data": round(data_risk, 1),
        "single_model": round(single_risk, 1),
        "multi_model": round(multi_risk, 1),
        "physics": round(physics_risk, 1),
        "total": round(total, 1),
    }


def _risk_level_from_config(score: float, config: TrustConfig) -> str:
    if score <= config.risk_low_max:
        return "LOW"
    if score <= config.risk_medium_max:
        return "MEDIUM"
    return "HIGH"


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
