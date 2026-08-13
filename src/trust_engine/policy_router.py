"""
Policy Router — 6 步决策：选模型 / 融合 / 拒绝

负责人: P4
输入: P1/P2/P3 证据 + TrustConfig
输出: PhaseDecision (每个 phase 独立)
"""

from typing import List, Optional, Dict
from src.trust_engine.schema import (
    ModelSuitability, PhysicsCheck, ConsensusResult,
    FusedPickCandidate, PhaseDecision, ModelAssessment,
    Action, TrustConfig,
)


def route_phase(
    phase: str,
    suitabilities: List[ModelSuitability],
    physics_checks: List[PhysicsCheck],
    consensus: Optional[ConsensusResult],
    fusion_candidate: Optional[FusedPickCandidate],
    single_model_evidences: list,
    config: TrustConfig,
    phase_risk: float = 0.0,
) -> PhaseDecision:
    """
    对单个 phase (P 或 S) 执行 6 步决策
    """
    decision = PhaseDecision(phase=phase, action=Action.ABSTAIN.value)
    decision.risk_score = round(phase_risk, 1)
    decision.risk_level = _risk_level(phase_risk, config)
    reasons = []

    # ── 第 0 步: 可比性 + 硬门槛 ──────────────────────
    eligible_models = _eligible_models(suitabilities, physics_checks)
    if not eligible_models:
        decision.reason_codes = ["NO_ELIGIBLE_MODELS"]
        return decision

    decision.rejected_models = [
        s.model_name for s in suitabilities
        if s.model_name not in eligible_models
    ]

    # ── 第 1 步: surviving models ─────────────────────
    survivors = _surviving_models(eligible_models, physics_checks, consensus)
    if not survivors:
        reasons.append("NO_SURVIVING_MODELS")
        decision.reason_codes = reasons
        return decision

    # ── 第 2 步: 能否 FUSE ────────────────────────────
    if config.fusion_enabled and fusion_candidate and fusion_candidate.fusion_allowed:
        fused_contributors = set(fusion_candidate.contributors)
        surviving_set = set(survivors)
        if fused_contributors.issubset(surviving_set):
            if phase_risk > config.automatic_risk_threshold:
                decision.reason_codes = reasons + ["RISK_ABOVE_AUTO_THRESHOLD"]
                return decision
            decision.action = Action.FUSE.value
            decision.selected_model = None
            decision.selected_time_s = fusion_candidate.fused_time_s
            decision.fused_pick = fusion_candidate
            decision.reason_codes = reasons + ["FUSE_CONSENSUS_CLUSTER"]
            return decision

    # ── 第 3 步: 只剩一个 survivor → 选它 ─────────────
    if len(survivors) == 1:
        model = survivors[0]
        if phase_risk > config.automatic_risk_threshold:
            decision.reason_codes = reasons + ["RISK_ABOVE_AUTO_THRESHOLD"]
            return decision
        decision.action = Action.ACCEPT.value if model == config.primary_model else Action.ROUTE.value
        decision.selected_model = model
        decision.reason_codes = reasons + [f"ONLY_SURVIVOR_{model}"]
        return decision

    # ── 第 4 步: 两个都合理但严重分歧 ─────────────────
    if consensus and consensus.status == "DISAGREEMENT":
        decision.action = Action.ABSTAIN.value
        decision.reason_codes = reasons + ["NO_DECISIVE_EVIDENCE_BETWEEN_MODELS"]
        return decision

    # ── 第 5 步: 有其他证据支持某模型？(暂无验证档案 → ABSTAIN)
    decision.action = Action.ABSTAIN.value
    decision.reason_codes = reasons + ["INSUFFICIENT_EVIDENCE_FOR_SELECTION"]
    return decision


def _risk_level(score: float, config: TrustConfig) -> str:
    if score <= config.risk_low_max:
        return "LOW"
    if score <= config.risk_medium_max:
        return "MEDIUM"
    return "HIGH"


def _eligible_models(
    suitabilities: List[ModelSuitability],
    physics_checks: List[PhysicsCheck],
) -> List[str]:
    """筛选 eligible=True 的模型"""
    eligible = set()
    for s in suitabilities:
        if s.eligible:
            eligible.add(s.model_name)
    for pc in physics_checks:
        if pc.hard_fail and pc.target_type == "MODEL":
            eligible.discard(pc.target_id)
    return sorted(eligible)


def _surviving_models(
    eligible: List[str],
    physics_checks: List[PhysicsCheck],
    consensus: Optional[ConsensusResult],
) -> List[str]:
    """从 eligible 中进一步排除 outlier"""
    survivors = set(eligible)
    for pc in physics_checks:
        if pc.hard_fail and pc.target_id in survivors:
            survivors.discard(pc.target_id)
    if consensus and consensus.outlier_models:
        if len(consensus.inlier_models) >= 2:
            survivors -= set(consensus.outlier_models)
    return sorted(survivors)
