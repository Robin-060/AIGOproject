from src.trust_engine.schema import EvidenceStatus, ModelPrediction
from src.trust_engine.single_model import evaluate_single_model_evidence


def test_missing_model_score_is_insufficient():
    result = evaluate_single_model_evidence(
        [ModelPrediction(model_name="PhaseNet", phase="P", score=None)]
    )[0]
    assert result.status == EvidenceStatus.INSUFFICIENT.value
    assert result.score is None
    assert result.reasons == ["MODEL_SCORE_UNAVAILABLE"]


def test_two_models_are_preserved_as_separate_evidence():
    results = evaluate_single_model_evidence(
        [
            ModelPrediction(model_name="PhaseNet", phase="P", score=0.90),
            ModelPrediction(model_name="PickBlue", phase="P", score=0.80),
        ]
    )
    assert [(result.model_name, result.phase) for result in results] == [
        ("PhaseNet", "P"),
        ("PickBlue", "P"),
    ]


def test_uncalibrated_scores_never_create_selected_model_reason():
    results = evaluate_single_model_evidence(
        [
            ModelPrediction(model_name="PhaseNet", phase="P", score=0.90),
            ModelPrediction(model_name="PickBlue", phase="P", score=0.80),
        ]
    )
    assert all("SELECTED_MODEL" not in result.reasons for result in results)
