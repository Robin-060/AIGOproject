"""
Demo 内置示例升级为四模型真实数据 — 同名覆盖 example_1/example_2

- 示例 1: XO.LA39..HH.2018.06.23.22.50.05 (四模型共识 → FUSE)
- 示例 2: XO.LA39..HH.2018.06.01.18.41.15 (geofon S 严重分歧 → ABSTAIN)

JSON 四段式 (load_from_mapping 契约) + 配套波形 CSV (time_s,Z,N,E,H)
用法: python -m src.experiments.regenerate_examples
"""

import csv
import json
import os
import sys
from pathlib import Path

os.environ["SEISBENCH_CACHE_ROOT"] = "D:/seisbench_cache"
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import warnings  # noqa: E402
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
from seisbench.data import OBS  # noqa: E402

SAMPLES = {
    "example_1": ("XO.LA39..HH.2018.06.23.22.50.05", "201806"),
    "example_2": ("XO.LA39..HH.2018.06.01.18.41.15", "201806"),
}

PROFILES = {
    "PhaseNet": {
        "model_name": "PhaseNet", "model_version": "geofon_pretrained",
        "model_family": "generic_three_component",
        "required_channels": ["Z", "N", "E"], "preferred_channels": [],
        "accepted_sampling_rates_hz": [100.0], "resampling_supported": True,
        "required_preprocessing_version": "obs_raw_v1",
        "validation_profile_id": "phasenet_geofon_v1",
        "validation_domain_known": True, "profile_source": "REAL_ADAPTER",
    },
    "PickBlue": {
        "model_name": "PickBlue", "model_version": "obs_pretrained",
        "model_family": "obs_specialized",
        "required_channels": ["Z", "H"], "preferred_channels": ["N", "E"],
        "accepted_sampling_rates_hz": [100.0], "resampling_supported": True,
        "required_preprocessing_version": "obs_raw_v1",
        "validation_profile_id": "pickblue_obs_v1",
        "validation_domain_known": True, "profile_source": "REAL_ADAPTER",
    },
    "OBSTransformer": {
        "model_name": "OBSTransformer", "model_version": "obst2024",
        "model_family": "transformer_multicomponent",
        "required_channels": ["H"], "preferred_channels": ["Z", "N", "E"],
        "accepted_sampling_rates_hz": [100.0], "resampling_supported": True,
        "required_preprocessing_version": "obs_raw_v1",
        "validation_profile_id": "obst2024_v1",
        "validation_domain_known": True, "profile_source": "REAL_ADAPTER",
    },
    "EQTransformer": {
        "model_name": "EQTransformer", "model_version": "obs",
        "model_family": "transformer_multicomponent",
        "required_channels": ["Z", "N", "E"], "preferred_channels": [],
        "accepted_sampling_rates_hz": [100.0], "resampling_supported": True,
        "required_preprocessing_version": "obs_raw_v1",
        "validation_profile_id": "eqt_obs_v1",
        "validation_domain_known": True, "profile_source": "REAL_ADAPTER",
    },
}

ADAPTERS = [
    {"model_name": m, "loaded": True, "run_succeeded": True, "output_comparable": True}
    for m in PROFILES
]


def main():
    records = {r["sample_id"]: r
               for r in json.loads((ROOT / "data" / "batch_calibration"
                                    / "records_all_v2.json").read_text(encoding="utf-8"))}
    quality = {row["sample_id"]: row
               for row in csv.DictReader((ROOT / "data" / "quality_manifest.csv")
                                         .open(encoding="utf-8"))}

    for name, (sid, chunk) in SAMPLES.items():
        record = records[sid]
        q = quality[sid]

        # 四段式 JSON
        payload = {
            "sample_metadata": {
                "sample_id": sid, "deployment_id": "XO",
                "station_id": sid.split(".")[1], "window_id": f"chunk_{chunk}",
                "start_time_utc": "", "duration_s": 60.0,
                "canonical_time_basis": "WINDOW_SECONDS", "expected_event": True,
                "data_source": "REAL", "preprocessing_version": "obs_raw_v1",
                "resampling_applied": False, "resampling_trace_id": None,
            },
            "quality_report": {
                "available_channels": (q["available_channels"] or "Z|N|E|H").split("|"),
                "missing_channels": (q["missing_channels"] or "").split("|") if q["missing_channels"] else [],
                "required_channels_for_task": ["Z", "N", "E"],
                "sampling_rate_hz": 100.0,
                "gap_ratio": float(q["gap_ratio"] or 0),
                "clipping_ratio": float(q["clipping_ratio"] or 0),
                "snr_db": float(q["snr_db"]) if q["snr_db"] else None,
                "metric_version": "v0.1", "source": "REAL_CALCULATION",
            },
            "model_profiles": PROFILES,
            "model_predictions": [
                {
                    "sample_id": sid, "window_id": f"chunk_{chunk}",
                    "model_name": model, "model_version": PROFILES[model]["model_version"],
                    "phase": phase,
                    "time_s": (pred.get(f"{phase}_pick")
                               if pred.get(f"{phase}_pick") is not None else -1),
                    "pick_time_utc": None, "source_time_basis": "WINDOW_SECONDS",
                    "score": pred.get("confidence"),
                    "adapter_status": "OK", "preprocessing_version": "obs_raw_v1",
                    "prediction_source": "REAL_MODEL",
                }
                for model, pred in record["predictions"].items()
                for phase in ("P", "S")
            ],
            "adapter_statuses": ADAPTERS,
        }
        out_json = ROOT / "data" / "examples" / f"{name}.json"
        out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                            encoding="utf-8")

        # 配套波形 CSV (真实波形)
        obs = OBS(chunks=[chunk])
        meta = {n: i for i, n in enumerate(obs.metadata["trace_name_original"])}
        waveform, _ = obs.get_sample(meta[sid])
        npts = waveform.shape[1]
        frame = {"time_s": np.arange(npts) / 100.0}
        comps = [tr for tr in ("Z", "N", "E", "H")]
        order = {"Z": 0, "1": 1, "2": 2, "H": 3}
        comp_order = "Z12H"  # 示例样本均为 Z12H
        for i, ch in enumerate(comp_order):
            frame[{"Z": "Z", "1": "N", "2": "E", "H": "H"}[ch]] = waveform[i]
        with open(ROOT / "data" / "examples" / f"{name}.csv", "w", newline="",
                  encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["time_s", "Z", "N", "E", "H"])
            for row in zip(frame["time_s"], *[frame[c] for c in comps]):
                writer.writerow([f"{row[0]:.2f}"] + [f"{v:.6f}" for v in row[1:]])

        print(f"✓ {name}: JSON 4 模型 {len(payload['model_predictions'])} 行 + "
              f"波形 CSV {npts} 点 | SNR {q['snr_db']}dB | "
              f"缺道 {q['missing_channels'] or '无'}")


if __name__ == "__main__":
    main()
