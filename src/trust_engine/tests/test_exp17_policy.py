"""EXP17-A 路由级测试 (预注册: docs/experiments/exp17_preregistration.md).

验证默认路径 = v1.5.1 fail-closed 不变; 显式开启 consensus_route 时
第 4.5 步改为 ROUTE 共识簇内校准置信度最高的幸存模型。
"""

import os

import pytest

from src.trust_engine.schema import (
    Action,
    ConsensusResult,
    FusedPickCandidate,
    ModelPrediction,
    ModelSuitability,
    PhysicsCheck,
    SingleModelEvidence,
    TrustConfig,
)
from src.trust_engine.policy_router import EXP17_POLICY_ENV, route_phase


def _inputs():
    suitabilities = [
        ModelSuitability(model_name="PickBlue", eligible=True),
        ModelSuitability(model_name="EQTransformer", eligible=True),
    ]
    physics = [PhysicsCheck()]
    consensus = ConsensusResult(
        phase="P", status="CONSENSUS",
        inlier_models=["PickBlue", "EQTransformer"],
        outlier_models=[], center_time_s=10.0, spread_s=0.1,
    )
    fusion = FusedPickCandidate(phase="P", fusion_allowed=False,
                                contributors=["PickBlue", "EQTransformer"],
                                reasons=["SPREAD_ABOVE_LIMIT"])
    evidences = [
        SingleModelEvidence(model_name="PickBlue", phase="P", score=0.0,
                            reasons=["CONFIDENCE_CALIBRATED_AVAILABLE"]),
        SingleModelEvidence(model_name="EQTransformer", phase="P", score=0.0,
                            reasons=["CONFIDENCE_CALIBRATED_AVAILABLE"]),
    ]
    predictions = [
        ModelPrediction(model_name="PickBlue", phase="P", time_s=10.0,
                        score=0.9),
        ModelPrediction(model_name="EQTransformer", phase="P", time_s=10.1,
                        score=0.8),
    ]
    config = TrustConfig()
    return suitabilities, physics, consensus, fusion, evidences, predictions, config


def _call(env_value=None):
    if env_value is None:
        os.environ.pop(EXP17_POLICY_ENV, None)
    else:
        os.environ[EXP17_POLICY_ENV] = env_value
    args = _inputs()
    return route_phase(
        phase="P", suitabilities=args[0], physics_checks=args[1],
        consensus=args[2], fusion_candidate=args[3],
        single_model_evidences=args[4], config=args[6],
        phase_risk=0.0, predictions=args[5],
    )


def test_default_path_remains_fail_closed():
    """未开启 EXP17 开关时, 第 4.5 步维持 v1.5.1 fail-closed."""
    decision = _call(None)
    assert decision.action == Action.ABSTAIN.value
    assert "CONSENSUS_WITHOUT_ADMISSIBLE_FUSION" in decision.reason_codes
    assert "CONSENSUS_ROUTE_BEST_INLIER" not in decision.reason_codes


def test_exp17_a_routes_best_inlier():
    """开启 consensus_route 后, ROUTE 校准置信度最高的共识簇幸存模型."""
    decision = _call("consensus_route")
    assert decision.action == Action.ROUTE.value
    assert decision.selected_model == "PickBlue"  # cal 0.9 > 0.8
    assert "CONSENSUS_ROUTE_BEST_INLIER" in decision.reason_codes


def test_exp17_a_excludes_below_floor_models():
    """校准置信度低于门槛的模型不作为 A 候选 → 维持 ABSTAIN."""
    args = _inputs()
    args[4][1].reasons = ["LOW_CALIBRATED_CONFIDENCE_EQTransformer_P"]
    os.environ[EXP17_POLICY_ENV] = "consensus_route"
    decision = route_phase(
        phase="P", suitabilities=args[0], physics_checks=args[1],
        consensus=args[2], fusion_candidate=args[3],
        single_model_evidences=args[4], config=args[6],
        phase_risk=0.0, predictions=args[5],
    )
    # PickBlue 仍达标 → 应 ROUTE PickBlue
    assert decision.action == Action.ROUTE.value
    assert decision.selected_model == "PickBlue"


def _b_inputs():
    """第 5 步场景: 共识 INSUFFICIENT, 幸存者 2 个但仅 1 个有拾取."""
    args = list(_inputs())
    args[2] = ConsensusResult(
        phase="P", status="INSUFFICIENT",
        inlier_models=[], outlier_models=[],
        center_time_s=-1, spread_s=-1,
    )
    # 只有 PickBlue 有 P 相拾取
    args[5] = [ModelPrediction(model_name="PickBlue", phase="P",
                               time_s=10.0, score=0.9)]
    return args


def test_b_default_path_still_abstains():
    """未开启 B 时, '2 幸存者但仅 1 个有拾取'维持第 5 步 ABSTAIN."""
    args = _b_inputs()
    os.environ.pop(EXP17_POLICY_ENV, None)
    decision = route_phase(
        phase="P", suitabilities=args[0], physics_checks=args[1],
        consensus=args[2], fusion_candidate=args[3],
        single_model_evidences=args[4], config=args[6],
        phase_risk=0.0, predictions=args[5],
    )
    assert decision.action == Action.ABSTAIN.value
    assert "INSUFFICIENT_EVIDENCE_FOR_SELECTION" in decision.reason_codes


def test_exp17_b_routes_only_usable_survivor():
    """开启 only_usable_survivor 后, 恰有 1 个幸存者有拾取 → ROUTE 它."""
    args = _b_inputs()
    os.environ[EXP17_POLICY_ENV] = "only_usable_survivor"
    decision = route_phase(
        phase="P", suitabilities=args[0], physics_checks=args[1],
        consensus=args[2], fusion_candidate=args[3],
        single_model_evidences=args[4], config=args[6],
        phase_risk=0.0, predictions=args[5],
    )
    assert decision.action == Action.ROUTE.value
    assert decision.selected_model == "PickBlue"
    assert "ONLY_USABLE_SURVIVOR_PickBlue" in decision.reason_codes


def test_exp17_b_risk_gate_still_applies():
    """风险超阈时 B 不生效 (与第 3 步原逻辑一致)."""
    args = _b_inputs()
    os.environ[EXP17_POLICY_ENV] = "only_usable_survivor"
    config = TrustConfig()
    decision = route_phase(
        phase="P", suitabilities=args[0], physics_checks=args[1],
        consensus=args[2], fusion_candidate=args[3],
        single_model_evidences=args[4], config=config,
        phase_risk=99.0, predictions=args[5],
    )
    assert decision.action == Action.ABSTAIN.value
    assert any("RISK_ABOVE" in c for c in decision.reason_codes)


def _single_survivor_inputs():
    """第 3 步场景: 唯一幸存者, 但无该相位拾取 (invalid-route bug 场景)."""
    args = list(_inputs())
    args[0] = [ModelSuitability(model_name="PickBlue", eligible=True)]
    args[2] = ConsensusResult(phase="P", status="INSUFFICIENT",
                              inlier_models=[], outlier_models=[],
                              center_time_s=-1, spread_s=-1)
    args[4] = [SingleModelEvidence(model_name="PickBlue", phase="P",
                                   score=None,
                                   reasons=["MODEL_SCORE_UNAVAILABLE"])]
    args[5] = []   # 无任何 P 相预测
    return args


def test_v151_bugfix_single_survivor_without_pick_abstains():
    """v1.5.1-bugfix: 唯一幸存者无有效拾取 → 不得 ROUTE, ABSTAIN."""
    args = _single_survivor_inputs()
    os.environ.pop(EXP17_POLICY_ENV, None)
    decision = route_phase(
        phase="P", suitabilities=args[0], physics_checks=args[1],
        consensus=args[2], fusion_candidate=args[3],
        single_model_evidences=args[4], config=args[6],
        phase_risk=0.0, predictions=args[5],
    )
    assert decision.action == Action.ABSTAIN.value
    assert "ONLY_SURVIVOR_PickBlue_NO_VALID_PICK" in decision.reason_codes


def test_v151_bugfix_single_survivor_with_pick_routes():
    """有有效拾取的唯一幸存者 → 维持原 ROUTE 行为."""
    args = _single_survivor_inputs()
    args[5] = [ModelPrediction(model_name="PickBlue", phase="P",
                               time_s=10.0, score=0.9)]
    os.environ.pop(EXP17_POLICY_ENV, None)
    decision = route_phase(
        phase="P", suitabilities=args[0], physics_checks=args[1],
        consensus=args[2], fusion_candidate=args[3],
        single_model_evidences=args[4], config=args[6],
        phase_risk=0.0, predictions=args[5],
    )
    assert decision.action == Action.ROUTE.value
    assert decision.selected_model == "PickBlue"
