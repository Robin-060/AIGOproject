"""
P3 multi-model consensus analysis.

Compares P/S pick times, identifies consensus models and outliers.
This module does not make final policy decisions.
"""

from __future__ import annotations

from statistics import median
from typing import List, Optional

from .schema import (
    ConsensusResult,
    ModelPrediction,
    ModelSuitability,
    PhysicsCheck,
    TrustConfig,
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
    """Return eligible models without physics hard failures."""

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
    """Find the largest pick-time cluster within tolerance."""

    ordered = sorted(predictions, key=lambda item: item.time_s)
    best_cluster: List[ModelPrediction] = []

    for start_index in range(len(ordered)):
        current_cluster: List[ModelPrediction] = []

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
    """Check sample, window, phase and time basis."""

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
    """Return valid predictions for one phase."""

    return [
        prediction
        for prediction in predictions
        if prediction.model_name in usable_models
        and prediction.phase == phase
        and prediction.adapter_status == "OK"
        and isinstance(prediction.time_s, (int, float))
        and not isinstance(prediction.time_s, bool)
        and prediction.time_s >= 0
    ]


def analyze_multi_model_consensus(
    predictions: List[ModelPrediction],
    suitability: List[ModelSuitability],
    physics_checks: List[PhysicsCheck],
    config: Optional["TrustConfig"] = None,
) -> List[ConsensusResult]:
    """Analyze P and S consensus separately.

    Tolerances are read from TrustConfig (calibrated values);
    fall back to the module constants when no config is given.
    """
    if config is None:
        tolerance_map = dict(CONSENSUS_TOLERANCE)
        severe_map = dict(SEVERE_DISAGREEMENT)
        version = VERSION
    else:
        tolerance_map = {
            "P": config.consensus_tolerance_p_s,
            "S": config.consensus_tolerance_s_s,
        }
        severe_map = {
            "P": config.severe_disagreement_p_s,
            "S": config.severe_disagreement_s_s,
        }
        version = config.config_version

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

        eligible_models = sorted(
            {
                prediction.model_name
                for prediction in phase_predictions
            }
        )

        missing_models = sorted(
            usable_models - set(eligible_models)
        )

        if not _same_comparison_group(phase_predictions):
            results.append(
                ConsensusResult(
                    phase=phase,
                    status="DISAGREEMENT",
                    eligible_models=eligible_models,
                    inlier_models=[],
                    outlier_models=eligible_models,
                    missing_models=missing_models,
                    center_time_s=-1.0,
                    spread_s=-1.0,
                    score=0.0,
                    reasons=["COMPARISON_GROUP_MISMATCH"],
                    version=version,
                )
            )
            continue

        tolerance = tolerance_map[phase]

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
            if len(inlier_times) == 1
            else -1.0
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
                inlier_models=[
                    prediction.model_name
                    for prediction in inliers
                ],
                outlier_models=[
                    prediction.model_name
                    for prediction in outliers
                ],
                missing_models=missing_models,
                center_time_s=center_time_s,
                spread_s=spread_s,
                score=score,
                reasons=reasons,
                version=version,
            )
        )

    return results
