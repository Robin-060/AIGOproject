"""冻结参数对账测试 (v1.5.1)

引擎代码内冻结的校准常量必须与冻结产物 JSON 一致; 不一致即测试失败 —
防止"参数实际冻结在代码里、冻结文件成为摆设"的漂移。
已知例外 (如实断言, 不静默): NATURAL_PENALTIES.moderate_signal = 1.0 为
v1.4 冻结值, ds4_natural_hazard.json 的 raw score 列为 2.0 (30×rate 候选分);
差异自冻结提交 0b6015c 即存在, 全部实验数字以代码冻结值计算。
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_platt_params_match_frozen_calibrators():
    from src.trust_engine.confidence_calibration import PLATT_PARAMS
    with open(ROOT / "results" / "calibration" / "platt_calibrators.json",
              encoding="utf-8") as f:
        frozen = json.load(f)
    # PhaseNet 缺席 = 刻意不校准 (样本不足), 校验其确实不在代码常量中
    assert "PhaseNet" not in PLATT_PARAMS
    for model, params in PLATT_PARAMS.items():
        assert model in frozen, f"{model} 不在冻结校准文件"
        assert abs(params["a"] - frozen[model]["a"]) <= 0.01, (model, params)
        assert abs(params["b"] - frozen[model]["b"]) <= 0.01, (model, params)


def test_natural_penalties_match_frozen_hazard():
    from src.trust_engine.data_evidence import NATURAL_PENALTIES
    with open(ROOT / "results" / "ds4_natural_hazard.json",
              encoding="utf-8") as f:
        frozen = json.load(f)["natural"]
    exact = {
        "channel_missing": "channel_missing",
        "gap_severe": "gap_severe",
        "clipping_severe": "clipping_severe",
        "clipping_moderate": "clipping_moderate",
        "strong_noise": "strong_noise",
    }
    for code_key, json_key in exact.items():
        assert code_key in NATURAL_PENALTIES, code_key
        assert abs(NATURAL_PENALTIES[code_key] - frozen[json_key]["score"]) <= 0.01, \
            (code_key, NATURAL_PENALTIES[code_key], frozen[json_key]["score"])
    # 已知例外: v1.4 冻结值 1.0 vs raw 候选分 2.0 (见模块 docstring)
    assert abs(NATURAL_PENALTIES["moderate_signal"] - 1.0) <= 1e-9
    assert abs(frozen["moderate_signal"]["score"] - 2.0) <= 0.01
