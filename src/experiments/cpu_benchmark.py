"""Measure model and Trust Layer latency on one reproducible OBS sample."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time
from pathlib import Path

import torch

from src.experiments.seisbench_noise import (
    DATA_DIR,
    OUTPUT_DIR,
    infer_models,
    load_dataset,
    load_models,
    profiles,
    select_sample_indices,
    waveform_to_stream,
)
from src.trust_engine.pipeline import run_pipeline
from src.trust_engine.schema import AdapterStatus, QualityReport, SampleMetadata


def model_size_bytes(model) -> int:
    return sum(value.numel() * value.element_size() for value in model.state_dict().values())


def benchmark(data_dir: Path, repeats: int = 3):
    dataset = load_dataset(data_dir)
    index = select_sample_indices(dataset, 1)[0]
    waveform, metadata = dataset.get_sample(index, sampling_rate=100.0)
    stream = waveform_to_stream(waveform, metadata)

    load_started = time.perf_counter()
    models, device = load_models("cpu")
    load_seconds = time.perf_counter() - load_started
    model_results = []
    all_predictions = []
    for name, model in models.items():
        model.classify(stream, batch_size=64)  # warm-up
        timings = []
        for _ in range(repeats):
            started = time.perf_counter()
            model.classify(stream, batch_size=64)
            timings.append(time.perf_counter() - started)
        all_predictions.extend(infer_models({name: model}, stream, str(metadata["trace_name_original"])))
        model_results.append(
            {
                "model": name,
                "parameters": sum(parameter.numel() for parameter in model.parameters()),
                "state_dict_mib": model_size_bytes(model) / (1024**2),
                "median_inference_s": statistics.median(timings),
                "min_inference_s": min(timings),
                "repeats": repeats,
            }
        )

    adapters = [AdapterStatus(name, True, True, True) for name in models]
    pipeline_inputs = dict(
        metadata=SampleMetadata(
            sample_id=str(metadata["trace_name_original"]),
            window_id=str(metadata["trace_name_original"]),
            duration_s=waveform.shape[1] / 100.0,
            data_source="SEISBENCH_OBS",
            preprocessing_version="seisbench_v0.12",
        ),
        quality=QualityReport(available_channels=["Z", "N", "E", "H"], sampling_rate_hz=100.0, snr_db=20.0),
        profiles=profiles(),
        predictions=all_predictions,
        adapter_statuses=adapters,
    )
    trust_timings = []
    for _ in range(100):
        started = time.perf_counter()
        run_pipeline(**pipeline_inputs)
        trust_timings.append(time.perf_counter() - started)
    return {
        "scope": "single public OBS waveform; CPU; warm cache; batch size 64",
        "sample_id": str(metadata["trace_name_original"]),
        "waveform_duration_s": waveform.shape[1] / 100.0,
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "torch": torch.__version__,
            "device": device,
        },
        "combined_model_load_s": load_seconds,
        "models": model_results,
        "trust_layer_median_ms": statistics.median(trust_timings) * 1000,
        "trust_layer_p95_ms": sorted(trust_timings)[94] * 1000,
        "limitations": [
            "This is a local engineering measurement, not a cross-device benchmark.",
            "Model storage uses state-dict tensor bytes and excludes Python/runtime dependencies.",
            "No quantization or pruning claim is made.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR / "cpu_benchmark.json")
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    result = benchmark(args.data_dir, max(1, args.repeats))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
