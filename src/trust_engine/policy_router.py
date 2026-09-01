"""
Policy Router — 6 步决策：选模型 / 融合 / 拒绝

负责人: P4
输入: P1/P2/P3 证据 + TrustConfig + 消融开关
输出: PhaseDecision (每个 phase 独立)

决策同时受 phase_risk 约束: 风险超过自动处理阈值时强制 ABSTAIN。
"""

from typing import List, Optional, Dict
import os

from src.trust_engine.confidence_calibration import calibrated_prob
from src.trust_engine.schema import (
    ModelSuitability, PhysicsCheck, ConsensusResult,
    FusedPickCandidate, PhaseDecision, ModelAssessment,
    Action, TrustConfig, SingleModelEvidence, ModelPrediction,
)

ALL_ENABLED = {"data": True, "single_model": True, "multi_model": True, "physics": True}

# ── EXP17 policy refinement 开关 (预注册: docs/experiments/exp17_preregistration.md) ──
# 默认关闭 = v1.5.1 冻结行为, 逐字节不变; 仅 EXP17 实验通过环境变量显式开启。
EXP17_POLICY_ENV = "OBS_EXP17_POLICY"


def _exp17_policy() -> str:
    return os.environ.get(EXP17_POLICY_ENV, "")


def route_phase(
    phase: str,
    suitabilities: List[ModelSuitability],
    physics_checks: List[PhysicsCheck],
    consensus: Optional[ConsensusResult],
    fusion_candidate: Optional[FusedPickCandidate],
    single_model_evidences: List[SingleModelEvidence],
    config: TrustConfig,
    enable: Optional[Dict[str, bool]] = None,
    phase_risk: float = 0.0,
    predictions: Optional[List[ModelPrediction]] = None,
) -> PhaseDecision:
    """
    对单个 phase (P 或 S) 执行 6 步决策

    Args:
        enable: 消融开关。关闭的证据不影响筛选逻辑
        phase_risk: 预先算好的四证据风险分 (0-100)，用于自动阈值约束
        predictions: 仅 EXP17-A 使用 (共识簇候选的校准置信度排序);
            默认 None, 不影响 v1.5.1 行为
    """
    if enable is None:
        enable = dict(ALL_ENABLED)

    decision = PhaseDecision(phase=phase, action=Action.ABSTAIN.value)
    decision.risk_score = round(phase_risk, 1)
    decision.risk_level = _risk_level(phase_risk, config)
    reasons = []

    # ── 第 0 步: 可比性 + 硬门槛 ──────────────────────
    eligible_models = _eligible_models(suitabilities, physics_checks, enable)
    if not eligible_models:
        decision.reason_codes = ["NO_ELIGIBLE_MODELS"]
        return decision

    decision.rejected_models = [
        s.model_name for s in suitabilities
        if s.model_name not in eligible_models
    ]

    # ── 第 1 步: surviving models ─────────────────────
    survivors = _surviving_models(eligible_models, physics_checks, consensus, enable)
    if not survivors:
        reasons.append("NO_SURVIVING_MODELS")
        decision.reason_codes = reasons
        return decision

    # ── 第 2 步: 能否 FUSE ────────────────────────────
    if config.fusion_enabled and fusion_candidate and fusion_candidate.fusion_allowed:
        fused_contributors = set(fusion_candidate.contributors)
        surviving_set = set(survivors)
        if fused_contributors.issubset(surviving_set):
            if _risk_too_high(phase_risk, config):
                decision.reason_codes = reasons + ["FUSE_RISK_ABOVE_AUTO_THRESHOLD"]
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
        if _risk_too_high(phase_risk, config):
            decision.reason_codes = reasons + [f"ONLY_SURVIVOR_{model}_RISK_ABOVE_THRESHOLD"]
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

    # ── 第 4.5 步: 多模型共识但无显式融合候选 ──────────
    if consensus and consensus.status == "CONSENSUS" and len(survivors) >= 2:
        # Fail closed: 共识本身不是自动输出许可。没有通过全部门槛的显式
        # FusedPickCandidate 时，不得改走 primary 或 consensus.center_time_s 旁路。
        candidate_reasons = (
            list(fusion_candidate.reasons) if fusion_candidate is not None
            else ["FUSION_CANDIDATE_MISSING"]
        )
        # EXP17-A (预注册, 仅显式开启): Consensus Route —
        # 共识簇内校准置信度最高、有真实拾取、风险不超阈的幸存模型 → ROUTE/ACCEPT
        if _exp17_policy() == "consensus_route":
            candidates = []
            for m in consensus.inlier_models:
                if m not in survivors:
                    continue
                ev = next((e for e in single_model_evidences
                           if e.model_name == m and e.phase == phase), None)
                if ev is None or "CONFIDENCE_CALIBRATED_AVAILABLE" not in ev.reasons:
                    continue
                pred = next((p for p in (predictions or [])
                             if p.model_name == m and p.phase == phase), None)
                if pred is None or pred.score is None:
                    continue
                candidates.append((calibrated_prob(m, pred.score), m))
            if candidates:
                candidates.sort(key=lambda x: (-x[0], x[1]))  # 校准置信度降序, 模型名 tie-break
                best = candidates[0][1]
                if not _risk_too_high(phase_risk, config):
                    decision.action = (Action.ACCEPT.value
                                       if best == config.primary_model
                                       else Action.ROUTE.value)
                    decision.selected_model = best
                    decision.reason_codes = reasons + candidate_reasons + [
                        "CONSENSUS_ROUTE_BEST_INLIER"
                    ]
                    return decision
        decision.action = Action.ABSTAIN.value
        decision.reason_codes = reasons + candidate_reasons + [
            "CONSENSUS_WITHOUT_ADMISSIBLE_FUSION"
        ]
        return decision

    # ── 第 5 步: 有其他证据支持某模型？(暂无验证档案 → ABSTAIN)
    decision.action = Action.ABSTAIN.value
    decision.reason_codes = reasons + ["INSUFFICIENT_EVIDENCE_FOR_SELECTION"]
    return decision


def _risk_too_high(phase_risk: float, config: TrustConfig) -> bool:
    """风险分超过自动处理阈值 → 不能自动 ACCEPT/ROUTE/FUSE"""
    return phase_risk > config.automatic_risk_threshold


def _risk_level(score: float, config: TrustConfig) -> str:
    if score <= config.risk_low_max:
        return "LOW"
    if score <= config.risk_medium_max:
        return "MEDIUM"
    return "HIGH"


def _eligible_models(
    suitabilities: List[ModelSuitability],
    physics_checks: List[PhysicsCheck],
    enable: Dict[str, bool],
) -> List[str]:
    """筛选 eligible 模型 (data 关闭时全部视为 eligible)"""
    eligible = set()
    for s in suitabilities:
        if not enable["data"] or s.eligible:
            eligible.add(s.model_name)
    if enable["physics"]:
        for pc in physics_checks:
            if pc.hard_fail and pc.target_type == "MODEL":
                eligible.discard(pc.target_id)
    return sorted(eligible)


def _surviving_models(
    eligible: List[str],
    physics_checks: List[PhysicsCheck],
    consensus: Optional[ConsensusResult],
    enable: Dict[str, bool],
) -> List[str]:
    """从 eligible 中排除 hard fail 和 outlier"""
    survivors = set(eligible)
    if enable["physics"]:
        for pc in physics_checks:
            if pc.hard_fail and pc.target_id in survivors:
                survivors.discard(pc.target_id)
    if enable["multi_model"] and consensus and consensus.outlier_models:
        if len(consensus.inlier_models) >= 2:
            survivors -= set(consensus.outlier_models)
    return sorted(survivors)
