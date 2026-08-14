"""Run the P3 noise experiment on public SeisBench OBS waveforms.

The experiment uses 20 deterministic samples from the official ``test`` split
of OBS chunk 201805. Every selected trace has four components and labelled P/S
arrivals. Label provenance (manual/automatic) is retained in the output.

Noise levels are the original waveform (L0) and additive Gaussian noise at
10 dB (L1), 5 dB (L2), and 2 dB (L3). The same trace/level noise realization is
shared by all models. The random seed is derived from the sample ID and level.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

from src.trust_engine.pipeline import run_pipeline
from src.trust_engine.schema import (
    AdapterStatus,
    ModelPrediction,
    ModelProfile,
    QualityReport,
    SampleMetadata,
)


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "seisbench" / "obs"
OUTPUT_DIR = ROOT / "docs" / "experiments"
CHUNK = "201805"
SAMPLE_COUNT = 20
NOISE_LEVELS: Dict[str, Optional[float]] = {
    "L0": None,
    "L1": 10.0,
    "L2": 5.0,
    "L3": 2.0,
}
MODELS = ("PhaseNet", "PickBlue", "OBSTransformer")
METHODS = ("single_model", "highest_confidence", "trust_layer")
METHOD_LABELS = {
    "single_model": "Single model",
    "highest_confidence": "Highest confidence",
    "trust_layer": "Trust Layer",
}
P_TOLERANCE_S = 0.5
S_TOLERANCE_S = 1.0


def stable_seed(sample_id: str, level: str) -> int:
    digest = hashlib.sha256(f"{sample_id}:{level}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % (2**32)


def add_noise(waveform: np.ndarray, level: str, sample_id: str) -> np.ndarray:
    """Add deterministic Gaussian noise at the requested signal/noise ratio."""
    target_snr_db = NOISE_LEVELS[level]
    output = np.asarray(waveform, dtype=np.float32).copy()
    if target_snr_db is None:
        return output

    rng = np.random.default_rng(stable_seed(sample_id, level))
    noise = rng.standard_normal(output.shape).astype(np.float32)
    for channel in range(output.shape[0]):
        signal_rms = float(np.sqrt(np.mean(np.square(output[channel]))))
        noise_rms = float(np.sqrt(np.mean(np.square(noise[channel]))))
        if signal_rms == 0.0 or noise_rms == 0.0:
            continue
        target_noise_rms = signal_rms / (10 ** (target_snr_db / 20.0))
        output[channel] += noise[channel] * (target_noise_rms / noise_rms)
    return output


def load_dataset(data_dir: Path):
    import seisbench.data as sbd

    metadata = data_dir / f"metadata{CHUNK}.csv"
    waveforms = data_dir / f"waveforms{CHUNK}.hdf5"
    if not metadata.is_file() or not waveforms.is_file():
        raise FileNotFoundError(
            "OBS chunk 201805 is missing. Run scripts/download_obs_201805.sh first."
        )
    return sbd.WaveformDataset(
        data_dir,
        chunks=[CHUNK],
        component_order="Z12H",
        dimension_order="NCW",
        missing_components="pad",
        cache="trace",
    )


def select_sample_indices(dataset, count: int = SAMPLE_COUNT) -> List[int]:
    metadata = dataset.metadata
    mask = (
        metadata["split"].eq("test")
        & metadata["trace_component_order"].eq("Z12H")
        & metadata["trace_p_arrival_sample"].notna()
        & metadata["trace_s_arrival_sample"].notna()
        & ~metadata["trace_has_spikes"].fillna(False).astype(bool)
    )
    candidates = metadata.loc[mask].sort_values(["source_id", "station_code", "trace_name"])
    if len(candidates) < count:
        raise ValueError(f"Need {count} eligible test samples; found {len(candidates)}")
    return candidates.index[:count].tolist()


def load_models(device: str):
    import seisbench
    import seisbench.models as sbm
    import torch

    seisbench.use_backup_repository()
    loaded = {
        "PhaseNet": sbm.PhaseNet.from_pretrained("geofon"),
        "PickBlue": sbm.PickBlue(base="phasenet"),
        "OBSTransformer": sbm.OBSTransformer.from_pretrained("obst2024"),
    }
    if device == "auto":
        device = "mps" if torch.backends.mps.is_available() else "cpu"
    if device == "mps":
        try:
            torch.empty(1, device="mps")
        except RuntimeError as exc:
            print(f"MPS unavailable at runtime ({exc}); falling back to CPU.", flush=True)
            device = "cpu"
    for model in loaded.values():
        model.eval()
        model.to(device)
    return loaded, device


def waveform_to_stream(waveform: np.ndarray, metadata: Dict[str, Any]):
    from obspy import Stream, Trace, UTCDateTime

    start = UTCDateTime(str(metadata["trace_start_time"]))
    sampling_rate = float(metadata["trace_sampling_rate_hz"])
    channels = ("HHZ", "HH1", "HH2", "HHH")
    traces = []
    for channel, values in zip(channels, waveform):
        trace = Trace(np.asarray(values, dtype=np.float32))
        trace.stats.network = str(metadata.get("station_network_code") or "XX")
        trace.stats.station = str(metadata.get("station_code") or "OBS")
        trace.stats.location = ""
        trace.stats.channel = channel
        trace.stats.starttime = start
        trace.stats.sampling_rate = sampling_rate
        traces.append(trace)
    return Stream(traces=traces)


def best_phase_pick(output, phase: str, start_time) -> Optional[Dict[str, float]]:
    candidates = [pick for pick in getattr(output, "picks", []) if pick.phase.upper() == phase]
    if not candidates:
        return None
    selected = max(candidates, key=lambda pick: float(pick.peak_value or 0.0))
    return {
        "time_s": float(selected.peak_time - start_time),
        "score": float(selected.peak_value or 0.0),
    }


def infer_models(models, stream, sample_id: str) -> List[ModelPrediction]:
    predictions: List[ModelPrediction] = []
    for name, model in models.items():
        output = model.classify(stream, batch_size=64)
        for phase in ("P", "S"):
            selected = best_phase_pick(output, phase, stream[0].stats.starttime)
            if selected is None:
                continue
            predictions.append(
                ModelPrediction(
                    sample_id=sample_id,
                    window_id=sample_id,
                    model_name=name,
                    model_version={
                        "PhaseNet": "geofon",
                        "PickBlue": "obs-phasenet",
                        "OBSTransformer": "obst2024",
                    }[name],
                    phase=phase,
                    time_s=selected["time_s"],
                    score=selected["score"],
                    adapter_status="OK",
                    preprocessing_version="seisbench_v0.12",
                    prediction_source="REAL_MODEL",
                )
            )
    return predictions


def profiles() -> List[ModelProfile]:
    common = dict(
        accepted_sampling_rates_hz=[100.0],
        resampling_supported=True,
        required_preprocessing_version="seisbench_v0.12",
        validation_domain_known=True,
        profile_source="SEISBENCH_PRETRAINED",
    )
    return [
        ModelProfile(model_name="PhaseNet", model_version="geofon", model_family="phasenet_land", required_channels=["Z", "N", "E"], **common),
        ModelProfile(model_name="PickBlue", model_version="obs-phasenet", model_family="phasenet_obs", required_channels=["Z", "N", "E", "H"], **common),
        ModelProfile(model_name="OBSTransformer", model_version="obst2024", model_family="eqtransformer_obs", required_channels=["Z", "N", "E"], **common),
    ]


def truth_pair(metadata: Dict[str, Any]) -> Dict[str, float]:
    sampling_rate = float(metadata["trace_sampling_rate_hz"])
    return {
        "P": float(metadata["trace_p_arrival_sample"]) / sampling_rate,
        "S": float(metadata["trace_s_arrival_sample"]) / sampling_rate,
    }


def pair_correct(pair: Dict[str, Optional[float]], truth: Dict[str, float]) -> bool:
    return (
        pair.get("P") is not None
        and pair.get("S") is not None
        and abs(float(pair["P"]) - truth["P"]) <= P_TOLERANCE_S
        and abs(float(pair["S"]) - truth["S"]) <= S_TOLERANCE_S
    )


def method_outcome(
    method: str,
    predictions: List[ModelPrediction],
    result,
    truth: Dict[str, float],
) -> Dict[str, Any]:
    pair: Dict[str, Optional[float]] = {"P": None, "S": None}
    abstained = False
    if method == "single_model":
        for phase in ("P", "S"):
            candidates = [
                p
                for p in predictions
                if p.model_name == "OBSTransformer" and p.phase == phase
            ]
            if candidates:
                pair[phase] = max(candidates, key=lambda p: p.score or 0).time_s
        abstained = any(pair[phase] is None for phase in ("P", "S"))
    elif method == "highest_confidence":
        for phase in ("P", "S"):
            candidates = [p for p in predictions if p.phase == phase]
            if candidates:
                pair[phase] = max(candidates, key=lambda p: p.score or 0).time_s
        abstained = any(pair[phase] is None for phase in ("P", "S"))
    else:
        for phase in ("P", "S"):
            decision = result.phase_decisions[phase]
            if decision.action == "ABSTAIN":
                abstained = True
            else:
                pair[phase] = decision.selected_time_s
        abstained = abstained or any(pair[phase] is None or pair[phase] < 0 for phase in ("P", "S"))

    correct = pair_correct(pair, truth) if not abstained else False
    unsafe = not abstained and not correct
    return {
        "p_time_s": pair["P"],
        "s_time_s": pair["S"],
        "abstained": int(abstained),
        "correct": int(correct),
        "unsafe_error": int(unsafe),
        # Safe handling means the method either returned a correct pair or blocked an unsafe pair.
        "intercepted_or_correct": int(not unsafe),
    }


def write_rows(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def summarize(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for level in NOISE_LEVELS:
        for method in METHODS:
            subset = [row for row in records if row["noise_level"] == level and row["method"] == method]
            total = len(subset)
            emitted = [row for row in subset if not int(row["abstained"])]
            unsafe = sum(int(row["unsafe_error"]) for row in subset)
            correct = sum(int(row["correct"]) for row in subset)
            safe = total - unsafe
            safe_low, safe_high = wilson_interval(safe, total)
            p_errors = [
                abs(float(row["p_time_s"]) - float(row["truth_p_s"]))
                for row in emitted
                if row["p_time_s"] not in (None, "")
            ]
            s_errors = [
                abs(float(row["s_time_s"]) - float(row["truth_s_s"]))
                for row in emitted
                if row["s_time_s"] not in (None, "")
            ]
            rows.append(
                {
                    "noise_level": level,
                    "method": method,
                    "total": total,
                    "correct": correct,
                    "abstained": sum(int(row["abstained"]) for row in subset),
                    "unsafe_errors": unsafe,
                    "accuracy_rate": correct / total,
                    "coverage_rate": len(emitted) / total,
                    "selective_accuracy": correct / len(emitted) if emitted else 0.0,
                    "abstention_rate": sum(int(row["abstained"]) for row in subset) / total,
                    "unsafe_output_rate": unsafe / total,
                    "safe_handling_rate": safe / total,
                    "safe_handling_ci95_low": safe_low,
                    "safe_handling_ci95_high": safe_high,
                    "p_mae_s_on_emitted": float(np.mean(p_errors)) if p_errors else "",
                    "s_mae_s_on_emitted": float(np.mean(s_errors)) if s_errors else "",
                    # Backward-compatible column retained for the P3 task card.
                    "interception_rate": safe / total,
                }
            )
    return rows


def wilson_interval(successes: int, total: int, z: float = 1.96) -> Tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    if total <= 0:
        return 0.0, 0.0
    proportion = successes / total
    denominator = 1 + z**2 / total
    center = (proportion + z**2 / (2 * total)) / denominator
    half_width = (
        z
        * np.sqrt(
            proportion * (1 - proportion) / total
            + z**2 / (4 * total**2)
        )
        / denominator
    )
    return center - half_width, center + half_width


def plot(summary: List[Dict[str, Any]], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"single_model": "#64748b", "highest_confidence": "#f59e0b", "trust_layer": "#0f766e"}
    markers = {"single_model": "o", "highest_confidence": "s", "trust_layer": "D"}
    figure, axis = plt.subplots(figsize=(9, 5.5))
    for method in METHODS:
        subset = [row for row in summary if row["method"] == method]
        values = [float(row["interception_rate"]) * 100 for row in subset]
        axis.plot(NOISE_LEVELS.keys(), values, label=METHOD_LABELS[method], color=colors[method], marker=markers[method], linewidth=2.5)
        for level, value in zip(NOISE_LEVELS, values):
            axis.annotate(f"{value:.0f}%", (level, value), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=8)
    axis.set_title("OBS Noise Robustness: Unsafe-output Interception")
    axis.set_xlabel("Noise level (L0 original; L1/L2/L3 = 10/5/2 dB)")
    axis.set_ylabel("Correct or safely abstained (%)")
    axis.set_ylim(0, 105)
    axis.grid(axis="y", alpha=0.25)
    axis.legend(loc="lower left")
    figure.tight_layout()
    figure.savefig(path, dpi=200)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--count", type=int, default=SAMPLE_COUNT)
    parser.add_argument("--device", choices=("auto", "cpu", "mps"), default="auto")
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Recompute summary and figure from existing per-sample records.",
    )
    args = parser.parse_args()

    if args.summary_only:
        records_path = args.output_dir / "noise_records_seisbench.csv"
        with records_path.open(encoding="utf-8", newline="") as handle:
            records = list(csv.DictReader(handle))
        summary = summarize(records)
        write_rows(args.output_dir / "noise_summary_seisbench.csv", summary)
        plot(summary, args.output_dir / "noise_curve.png")
        print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
        return

    dataset = load_dataset(args.data_dir)
    sample_indices = select_sample_indices(dataset, args.count)
    models, device = load_models(args.device)
    model_profiles = profiles()
    adapters = [AdapterStatus(name, True, True, True) for name in MODELS]
    records: List[Dict[str, Any]] = []
    raw_predictions: List[Dict[str, Any]] = []

    print(f"Selected {len(sample_indices)} OBS test samples; device={device}", flush=True)
    for position, index in enumerate(sample_indices, 1):
        waveform, metadata = dataset.get_sample(index, sampling_rate=100.0)
        sample_id = str(metadata["trace_name_original"])
        truth = truth_pair(metadata)
        for level, snr_db in NOISE_LEVELS.items():
            noisy = add_noise(waveform, level, sample_id)
            stream = waveform_to_stream(noisy, metadata)
            predictions = infer_models(models, stream, sample_id)
            raw_predictions.extend(
                {
                    "sample_id": sample_id,
                    "noise_level": level,
                    **asdict(prediction),
                }
                for prediction in predictions
            )
            quality = QualityReport(
                available_channels=["Z", "N", "E", "H"],
                missing_channels=[],
                required_channels_for_task=["Z", "N", "E"],
                sampling_rate_hz=100.0,
                snr_db=20.0 if snr_db is None else snr_db,
                source="SEISBENCH_OBS_PLUS_SYNTHETIC_NOISE",
            )
            result = run_pipeline(
                metadata=SampleMetadata(
                    sample_id=sample_id,
                    window_id=sample_id,
                    duration_s=noisy.shape[1] / 100.0,
                    data_source="SEISBENCH_OBS",
                    preprocessing_version="seisbench_v0.12",
                ),
                quality=quality,
                profiles=model_profiles,
                predictions=predictions,
                adapter_statuses=adapters,
            )
            for method in METHODS:
                outcome = method_outcome(method, predictions, result, truth)
                records.append(
                    {
                        "sample_id": sample_id,
                        "noise_level": level,
                        "target_snr_db": "original" if snr_db is None else snr_db,
                        "method": method,
                        "truth_p_s": truth["P"],
                        "truth_s_s": truth["S"],
                        "p_label_status": metadata.get("trace_p_status"),
                        "s_label_status": metadata.get("trace_s_status"),
                        **outcome,
                    }
                )
        print(f"[{position}/{len(sample_indices)}] {sample_id}", flush=True)

    summary = summarize(records)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_rows(args.output_dir / "noise_records_seisbench.csv", records)
    write_rows(args.output_dir / "noise_summary_seisbench.csv", summary)
    with (args.output_dir / "noise_predictions_seisbench.json").open("w", encoding="utf-8") as handle:
        json.dump(raw_predictions, handle, ensure_ascii=False, indent=2)
    plot(summary, args.output_dir / "noise_curve.png")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
