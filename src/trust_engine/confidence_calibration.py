"""置信度校准器 (v1.5) — Platt/logistic, main 拟合 + holdout 验证

校准语义 (C 第一刀): raw 0.90 不可直接解读;
calibrated 0.78 ≈ 校准集上这类输出约 78% 正确。
- PickBlue / EQTransformer / OBSTransformer: Platt 校准 (holdout Brier 改善)
- PhaseNet (geofon): 校准样本不足 (main <30), 保留 raw 并如实标注

出处: results/calibration/platt_calibrators.json (main 拟合, holdout Brier/ECE)
"""

import numpy as np
from scipy.special import expit

PLATT_PARAMS = {
    "PickBlue": {"a": 2.82, "b": 0.20},
    "OBSTransformer": {"a": 3.87, "b": -1.81},
    "EQTransformer": {"a": 3.65, "b": -0.29},
    # PhaseNet 缺席 = 不校准 (样本不足), calibrated = raw
}

CALIBRATED_CONFIDENCE_FLOOR = 0.70  # 校准正确率下限 (FUSE 门槛 / 单模型警示线)


def calibrated_prob(model_name: str, raw_score: float):
    """raw confidence → calibrated probability; 未校准模型返回原值."""
    if raw_score is None:
        return None
    params = PLATT_PARAMS.get(model_name)
    if params is None:
        return raw_score
    return float(expit(params["a"] * raw_score + params["b"]))


def is_calibrated(model_name: str) -> bool:
    return model_name in PLATT_PARAMS
