"""
P3 fusion-candidate generation.

Creates median-based candidates from consensus inliers.
This module does not make the final policy decision.
"""

from __future__ import annotations

from statistics import median
from typing import List

from .confidence_calibration import CALIBRATED_CONFIDENCE_FLOOR, calibrated_prob
from .multi_model import CONSENSUS_TOLERANCE
from .schema import (
    ConsensusResult,
    FusedPickCandidate,
    ModelPrediction,
)


FUSION_METHOD = "MEDIAN_INLIERS"
VERSION = "heuristic_v0.1"


def _get_inlier_predictions(
    predictions: List[ModelPrediction],
    consensus: ConsensusResult,
) -> List[ModelPrediction]:
    """Return predictions selected as consensus inliers."""

    inlier_names = set(consensus.inlier_models)

    return [
        prediction
        for prediction in predictions
        if prediction.phase == consensus.phase
        and prediction.model_name in inlier_names
        and prediction.adapter_status == "OK"
        and isinstance(prediction.time_s, (int, float))
        and not isinstance(prediction.time_s, bool)
        and prediction.time_s >= 0
    ]


def _same_fusion_group(
    predictions: List[ModelPrediction],
) -> bool:
    """Check that contributors use the same comparison basis."""

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


def build_fusion_candidates(
    predictions: List[ModelPrediction],
    consensus_results: List[ConsensusResult],
) -> List[FusedPickCandidate]:
    """Build fusion candidates from consensus results."""

    candidates: List[FusedPickCandidate] = []

    for consensus in consensus_results:
        phase_predictions = [
            prediction
            for prediction in predictions
            if prediction.phase == consensus.phase
        ]

        inliers = _get_inlier_predictions(
            predictions,
            consensus,
        )

        inlier_times = [
            prediction.time_s
            for prediction in inliers
        ]

        spread_s = (
            max(inlier_times) - min(inlier_times)
            if len(inlier_times) >= 2
            else 0.0
            if len(inlier_times) == 1
            else -1.0
        )

        tolerance = CONSENSUS_TOLERANCE.get(
            consensus.phase,
            -1.0,
        )

        # 第二刀: FUSE 需额外满足校准置信度条件 (一致 ≠ 可信, 治"抱团一起错")
        calibrated_ok = (
            len(inliers) >= 2
            and all(
                (cp := calibrated_prob(prediction.model_name, prediction.score)) is not None
                and cp >= CALIBRATED_CONFIDENCE_FLOOR
                for prediction in inliers
            )
        )

        fusion_allowed = (
            consensus.status == "CONSENSUS"
            and len(inliers) >= 2
            and tolerance >= 0
            and spread_s <= tolerance
            and _same_fusion_group(inliers)
            and calibrated_ok
        )

        if fusion_allowed:
            contributors = [
                prediction.model_name
                for prediction in inliers
            ]

            contributor_names = set(contributors)

            excluded_models = [
                prediction.model_name
                for prediction in phase_predictions
                if prediction.model_name not in contributor_names
            ]

            reasons = ["MODEL_CONSENSUS"]
            fused_time_s = median(inlier_times)

        else:
            contributors = []

            excluded_models = [
                prediction.model_name
                for prediction in phase_predictions
            ]

            reasons = list(consensus.reasons)

            if not calibrated_ok and "FUSION_CALIBRATED_CONFIDENCE_BELOW_FLOOR" not in reasons:
                reasons.append("FUSION_CALIBRATED_CONFIDENCE_BELOW_FLOOR")

            if "FUSION_NOT_ALLOWED" not in reasons:
                reasons.append("FUSION_NOT_ALLOWED")

            fused_time_s = -1.0

        candidates.append(
            FusedPickCandidate(
                phase=consensus.phase,
                fusion_allowed=fusion_allowed,
                fused_time_s=fused_time_s,
                contributors=contributors,
                excluded_models=excluded_models,
                spread_s=spread_s,
                fusion_method=FUSION_METHOD,
                threshold_version=VERSION,
                reasons=reasons,
            )
        )

    return candidates
