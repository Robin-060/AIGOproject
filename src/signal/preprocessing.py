"""Reproducible, CPU-friendly preprocessing for OBS waveforms."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

import numpy as np
from scipy import signal

from src.signal.io import WaveformBundle


@dataclass(frozen=True)
class PreprocessConfig:
    detrend: str = "linear"
    taper_fraction: float = 0.02
    bandpass_low_hz: float = 1.0
    bandpass_high_hz: float = 20.0
    notch_hz: float = 0.0
    normalize: str = "robust"
    version: str = "obs_preprocess_v1"


def _robust_rms(values: np.ndarray) -> float:
    scale = float(np.percentile(np.abs(values), 95))
    return scale if scale > np.finfo(np.float32).eps else 1.0


def quality_statistics(data: np.ndarray) -> Dict[str, float]:
    values = np.asarray(data, dtype=np.float64)
    peak = float(np.max(np.abs(values))) if values.size else 0.0
    clipping = float(np.mean(np.abs(values) >= peak * 0.999)) if peak else 0.0
    gaps = float(np.mean(~np.isfinite(values)))
    rms = float(np.sqrt(np.mean(np.square(np.nan_to_num(values)))))
    return {"rms": rms, "peak": peak, "gap_ratio": gaps, "clipping_ratio": clipping}


def preprocess_waveform(bundle: WaveformBundle, config: PreprocessConfig = PreprocessConfig()) -> Tuple[WaveformBundle, Dict[str, Any]]:
    data = np.nan_to_num(bundle.data.astype(np.float64), copy=True)
    before = quality_statistics(bundle.data)
    nyquist = bundle.sampling_rate_hz / 2.0
    if not 0 <= config.taper_fraction <= 0.5:
        raise ValueError("taper_fraction must be between 0 and 0.5")
    if not 0 < config.bandpass_low_hz < config.bandpass_high_hz < nyquist:
        raise ValueError("bandpass frequencies must satisfy 0 < low < high < Nyquist")

    if config.detrend in {"constant", "linear"}:
        data = signal.detrend(data, axis=-1, type=config.detrend)
    elif config.detrend != "none":
        raise ValueError("detrend must be none, constant, or linear")

    if config.taper_fraction:
        window = signal.windows.tukey(data.shape[1], alpha=min(1.0, config.taper_fraction * 2))
        data *= window

    sos = signal.butter(4, [config.bandpass_low_hz, config.bandpass_high_hz], btype="bandpass", fs=bundle.sampling_rate_hz, output="sos")
    data = signal.sosfiltfilt(sos, data, axis=-1)
    if config.notch_hz:
        if config.notch_hz >= nyquist:
            raise ValueError("notch_hz must be below Nyquist")
        b, a = signal.iirnotch(config.notch_hz, 30.0, fs=bundle.sampling_rate_hz)
        data = signal.filtfilt(b, a, data, axis=-1)

    if config.normalize == "robust":
        data = np.stack([channel / _robust_rms(channel) for channel in data])
    elif config.normalize == "max":
        data = np.stack([channel / max(float(np.max(np.abs(channel))), 1e-12) for channel in data])
    elif config.normalize != "none":
        raise ValueError("normalize must be none, robust, or max")

    processed = WaveformBundle(
        data.astype(np.float32),
        bundle.sampling_rate_hz,
        list(bundle.channels),
        start_time_utc=bundle.start_time_utc,
        source_format=bundle.source_format,
        metadata={**bundle.metadata, "preprocessing_version": config.version},
    )
    report = {"version": config.version, "config": config.__dict__, "before": before, "after": quality_statistics(processed.data)}
    return processed, report
