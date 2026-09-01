"""
可靠性引擎 — 汇总 P1/P2/P3 证据 → 风险评估（三版合并版）

合并来源:
  - phase2-calibration: enable 字典开关 + single_model 接入决策
  - phase2-baseline:    ablation 实验需求 (开关禁用时中性化证据)
  - phase3:             data_evidence 参数 + 证据分解 evidence_breakdown

约定:
  - enable 用字典: {"data", "single_model", "multi_model", "physics"}
  - ConsensusResult.score 语义 = 一致比例 (0-1), 1.0 = 完全一致
  - 风险分解记录在 result.evidence_breakdown (每 phase + overall)
"""

from typing import List, Optional, Dict
from src.trust_engine.schema import (
    SampleMetadata, QualityReport, ModelProfile, ModelPrediction,
    TrustConfig, ReliabilityResult, ModelAssessment,
    ModelSuitability, PhysicsCheck, ConsensusResult, FusedPickCandidate,
    SingleModelEvidence, PhaseDecision, FinalPairStatus, EvidenceScore,
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
    # P1 数据证据 (P1 的 data_evidence.py 产出)
    data_evidence: Optional[EvidenceScore] = None,
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
        data_evidence: P1 数据质量证据 (EvidenceScore, 满分30)
        enable: 消融实验开关，如 {"multi_model": False} 关闭多模型证据。
                关闭的证据不参与风险评分，也不参与模型筛选。
    """
    if enable is None:
        enable = dict(ALL_ENABLED)

    result = ReliabilityResult(
        sample_id=metadata.sample_id,
        config_version=config.config_version,
        config_hash=config.config_hash,
        parent_config=config.parent_config,
        data_source=metadata.data_source,
    )
    reasons = []

    # 1. 证据完整性检查 (关闭的证据不检查)
    missing = _check_evidence_completeness(
        data_evidence, suitabilities, single_evidences,
        physics_checks, consensus_results, enable,
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

    # ── 消融: 禁用证据中性化 ───────────────────────────
    if not enable["data"]:
        from dataclasses import replace
        suitabilities = [
            replace(s, eligible=True, penalty=0.0) for s in suitabilities
        ]
        data_evidence = EvidenceScore(score=0.0, reasons=["ABLATION_DATA_DISABLED"])

    if not enable["single_model"]:
        single_evidences = []

    if not enable["physics"]:
        physics_checks = []

    if not enable["multi_model"]:
        from dataclasses import replace
        consensus_results = [
            replace(c, status="INSUFFICIENT", inlier_models=[],
                    outlier_models=[], score=1.0,
                    reasons=list(c.reasons) + ["ABLATION_MULTI_DISABLED"])
            for c in consensus_results
        ]
        fusion_candidates = []

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

        breakdown = _compute_phase_risk(
            data_evidence=data_evidence,
            single_evidences=phase_single,
            consensus=consensus_map.get(phase) if enable["multi_model"] else None,
            physics_checks=physics_checks,
            enable=enable,
            config=config,
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
            phase_risk=breakdown["total"],
            predictions=predictions,
        )
        result.phase_decisions[phase] = decision
        result.evidence_breakdown[phase] = breakdown

    # 4. 整体风险
    all_scores = [d.risk_score for d in result.phase_decisions.values()]
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


def _compute_phase_risk(
    data_evidence: Optional[EvidenceScore],
    single_evidences: List[SingleModelEvidence],
    consensus: Optional[ConsensusResult],
    physics_checks: List[PhysicsCheck],
    enable: Dict[str, bool],
    config: TrustConfig = None,
) -> Dict[str, float]:
    """四类证据风险分解 (0-100)，关闭的证据记 0。权重上限取自 config。"""
    if config is None:
        config = TrustConfig()

    # 数据证据 (上限 config.data_weight)
    if enable["data"] and data_evidence is not None:
        data_risk = min(float(data_evidence.score or 0.0), config.data_weight)
    else:
        data_risk = 0.0

    # 单模型证据 (上限 config.single_model_weight)
    if enable["single_model"]:
        single_risk = min(
            sum(float(sv.score or 0.0) for sv in single_evidences),
            config.single_model_weight,
        )
    else:
        single_risk = 0.0

    # 多模型证据 (上限 config.multi_model_weight)
    mw = config.multi_model_weight
    if enable["multi_model"] and consensus is not None:
        if consensus.status == "DISAGREEMENT":
            if ("SEVERE_DISAGREEMENT" in consensus.reasons
                    or "COMPARISON_GROUP_MISMATCH" in consensus.reasons):
                multi_risk = mw          # SEVERE → 满档
            else:
                multi_risk = mw * 0.5    # MINOR → 半档
        elif consensus.status == "INSUFFICIENT":
            multi_risk = mw * 0.5
        elif consensus.status == "CONSENSUS":
            if consensus.score >= 1.0:
                multi_risk = 0.0         # 完全一致 → 无分歧罚分 (无负分)
            else:
                # 有离群模型时保留离群罚 (与离群占比成正比)
                multi_risk = min(max((1.0 - consensus.score) * mw, 0.0), mw)
        else:
            multi_risk = 0.0
    else:
        multi_risk = 0.0

    # 物理证据 (上限 config.physics_weight)
    if enable["physics"]:
        physics_risk = min(
            sum(float(check.score or 0.0)
                for check in physics_checks
                if check.status == "FAIL"),
            config.physics_weight,
        )
    else:
        physics_risk = 0.0

    total = min(data_risk + single_risk + multi_risk + physics_risk, 100.0)

    return {
        "data": round(data_risk, 1),
        "single_model": round(single_risk, 1),
        "multi_model": round(multi_risk, 1),
        "physics": round(physics_risk, 1),
        "total": round(total, 1),
    }


def _check_evidence_completeness(
    data_evidence: Optional[EvidenceScore],
    suitabilities: Optional[List],
    single_evidences: Optional[List],
    physics_checks: Optional[List],
    consensus_results: Optional[List],
    enable: Dict[str, bool],
) -> List[str]:
    """检查证据模块是否齐全 (关闭的证据不检查)"""
    missing = []
    if enable["data"] and data_evidence is None:
        missing.append("P1_DATA")
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
