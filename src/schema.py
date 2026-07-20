"""
统一 Schema — Trust Engine 全组共用数据结构

版本: v1.0
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
import json


# ═══════════════════════════════════════════════════════════
# 波形元信息
# ═══════════════════════════════════════════════════════════

@dataclass
class WaveformInfo:
    station: str = ""
    network: str = ""
    channels: List[str] = field(default_factory=list)
    sampling_rate: float = 100.0
    start_time: str = ""
    duration_s: float = 60.0


# ═══════════════════════════════════════════════════════════
# 数据质量报告 (数据与模型组产出)
# ═══════════════════════════════════════════════════════════

@dataclass
class QualityReport:
    missing_channels: List[str] = field(default_factory=list)
    gap_ratio: float = 0.0
    clipping_ratio: float = 0.0
    snr_db: float = 20.0
    sampling_rate_ok: bool = True

    def summary(self) -> str:
        issues = []
        if self.missing_channels:
            issues.append(f"缺{self.missing_channels}通道")
        if self.gap_ratio > 0.05:
            issues.append(f"断点率{self.gap_ratio:.1%}")
        if self.clipping_ratio > 0.05:
            issues.append(f"削波率{self.clipping_ratio:.1%}")
        if self.snr_db < 3.0:
            issues.append(f"低SNR({self.snr_db:.1f}dB)")
        return "数据质量良好" if not issues else "质量问题: " + ", ".join(issues)


# ═══════════════════════════════════════════════════════════
# 模型预测 (数据与模型组产出)
# ═══════════════════════════════════════════════════════════

@dataclass
class ModelPrediction:
    model: str
    model_version: str = "unknown"
    phase: str = ""          # "P" | "S"
    time_s: float = -1       # 窗口相对秒, -1 = 未检出
    score: float = 0.0       # 模型置信度 0-1
    window_id: str = ""


# ═══════════════════════════════════════════════════════════
# 四类证据
# ═══════════════════════════════════════════════════════════

@dataclass
class Evidence:
    data_score: float = 0.0
    data_reasons: List[str] = field(default_factory=list)
    single_model_score: float = 0.0
    single_model_reasons: List[str] = field(default_factory=list)
    multi_model_score: float = 0.0
    multi_model_reasons: List[str] = field(default_factory=list)
    physics_score: float = 0.0
    physics_reasons: List[str] = field(default_factory=list)

    @property
    def total_score(self) -> float:
        return self.data_score + self.single_model_score + \
               self.multi_model_score + self.physics_score

    @property
    def all_reasons(self) -> List[str]:
        return (self.data_reasons + self.single_model_reasons +
                self.multi_model_reasons + self.physics_reasons)


# ═══════════════════════════════════════════════════════════
# 可靠性决策结果 (Trust Engine 最终产出)
# ═══════════════════════════════════════════════════════════

@dataclass
class ReliabilityResult:
    risk_score: float = 0.0
    risk_level: str = "LOW"          # LOW | MEDIUM | HIGH
    action: str = "ACCEPT"           # ACCEPT | ROUTE | ABSTAIN
    reason_codes: List[str] = field(default_factory=list)
    evidence_summary: str = ""


# ═══════════════════════════════════════════════════════════
# 单个样本完整分析结果 (顶层)
# ═══════════════════════════════════════════════════════════

@dataclass
class SampleAnalysis:
    sample_id: str
    waveform_info: WaveformInfo = field(default_factory=WaveformInfo)
    quality: QualityReport = field(default_factory=QualityReport)
    predictions: List[ModelPrediction] = field(default_factory=list)
    reliability: Optional[ReliabilityResult] = None

    def to_json(self, indent: int = 2) -> str:
        d = {
            "sample_id": self.sample_id,
            "waveform_info": asdict(self.waveform_info),
            "quality": asdict(self.quality),
            "predictions": [asdict(p) for p in self.predictions],
        }
        if self.reliability:
            d["reliability"] = asdict(self.reliability)
        return json.dumps(d, indent=indent, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════

def risk_level(score: float) -> str:
    if score <= 30:
        return "LOW"
    if score <= 60:
        return "MEDIUM"
    return "HIGH"


def action_for(level: str) -> str:
    return {"LOW": "ACCEPT", "MEDIUM": "ROUTE", "HIGH": "ABSTAIN"}[level]


def route(risk_score: float) -> tuple:
    """分数 → (等级, 动作)"""
    level = risk_level(risk_score)
    action = action_for(level)
    return level, action
