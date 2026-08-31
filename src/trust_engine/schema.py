"""
统一 Schema — Trust Engine 全组共用数据结构 v2

负责人: P4
必须最先完成，解锁 P1/P2/P3
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from enum import Enum
import json


# ═══════════════════════════════════════
# 状态枚举
# ═══════════════════════════════════════

class EvidenceStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    INSUFFICIENT = "INSUFFICIENT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class SuitabilityLevel(str, Enum):
    COMPATIBLE = "COMPATIBLE"
    DEGRADED = "DEGRADED"
    INCOMPATIBLE = "INCOMPATIBLE"
    UNKNOWN = "UNKNOWN"


class ConsensusStatus(str, Enum):
    CONSENSUS = "CONSENSUS"
    DISAGREEMENT = "DISAGREEMENT"
    INSUFFICIENT = "INSUFFICIENT"


class PhysicsStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INSUFFICIENT = "INSUFFICIENT"


class FinalPairStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class Action(str, Enum):
    ACCEPT = "ACCEPT"
    ROUTE = "ROUTE"
    FUSE = "FUSE"
    ABSTAIN = "ABSTAIN"


# ═══════════════════════════════════════
# 输入对象
# ═══════════════════════════════════════

@dataclass
class SampleMetadata:
    sample_id: str
    deployment_id: str = ""
    station_id: str = ""
    window_id: str = ""
    start_time_utc: str = ""
    duration_s: float = 60.0
    canonical_time_basis: str = "WINDOW_SECONDS"
    expected_event: Optional[bool] = None
    data_source: str = "REAL"
    # P1 扩展字段
    preprocessing_version: str = ""
    resampling_applied: bool = False
    resampling_trace_id: Optional[str] = None


@dataclass
class QualityReport:
    available_channels: List[str] = field(default_factory=list)
    missing_channels: List[str] = field(default_factory=list)
    required_channels_for_task: List[str] = field(default_factory=lambda: ["Z", "N", "E"])
    sampling_rate_hz: float = 100.0
    gap_ratio: float = 0.0
    clipping_ratio: float = 0.0
    snr_db: Optional[float] = None
    metric_version: str = "v0.1"
    source: str = "REAL_CALCULATION"

    def summary(self) -> str:
        issues = []
        if self.missing_channels:
            issues.append(f"缺{self.missing_channels}通道")
        if self.gap_ratio > 0.05:
            issues.append(f"断点率{self.gap_ratio:.1%}")
        if self.clipping_ratio > 0.05:
            issues.append(f"削波率{self.clipping_ratio:.1%}")
        if self.snr_db is not None and self.snr_db < 3.0:
            issues.append(f"低SNR({self.snr_db:.1f}dB)")
        return "数据质量良好" if not issues else "质量问题: " + ", ".join(issues)


@dataclass
class ModelProfile:
    model_name: str
    model_version: str = "unknown"
    model_family: str = ""
    required_channels: List[str] = field(default_factory=list)
    preferred_channels: List[str] = field(default_factory=list)
    accepted_sampling_rates_hz: List[float] = field(default_factory=list)
    resampling_supported: bool = False
    required_preprocessing_version: str = ""
    validation_profile_id: Optional[str] = None
    validation_domain_known: bool = False
    profile_source: str = "REAL_ADAPTER"


@dataclass
class ModelPrediction:
    sample_id: str = ""
    window_id: str = ""
    model_name: str = ""
    model_version: str = "unknown"
    phase: str = ""
    time_s: float = -1
    pick_time_utc: Optional[str] = None
    source_time_basis: str = "WINDOW_SECONDS"
    score: Optional[float] = None
    adapter_status: str = "OK"
    preprocessing_version: str = ""
    prediction_source: str = "REAL_MODEL"


# P1 扩展: Adapter 状态
@dataclass
class AdapterStatus:
    model_name: str = ""
    loaded: bool = False
    run_succeeded: bool = False
    output_comparable: bool = False


# ═══════════════════════════════════════
# 配置
# ═══════════════════════════════════════

@dataclass
class TrustConfig:
    primary_model: str = ""
    fusion_enabled: bool = True
    consensus_tolerance_p_s: float = 0.34    # calibrated: 95%分位 (n=674)
    consensus_tolerance_s_s: float = 0.51    # calibrated: 95%分位 (n=455)
    automatic_risk_threshold: float = 10.0     # 风险分 ≤10 自动处理 (错误率 ≤12.6%)
    risk_low_max: float = 10.0               # calibrated: 风险校准曲线 (n=891, 10分处错误率12.6%)
    risk_medium_max: float = 30.0            # calibrated: 风险校准曲线 (30分处错误率76.5%)
    min_sp_s: float = 5.7                     # calibrated: 2.5%分位 (n=411)
    max_sp_s: float = 33.42                   # calibrated: 97.5%分位 (n=411)
    severe_disagreement_p_s: float = 1.0
    severe_disagreement_s_s: float = 2.0
    required_channels_for_task: List[str] = field(default_factory=lambda: ["Z", "N", "E"])
    # 证据权重上限 (四类证据各自的风险分满分)
    data_weight: float = 30.0                 # 保留启发式: 批量数据无质量失败样本, 故障注入验证有效性
    single_model_weight: float = 24.0         # calibrated: 逻辑回归拟合 (n=895)
    multi_model_weight: float = 37.0          # calibrated: 逻辑回归拟合 (n=895)
    physics_weight: float = 40.0              # calibrated: 逻辑回归拟合 (n=895)
    fusion_confidence_floor: float = 0.70      # v1.5: calibrated probability gate
    single_low_confidence_score: float = 5.0
    p_after_s_score: float = 10.0
    sp_interval_score: float = 5.0
    data_penalties: Dict[str, float] = field(default_factory=lambda: {
        "channel_missing": 1.5,
        "channel_multi_missing": 3.0,
        "gap_severe": 2.8,
        "gap_moderate": 1.4,
        "clipping_severe": 0.0,
        "clipping_moderate": 0.0,
        "strong_noise": 1.3,
        "moderate_signal": 1.0,
    })
    config_version: str = "calibrated_v1.0"
    config_hash: str = ""
    parent_config: str = ""


# ═══════════════════════════════════════
# 证据对象
# ═══════════════════════════════════════

@dataclass
class EvidenceScore:
    score: float = 0.0
    reasons: List[str] = field(default_factory=list)
    status: str = "AVAILABLE"
    source: str = ""
    version: str = "heuristic_v0.1"


@dataclass
class ModelSuitability:
    model_name: str = ""
    eligible: bool = False
    suitability_level: str = "UNKNOWN"
    penalty: float = 0.0
    reasons: List[str] = field(default_factory=list)
    profile_source: str = "REAL_ADAPTER"


@dataclass
class SingleModelEvidence:
    model_name: str = ""
    phase: str = ""
    score: Optional[float] = None
    reasons: List[str] = field(default_factory=list)
    status: str = "AVAILABLE"


@dataclass
class PhysicsCheck:
    target_type: str = ""       # MODEL / FINAL_PAIR
    target_id: str = ""
    status: str = "PASS"        # PASS / FAIL / INSUFFICIENT
    hard_fail: bool = False
    score: float = 0.0
    reasons: List[str] = field(default_factory=list)


@dataclass
class ConsensusResult:
    phase: str = ""
    status: str = "INSUFFICIENT"
    eligible_models: List[str] = field(default_factory=list)
    inlier_models: List[str] = field(default_factory=list)
    outlier_models: List[str] = field(default_factory=list)
    missing_models: List[str] = field(default_factory=list)
    center_time_s: float = -1
    spread_s: float = -1
    score: float = 0.0
    reasons: List[str] = field(default_factory=list)
    version: str = "heuristic_v0.1"


@dataclass
class FusedPickCandidate:
    phase: str = ""
    fusion_allowed: bool = False
    fused_time_s: float = -1
    contributors: List[str] = field(default_factory=list)
    excluded_models: List[str] = field(default_factory=list)
    spread_s: float = -1
    fusion_method: str = "MEDIAN_INLIERS"
    threshold_version: str = "heuristic_v0.1"
    reasons: List[str] = field(default_factory=list)


@dataclass
class ModelAssessment:
    model_name: str = ""
    eligible: bool = False
    suitability_level: str = "UNKNOWN"
    model_risk_score: float = 0.0
    hard_fail: bool = False
    consensus_role: str = ""
    reasons: List[str] = field(default_factory=list)
    selection_supported: bool = False


# ═══════════════════════════════════════
# 最终决策
# ═══════════════════════════════════════

@dataclass
class PhaseDecision:
    phase: str = ""
    action: str = "ABSTAIN"
    selected_model: Optional[str] = None
    selected_time_s: float = -1
    fused_pick: Optional[FusedPickCandidate] = None
    rejected_models: List[str] = field(default_factory=list)
    risk_score: float = 0.0
    risk_level: str = "LOW"
    reason_codes: List[str] = field(default_factory=list)


@dataclass
class ReliabilityResult:
    sample_id: str = ""
    evidence_status: str = "INCOMPLETE"
    overall_risk_score: float = 0.0
    overall_risk_level: str = "LOW"
    phase_decisions: Dict[str, PhaseDecision] = field(default_factory=dict)
    model_assessments: List[ModelAssessment] = field(default_factory=list)
    final_pair_status: str = "PARTIAL"
    evidence_breakdown: Dict[str, Any] = field(default_factory=dict)
    reason_codes: List[str] = field(default_factory=list)
    config_version: str = "heuristic_v0.1"
    config_hash: str = ""
    parent_config: str = ""
    data_source: str = ""

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(asdict(self), indent=indent, ensure_ascii=False)


# ═══════════════════════════════════════
# 工具
# ═══════════════════════════════════════

def risk_level(score: float) -> str:
    if score <= 30: return "LOW"
    if score <= 60: return "MEDIUM"
    return "HIGH"


# ═══════════════ Demo 配置 — 仅测试用，非真实模型参数 ═══════════════
# 等数据组交付真实 ModelProfile 后替换。不得用于性能结论。

DEMO_MODEL_PROFILES = {
    "PhaseNet": ModelProfile(
        model_name="PhaseNet",
        model_version="original",
        model_family="generic",
        required_channels=["Z", "N", "E"],
        preferred_channels=[],
        accepted_sampling_rates_hz=[100.0],
        profile_source="DEMO_PROFILE",
    ),
    "PickBlue": ModelProfile(
        model_name="PickBlue",
        model_version="demo",
        model_family="obs_specialized",
        required_channels=["Z", "N", "E", "H"],
        preferred_channels=[],
        accepted_sampling_rates_hz=[100.0],
        profile_source="DEMO_PROFILE",
    ),
}

DEMO_CONFIG = TrustConfig(
    primary_model="PhaseNet",
    fusion_enabled=True,
    config_version="heuristic_v0.1",
)
