"""
P3：多模型一致性分析。

负责比较不同模型的 P/S 拾取时间，
识别共识模型、离群模型和模型冲突。
不负责最终的 ACCEPT、FUSE 或 ABSTAIN 决策。
"""

from __future__ import annotations

from statistics import median
from typing import List

from .schema import (
    ConsensusResult,
    ModelPrediction,
    ModelSuitability,
    PhysicsCheck,
)


CONSENSUS_TOLERANCE = {
    "P": 0.30,
    "S": 0.50,
}

SEVERE_DISAGREEMENT = {
    "P": 1.00,
    "S": 2.00,
}

VERSION = "heuristic_v0.1"
def _get_usable_models(
    suitability: List[ModelSuitability],
    physics_checks: List[PhysicsCheck],
) -> set[str]:
    """返回 eligible 且没有物理 hard fail 的模型名称。"""

    eligible_models = {
        item.model_name
        for item in suitability
        if item.eligible
    }

    hard_failed_models = {
        check.target_id
        for check in physics_checks
        if check.target_type == "MODEL" and check.hard_fail
    }

    return eligible_models - hard_failed_models


def _find_largest_cluster(
    predictions: List[ModelPrediction],
    tolerance: float,
) -> tuple[List[ModelPrediction], List[ModelPrediction]]:
    """寻找时间跨度不超过 tolerance 的最大模型簇。"""

    ordered = sorted(predictions, key=lambda item: item.time_s)
    best_cluster: List[ModelPrediction] = []

    for start_index in range(len(ordered)):
        current_cluster = []

        for prediction in ordered[start_index:]:
            if prediction.time_s - ordered[start_index].time_s <= tolerance:
                current_cluster.append(prediction)
            else:
                break

        if len(current_cluster) > len(best_cluster):
            best_cluster = current_cluster

    outliers = [
        prediction
        for prediction in ordered
        if prediction not in best_cluster
    ]

    return best_cluster, outliers




def _same_comparison_group(
    predictions: List[ModelPrediction],
) -> bool:
    """确认所有预测属于同一个 sample、window 和 phase。"""

    if not predictions:
        return True

    first = predictions[0]

    return all(
        prediction.sample_id == first.sample_id
        and prediction.window_id == first.window_id
        and prediction.phase == first.phase
        and prediction.source_time_basis == first.source_time_basis
        for prediction in predictions
    )


def _get_phase_predictions(
    predictions: List[ModelPrediction],
    usable_models: set[str],
    phase: str,
) -> List[ModelPrediction]:
    """筛选指定 phase 中可以参与比较的预测。"""

    return [
        prediction
        for prediction in predictions
        if prediction.model_name in usable_models
        and prediction.phase == phase
        and isinstance(prediction.time_s, (int, float))
        and prediction.time_s >= 0
    ]


def analyze_multi_model_consensus(
    predictions: List[ModelPrediction],
    suitability: List[ModelSuitability],
    physics_checks: List[PhysicsCheck],
) -> List[ConsensusResult]:
    """分别分析 P 波和 S 波的多模型一致性。"""

    usable_models = _get_usable_models(
        suitability,
        physics_checks,
    )
    results: List[ConsensusResult] = []

    for phase in ("P", "S"):
        phase_predictions = _get_phase_predictions(
            predictions,
            usable_models,
            phase,
        )
        if not _same_comparison_group(phase_predictions):
            raise ValueError(
                "Predictions must share sample_id, window_id, and phase."
            )

        tolerance = CONSENSUS_TOLERANCE[phase]
        inliers, outliers = _find_largest_cluster(
            phase_predictions,
            tolerance,
        )

        if len(phase_predictions) < 2:
            status = "INSUFFICIENT"
            reasons = ["INSUFFICIENT_MODEL_COUNT"]
        elif len(inliers) >= 2:
            status = "CONSENSUS"
            reasons = ["MODEL_CONSENSUS"]

            if outliers:
                reasons.append("MODEL_OUTLIER_DETECTED")
        else:
            status = "DISAGREEMENT"
            reasons = [f"MODEL_DISAGREEMENT_{phase}"]
        inlier_times = [
            prediction.time_s
            for prediction in inliers
        ]

        center_time_s = (
            median(inlier_times)
            if inlier_times
            else -1.0
        )

        spread_s = (
            max(inlier_times) - min(inlier_times)
            if len(inlier_times) >= 2
            else 0.0
        )

        eligible_models = sorted({
            prediction.model_name
            for prediction in phase_predictions
        })
        inlier_models = sorted({
            prediction.model_name
            for prediction in inliers
        })
        outlier_models = sorted({
            prediction.model_name
            for prediction in outliers
        })
        missing_models = sorted(
            usable_models - set(eligible_models)
        )
              score = (
            len(inliers) / len(phase_predictions)
            if phase_predictions
            else 0.0
        )

        results.append(
            ConsensusResult(
                phase=phase,
                status=status,
                eligible_models=eligible_models,
                inlier_models=inlier_models,
                outlier_models=outlier_models,
                missing_models=missing_models,
                center_time_s=center_time_s,
                spread_s=spread_s,
                score=score,
                reasons=reasons,
            )
        )

    return results
