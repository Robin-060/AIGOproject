"""
数据层 → Trust Engine 桥接脚本
==============================
读取 data_layer.py 输出的 JSON，转换为 Trust Engine 所需的数据对象并调用流水线。

用法:
    python data_layer.py --output data_out.json          # 先跑数据层
    python feed_trust_engine.py data_out.json             # 再喂入调度层

或者在项目根目录:
    cd D:/Uni/AIGO/AIGOproject-dev-trust-engine/AIGOproject-dev-trust-engine
    python -c "
import sys, json
sys.path.insert(0, '../../AIGOproject-Model/AIGOproject-Model')
from feed_trust_engine import run
result = run('../../AIGOproject-Model/AIGOproject-Model/data_out.json')
print(result.to_json())
"
"""

import sys, json
from pathlib import Path

# 将 Trust Engine 路径加入 sys.path (相对于本文件)
TRUST_ENGINE_ROOT = Path(__file__).resolve().parent.parent / "AIGOproject-dev-trust-engine" / "AIGOproject-dev-trust-engine"
if str(TRUST_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(TRUST_ENGINE_ROOT))

from src.trust_engine.schema import (
    SampleMetadata,
    QualityReport,
    ModelProfile,
    ModelPrediction,
    TrustConfig,
    AdapterStatus,
    DEMO_CONFIG,
)
from src.trust_engine.pipeline import analyze_sample


def load_data_layer_json(json_path: str) -> dict:
    """读取 data_layer.py 输出的 JSON 文件"""
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def convert_to_trust_engine(data: dict):
    """
    将数据层 JSON (dict) 转换为 Trust Engine 期望的 dataclass 对象。

    返回: (SampleMetadata, QualityReport, List[ModelProfile],
           List[ModelPrediction], List[AdapterStatus])
    """
    # SampleMetadata
    sm = data["sample_metadata"]
    metadata = SampleMetadata(
        sample_id=sm["sample_id"],
        deployment_id=sm.get("deployment_id", ""),
        station_id=sm.get("station_id", ""),
        window_id=sm.get("window_id", ""),
        start_time_utc=sm.get("start_time_utc", ""),
        duration_s=sm.get("duration_s", 60.0),
        canonical_time_basis=sm.get("canonical_time_basis", "WINDOW_SECONDS"),
        expected_event=sm.get("expected_event"),
        data_source=sm.get("data_source", "REAL"),
        preprocessing_version=sm.get("preprocessing_version", ""),
        resampling_applied=sm.get("resampling_applied", False),
        resampling_trace_id=sm.get("resampling_trace_id"),
    )

    # QualityReport
    qr = data["quality_report"]
    quality = QualityReport(
        available_channels=qr["available_channels"],
        missing_channels=qr.get("missing_channels", []),
        required_channels_for_task=qr.get("required_channels_for_task", ["Z", "N", "E"]),
        sampling_rate_hz=qr.get("sampling_rate_hz", 100.0),
        gap_ratio=qr.get("gap_ratio", 0.0),
        clipping_ratio=qr.get("clipping_ratio", 0.0),
        snr_db=qr.get("snr_db"),
        metric_version=qr.get("metric_version", "v0.1"),
        source=qr.get("source", "REAL_CALCULATION"),
    )

    # ModelProfile[]
    profiles = []
    for name, mp in data["model_profiles"].items():
        profiles.append(ModelProfile(
            model_name=mp["model_name"],
            model_version=mp.get("model_version", "unknown"),
            model_family=mp.get("model_family", ""),
            required_channels=mp.get("required_channels", []),
            preferred_channels=mp.get("preferred_channels", []),
            accepted_sampling_rates_hz=mp.get("accepted_sampling_rates_hz", []),
            resampling_supported=mp.get("resampling_supported", False),
            required_preprocessing_version=mp.get("required_preprocessing_version", ""),
            validation_profile_id=mp.get("validation_profile_id"),
            validation_domain_known=mp.get("validation_domain_known", True),
            profile_source=mp.get("profile_source", "REAL_ADAPTER"),
        ))

    # ModelPrediction[]
    predictions = []
    for pred in data["model_predictions"]:
        predictions.append(ModelPrediction(
            sample_id=pred.get("sample_id", ""),
            window_id=pred.get("window_id", ""),
            model_name=pred.get("model_name", ""),
            model_version=pred.get("model_version", "unknown"),
            phase=pred.get("phase", ""),
            time_s=pred.get("time_s", -1),
            pick_time_utc=pred.get("pick_time_utc"),
            source_time_basis=pred.get("source_time_basis", "WINDOW_SECONDS"),
            score=pred.get("score"),
            adapter_status=pred.get("adapter_status", "OK"),
            preprocessing_version=pred.get("preprocessing_version", ""),
            prediction_source=pred.get("prediction_source", "REAL_MODEL"),
        ))

    # AdapterStatus[]
    adapter_statuses = []
    for adp in data.get("adapter_statuses", []):
        adapter_statuses.append(AdapterStatus(
            model_name=adp["model_name"],
            loaded=adp.get("loaded", False),
            run_succeeded=adp.get("run_succeeded", False),
            output_comparable=adp.get("output_comparable", False),
        ))

    return metadata, quality, profiles, predictions, adapter_statuses


def run(json_path: str):
    """
    完整流程: 加载数据层 JSON → 转换 → 喂入 Trust Engine → 返回 ReliabilityResult
    """
    data = load_data_layer_json(json_path)
    metadata, quality, profiles, predictions, adapter_statuses = convert_to_trust_engine(data)

    print("=" * 60)
    print("数据层 → Trust Engine 桥接")
    print("=" * 60)
    print(f"Sample:  {metadata.sample_id}")
    print(f"Station: {metadata.station_id}")
    print(f"Quality: SNR={quality.snr_db}dB, gap={quality.gap_ratio:.2%}, "
          f"clip={quality.clipping_ratio:.2%}")
    print(f"Models:  {[p.model_name for p in profiles]}")
    print(f"Picks:   {len(predictions)} predictions from {len(set(p.model_name for p in predictions))} models")
    print()

    # ── 调用 Trust Engine ──
    config = DEMO_CONFIG

    result = analyze_sample(
        metadata=metadata,
        quality=quality,
        model_profiles=profiles,
        predictions=predictions,
        config=config,
        # P1/P2/P3 证据留空 — 由 evaluate_reliability 内部处理
    )

    print("=" * 60)
    print("Trust Engine 结果")
    print("=" * 60)
    print(f"Overall risk: {result.overall_risk_score} ({result.overall_risk_level})")
    print(f"Evidence:     {result.evidence_status}")
    print(f"Final pair:   {result.final_pair_status}")
    print(f"Reason codes: {result.reason_codes}")

    for phase, decision in result.phase_decisions.items():
        print(f"  {phase}-phase: action={decision.action}, risk={decision.risk_score}, "
              f"reasons={decision.reason_codes}")

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python feed_trust_engine.py <data_layer_output.json>")
        print("示例: python feed_trust_engine.py data_out.json")
        sys.exit(1)

    run(sys.argv[1])
