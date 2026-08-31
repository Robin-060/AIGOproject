from src.trust_engine.fusion import build_fusion_candidates
from src.trust_engine.multi_model import analyze_multi_model_consensus
from src.trust_engine.policy_router import route_phase
from src.trust_engine.schema import (
    ConsensusResult,
    ModelPrediction,
    ModelSuitability,
    TrustConfig,
)


def _predictions(phase_net_score=0.90, pick_blue_score=0.90,
                 obst_score=0.80):
    return [
        ModelPrediction(
            sample_id="sample-1",
            window_id="window-1",
            model_name="PhaseNet",
            phase="P",
            time_s=12.30,
            score=phase_net_score,
            source_time_basis="WINDOW_SECONDS",
        ),
        ModelPrediction(
            sample_id="sample-1",
            window_id="window-1",
            model_name="PickBlue",
            phase="P",
            time_s=12.42,
            score=pick_blue_score,
            source_time_basis="WINDOW_SECONDS",
        ),
        ModelPrediction(
            sample_id="sample-1",
            window_id="window-1",
            model_name="OBSTransformer",
            phase="P",
            time_s=17.80,
            score=obst_score,
            source_time_basis="WINDOW_SECONDS",
        ),
    ]


def _suitability():
    return [
        ModelSuitability(model_name="PhaseNet", eligible=True),
        ModelSuitability(model_name="PickBlue", eligible=True),
        ModelSuitability(model_name="OBSTransformer", eligible=True),
    ]


def test_consensus_and_fusion():
    predictions = _predictions()
    consensus_results = analyze_multi_model_consensus(
        predictions=predictions,
        suitability=_suitability(),
        physics_checks=[],
    )

    p_result = next(
        result
        for result in consensus_results
        if result.phase == "P"
    )

    assert p_result.status == "CONSENSUS"
    assert set(p_result.inlier_models) == {
        "PhaseNet",
        "PickBlue",
    }
    assert p_result.outlier_models == ["OBSTransformer"]
    assert round(p_result.center_time_s, 2) == 12.36
    assert round(p_result.spread_s, 2) == 0.12

    fusion_candidates = build_fusion_candidates(
        predictions=predictions,
        consensus_results=consensus_results,
    )

    p_candidate = next(
        candidate
        for candidate in fusion_candidates
        if candidate.phase == "P"
    )

    assert p_candidate.fusion_allowed is True
    assert round(p_candidate.fused_time_s, 2) == 12.36
    assert set(p_candidate.contributors) == {
        "PhaseNet",
        "PickBlue",
    }
    assert p_candidate.excluded_models == ["OBSTransformer"]


def test_fusion_rejected_when_calibrated_confidence_low():
    """第二刀: 一致 ≠ 可信 — 低校准置信度时拒绝融合 (治抱团一起错)."""
    predictions = _predictions(phase_net_score=0.50, pick_blue_score=0.55)
    consensus_results = analyze_multi_model_consensus(
        predictions=predictions,
        suitability=_suitability(),
        physics_checks=[],
    )
    fusion_candidates = build_fusion_candidates(
        predictions=predictions,
        consensus_results=consensus_results,
    )
    p_candidate = next(
        candidate
        for candidate in fusion_candidates
        if candidate.phase == "P"
    )
    assert p_candidate.fusion_allowed is False
    assert "FUSION_CALIBRATED_CONFIDENCE_BELOW_FLOOR" in p_candidate.reasons


def test_fusion_uses_active_config_tolerance_and_floor():
    predictions = _predictions()
    config = TrustConfig(
        consensus_tolerance_p_s=0.34,
        fusion_confidence_floor=0.99,
        config_version="test-strict",
    )
    consensus_results = analyze_multi_model_consensus(
        predictions=predictions,
        suitability=_suitability(),
        physics_checks=[],
        config=config,
    )
    candidate = next(
        item for item in build_fusion_candidates(
            predictions, consensus_results, config
        ) if item.phase == "P"
    )
    assert candidate.fusion_allowed is False
    assert candidate.threshold_version == "test-strict"


def test_consensus_without_admissible_candidate_is_fail_closed():
    decision = route_phase(
        phase="P",
        suitabilities=[
            ModelSuitability(model_name="M1", eligible=True),
            ModelSuitability(model_name="M2", eligible=True),
        ],
        physics_checks=[],
        consensus=ConsensusResult(
            phase="P", status="CONSENSUS", inlier_models=["M1", "M2"]
        ),
        fusion_candidate=None,
        single_model_evidences=[],
        config=TrustConfig(automatic_risk_threshold=100.0),
        phase_risk=0.0,
    )
    assert decision.action == "ABSTAIN"
    assert "FUSION_CANDIDATE_MISSING" in decision.reason_codes


if __name__ == "__main__":
    test_consensus_and_fusion()
    test_fusion_rejected_when_calibrated_confidence_low()
    print("P3 consensus and fusion tests passed.")
