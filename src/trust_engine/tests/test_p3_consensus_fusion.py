from src.trust_engine.fusion import build_fusion_candidates
from src.trust_engine.multi_model import analyze_multi_model_consensus
from src.trust_engine.schema import ModelPrediction, ModelSuitability


def test_consensus_and_fusion():
    predictions = [
        ModelPrediction(
            sample_id="sample-1",
            window_id="window-1",
            model_name="PhaseNet",
            phase="P",
            time_s=12.30,
            source_time_basis="WINDOW_SECONDS",
        ),
        ModelPrediction(
            sample_id="sample-1",
            window_id="window-1",
            model_name="PickBlue",
            phase="P",
            time_s=12.42,
            source_time_basis="WINDOW_SECONDS",
        ),
        ModelPrediction(
            sample_id="sample-1",
            window_id="window-1",
            model_name="OBSTransformer",
            phase="P",
            time_s=17.80,
            source_time_basis="WINDOW_SECONDS",
        ),
    ]

    suitability = [
        ModelSuitability(model_name="PhaseNet", eligible=True),
        ModelSuitability(model_name="PickBlue", eligible=True),
        ModelSuitability(model_name="OBSTransformer", eligible=True),
    ]

    consensus_results = analyze_multi_model_consensus(
        predictions=predictions,
        suitability=suitability,
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


if __name__ == "__main__":
    test_consensus_and_fusion()
    print("P3 consensus and fusion test passed.")
