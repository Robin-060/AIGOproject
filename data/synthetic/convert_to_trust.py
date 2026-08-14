"""
真实模型预测 → Trust Engine ModelPrediction[] 转换

读取 data/synthetic/predictions.json（真实三模型推理结果），
转换为 Trust Engine 消费的标准格式。

用法:
    python data/synthetic/convert_to_trust.py
    → 输出 data/synthetic/trust_input.json

每样本结构 (可直接喂给 pipeline / grid_search / 消融实验):
    {
      "sample_id": "syn_0000",
      "label": "EARTHQUAKE",
      "noise_level": "L1",
      "ground_truth": {"P_time_s": "11.84", "S_time_s": "28.44"},
      "metadata": {SampleMetadata 字段},
      "quality": {QualityReport 字段},
      "predictions": [ModelPrediction 字段列表]
    }
"""

import json
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent
PREDICTIONS_PATH = OUT_DIR / "predictions.json"
OUTPUT_PATH = OUT_DIR / "trust_input.json"

# 模型 Profile (与数据组 MODEL_PROFILES 一致)
MODEL_VERSIONS = {
    "PhaseNet": "obs_pretrained",
    "PickBlue": "phasenet_base",
    "OBSTransformer": "obst2024",
}

# 仿真波形通道: 全部 4 通道 (Z/N/E/H)
CHANNELS = ["Z", "N", "E", "H"]


def convert_predictions(data: list) -> list:
    """把 predictions.json 转成 Trust Engine 输入格式"""
    results = []

    for sample in data:
        sample_id = sample["sample_id"]
        label = sample["label"]
        noise_level = sample["noise_level"]

        # 1. SampleMetadata
        metadata = {
            "sample_id": sample_id,
            "station_id": "SYN",
            "window_id": f"window_{sample_id}",
            "duration_s": 60.0,
            "canonical_time_basis": "WINDOW_SECONDS",
            "expected_event": (label == "EARTHQUAKE"),
            "data_source": "SYNTHETIC",
            "preprocessing_version": "synthetic_v1",
            "resampling_applied": False,
        }

        # 2. QualityReport (合成数据: 无断点无削波, SNR 按噪声等级映射)
        snr_map = {"L0": 20.0, "L1": 10.0, "L2": 5.0, "L3": 2.0}
        quality = {
            "available_channels": CHANNELS,
            "missing_channels": [],
            "required_channels_for_task": ["Z", "N", "E"],
            "sampling_rate_hz": 100.0,
            "gap_ratio": 0.0,
            "clipping_ratio": 0.0,
            "snr_db": snr_map.get(noise_level, 10.0),
            "metric_version": "v0.1",
            "source": "SYNTHETIC_FIXTURE",
        }

        # 3. ModelPrediction[]
        predictions = []
        for model_name, pred in sample["predictions"].items():
            for phase_key, phase_name in [("P_pick", "P"), ("S_pick", "S")]:
                time_s = pred.get(phase_key)
                if time_s is not None:
                    predictions.append({
                        "sample_id": sample_id,
                        "window_id": f"window_{sample_id}",
                        "model_name": model_name,
                        "model_version": MODEL_VERSIONS.get(model_name, "unknown"),
                        "phase": phase_name,
                        "time_s": float(time_s),
                        "pick_time_utc": None,
                        "source_time_basis": "WINDOW_SECONDS",
                        "score": pred.get("confidence"),
                        "adapter_status": "OK",
                        "preprocessing_version": "synthetic_v1",
                        "prediction_source": "REAL_MODEL",
                    })

        results.append({
            "sample_id": sample_id,
            "label": label,
            "noise_level": noise_level,
            "ground_truth": {
                "P_time_s": sample["ground_truth"]["P_time_s"],
                "S_time_s": sample["ground_truth"]["S_time_s"],
            },
            "metadata": metadata,
            "quality": quality,
            "predictions": predictions,
        })

    return results


def main():
    with open(PREDICTIONS_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)

    converted = convert_predictions(raw)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(converted, f, indent=2, ensure_ascii=False)

    # 统计
    n_with_preds = sum(1 for s in converted if s["predictions"])
    total_preds = sum(len(s["predictions"]) for s in converted)
    print(f"✅ 转换 {len(converted)} 个样本 → {OUTPUT_PATH}")
    print(f"   其中有模型检出的: {n_with_preds}/{len(converted)}")
    print(f"   总预测条数: {total_preds}")
    print()
    print("下游用法 (P2 消融/噪声实验):")
    print("  import json")
    print("  data = json.load(open('data/synthetic/trust_input.json', encoding='utf-8'))")
    print("  for sample in data:")
    print("      result = evaluate_reliability(")
    print("          metadata=SampleMetadata(**sample['metadata']),")
    print("          quality=QualityReport(**sample['quality']),")
    print("          predictions=[ModelPrediction(**p) for p in sample['predictions']],")
    print("          ...")
    print("      )")


if __name__ == "__main__":
    main()
