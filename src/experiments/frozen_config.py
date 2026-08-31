"""
frozen_config.py — 冻结实验配置读取 (v1.5.1)

复现链各脚本的统一参数来源。任何脚本需要实验控制参数
(冻结档案 / Equal-Coverage 点位 / 参数集版本) 必须经此读取,
禁止在脚本内硬编码复刻 — 保证"配置文件真正控制实验"。

用法:
    from src.experiments.frozen_config import (
        load_frozen_experiment, load_equal_coverage_points)
"""

from src.trust_engine.config_loader import CONFIG_PATH, load_frozen_config

FROZEN_CONFIG = CONFIG_PATH


def load_frozen_experiment():
    """返回 (frozen_profile, coverage_points, parameter_set).

    任一控制字段缺失即抛错 — 冻结配置失效时拒绝运行, 不静默回退。
    """
    frozen = load_frozen_config()
    return (
        frozen.selected_profile,
        [int(point) for point in frozen.coverage_points],
        str(frozen.raw["trust_engine"]["parameter_set"]),
    )


def load_equal_coverage_points():
    """返回 YAML 冻结的 Equal-Coverage 点位列表 (int)."""
    _, points, _ = load_frozen_experiment()
    return points
