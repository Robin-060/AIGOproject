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


@dataclass
class QualityReport:
    available_channels: List[str] = field(default_factory=list)
    missing_channels: List[str] = field(default_factory=list)
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


# ═══════════════════════════════════════
# 配置
# ═══════════════════════════════════════

@dataclass
class TrustConfig:
    primary_model: str = ""
    fusion_enabled: bool = True
    consensus_tolerance_p_s: float = 0.30
    consensus_tolerance_s_s: float = 0.50
    severe_disagreement_p_s: float = 1.00
    severe_disagreement_s_s: float = 2.00
    automatic_risk_threshold: float = 30.0
    risk_low_max: float = 30.0
    risk_medium_max: float = 60.0
    min_sp_s: float = 0.1
    max_sp_s: float = 60.0
    required_channels_for_task: List[str] = field(default_factory=lambda: ["Z", "N", "E"])
    config_version: str = "heuristic_v0.1"


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
    data_source: str = ""

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self, indent=indent, ensure_ascii=False, default=str)


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
