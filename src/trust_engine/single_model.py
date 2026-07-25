"""P1 per-model, per-phase confidence evidence."""

from typing import List

from src.trust_engine.schema import (
    EvidenceStatus,
    ModelPrediction,
    SingleModelEvidence,
)


CONFIDENCE_THRESHOLD = 0.30


def evaluate_single_model_evidence(
    predictions: List[ModelPrediction],
) -> List[SingleModelEvidence]:
    """Preserve one evidence result for each supplied model and phase pair."""

    results = []

    for prediction in predictions:
        if prediction.score is None:
            results.append(
                SingleModelEvidence(
                    model_name=prediction.model_name,
                    phase=prediction.phase,
                    score=None,
                    reasons=["MODEL_SCORE_UNAVAILABLE"],
                    status=EvidenceStatus.INSUFFICIENT.value,
                )
            )
            continue

        if prediction.score < CONFIDENCE_THRESHOLD:
            risk_score = 5
            reasons = [
                f"LOW_CONFIDENCE_{prediction.model_name}_{prediction.phase}"
            ]
        else:
            risk_score = 0
            reasons = ["CONFIDENCE_AVAILABLE"]

        results.append(
            SingleModelEvidence(
                model_name=prediction.model_name,
                phase=prediction.phase,
                score=risk_score,
                reasons=reasons,
                status=EvidenceStatus.AVAILABLE.value,
            )
        )

    return results
