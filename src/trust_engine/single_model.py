"""P1 per-model, per-phase confidence evidence (v1.5 校准语义)."""

from typing import List

from src.trust_engine.confidence_calibration import (
    calibrated_prob,
)
from src.trust_engine.schema import (
    EvidenceStatus,
    ModelPrediction,
    SingleModelEvidence,
    TrustConfig,
)


def evaluate_single_model_evidence(
    predictions: List[ModelPrediction],
    config: TrustConfig = None,
) -> List[SingleModelEvidence]:
    """Preserve one evidence result for each supplied model and phase pair.

    v1.5: 置信度经 Platt 校准 (PickBlue/OBSTransformer/EQT);
    PhaseNet(geofon) 样本不足保留 raw 并如实标注。
    校准正确率 < 0.70 → 警示分 5; 否则 0。
    """

    config = config or TrustConfig()
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

        calibrated = calibrated_prob(prediction.model_name, prediction.score)

        if calibrated < config.fusion_confidence_floor:
            risk_score = config.single_low_confidence_score
            reasons = [
                f"LOW_CALIBRATED_CONFIDENCE_{prediction.model_name}_{prediction.phase}"
            ]
        else:
            risk_score = 0
            reasons = ["CONFIDENCE_CALIBRATED_AVAILABLE"]

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
