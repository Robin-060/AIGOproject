"""
P3：生成多模型融合候选结果。

只使用共识簇中的模型计算候选时间，
不负责最终的 FUSE、ACCEPT 或 ABSTAIN 决策。
"""

from __future__ import annotations

from statistics import median
from typing import List

from .schema import (
    ConsensusResult,
    FusedPickCandidate,
    ModelPrediction,
)
from .multi_model import CONSENSUS_TOLERANCE

FUSION_METHOD = "MEDIAN_INLIERS"
VERSION = "heuristic_v0.1"


def _get_inlier_predictions(
    predictions: List[ModelPrediction],
    consensus: ConsensusResult,
) -> List[ModelPrediction]:
    """找出属于共识簇、可以参与融合的模型预测。"""

    return [
        prediction
        for prediction in predictions
        if prediction.phase == consensus.phase
        and prediction.model_name in consensus.inlier_models
        and isinstance(prediction.time_s, (int, float))
        and prediction.time_s >= 0
    ]


def _same_fusion_group(
    predictions: List[ModelPrediction],
) -> bool:
    """确认参与融合的预测属于同一数据片段和时间基准。"""

    if not predictions:
        return False

    first = predictions[0]
    first_time_basis = first.source_time_basis

    return all(
        prediction.sample_id == first.sample_id
        and prediction.window_id == first.window_id
        and prediction.phase == first.phase
        and prediction.source_time_basis == first_time_basis
        for prediction in predictions
    )


def build_fusion_candidates(
    predictions: List[ModelPrediction],
    consensus_results: List[ConsensusResult],
) -> List[FusedPickCandidate]:
    """根据多模型共识结果生成融合候选。"""

    candidates: List[FusedPickCandidate] = []

    for consensus in consensus_results:
        inlier_predictions = _get_inlier_predictions(
            predictions,
            consensus,
        )
        tolerance = CONSENSUS_TOLERANCE.get(consensus.phase)

        fusion_allowed = (
            consensus.status == "CONSENSUS"
            and len(inlier_predictions) >= 2
            and tolerance is not None
            and consensus.spread_s is not None
            and consensus.spread_s <= tolerance
            and _same_fusion_group(inlier_predictions)
        )

        inlier_times = [
            prediction.time_s
            for prediction in inlier_predictions
        ]
        inlier_model_names = sorted({
            prediction.model_name
            for prediction in inlier_predictions
        })
        all_phase_models = {
            prediction.model_name
            for prediction in predictions
            if prediction.phase == consensus.phase
        }

        if fusion_allowed:
            fused_time_s = median(inlier_times)
            contributors = inlier_model_names
            excluded_models = sorted(
                all_phase_models - set(contributors)
            )
            reasons = ["MODEL_CONSENSUS"]
        else:
            fused_time_s = -1.0
            contributors = []
            excluded_models = sorted(all_phase_models)
            reasons = list(consensus.reasons)

            if "FUSION_NOT_ALLOWED" not in reasons:
                reasons.append("FUSION_NOT_ALLOWED")

        candidates.append(
            FusedPickCandidate(
                phase=consensus.phase,
                fusion_allowed=fusion_allowed,
                fused_time_s=fused_time_s,
                contributors=contributors,
                excluded_models=excluded_models,
                spread_s=consensus.spread_s,
                fusion_method=FUSION_METHOD,
                threshold_version=VERSION,
                reasons=reasons,
            )
        )

    return candidates
