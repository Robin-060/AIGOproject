"""
frozen_config.py — 冻结实验配置读取 (v1.5.1)

复现链各脚本的统一参数来源。任何脚本需要实验控制参数
(冻结档案 / Equal-Coverage 点位 / 参数集版本) 必须经此读取,
禁止在脚本内硬编码复刻 — 保证"配置文件真正控制实验"。

用法:
    from src.experiments.frozen_config import (
        load_frozen_experiment, load_equal_coverage_points)
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FROZEN_CONFIG = ROOT / "configs" / "semifinal_main.yaml"


def _load_yaml():
    import yaml
    with open(FROZEN_CONFIG, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_frozen_experiment():
    """返回 (frozen_profile, coverage_points, parameter_set).

    任一控制字段缺失即抛错 — 冻结配置失效时拒绝运行, 不静默回退。
    """
    raw = _load_yaml()
    frozen_profile = (raw.get("experiment") or {}).get("frozen_profile")
    points = (raw.get("equal_coverage") or {}).get("points")
    param_set = (raw.get("trust_engine") or {}).get("parameter_set")
    if not frozen_profile:
        raise ValueError(f"冻结配置缺失 experiment.frozen_profile ({FROZEN_CONFIG})")
    if not points:
        raise ValueError(f"冻结配置缺失 equal_coverage.points ({FROZEN_CONFIG})")
    if not param_set:
        raise ValueError(f"冻结配置缺失 trust_engine.parameter_set ({FROZEN_CONFIG})")
    return frozen_profile, [int(p) for p in points], param_set


def load_equal_coverage_points():
    """返回 YAML 冻结的 Equal-Coverage 点位列表 (int)."""
    _, points, _ = load_frozen_experiment()
    return points
