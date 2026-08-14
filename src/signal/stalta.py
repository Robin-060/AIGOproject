"""Transparent classic STA/LTA event-trigger baseline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np


@dataclass(frozen=True)
class Trigger:
    onset_s: float
    offset_s: float
    peak_ratio: float


def _moving_average(values: np.ndarray, window: int) -> np.ndarray:
    cumulative = np.cumsum(np.insert(values, 0, 0.0))
    average = (cumulative[window:] - cumulative[:-window]) / window
    return np.pad(average, (window - 1, 0), mode="edge")


def classic_sta_lta(values: np.ndarray, sampling_rate_hz: float, sta_s: float = 0.5, lta_s: float = 5.0) -> np.ndarray:
    samples = np.nan_to_num(np.asarray(values, dtype=np.float64))
    nsta = max(1, int(round(sta_s * sampling_rate_hz)))
    nlta = max(nsta + 1, int(round(lta_s * sampling_rate_hz)))
    if len(samples) < nlta:
        raise ValueError("waveform is shorter than the LTA window")
    energy = np.square(samples)
    sta = _moving_average(energy, nsta)
    lta = _moving_average(energy, nlta)
    ratio = sta / np.maximum(lta, np.finfo(np.float64).eps)
    ratio[:nlta] = 0.0
    return ratio


def detect_triggers(ratio: np.ndarray, sampling_rate_hz: float, on_threshold: float = 3.5, off_threshold: float = 1.2, minimum_duration_s: float = 0.05) -> List[Trigger]:
    active = False
    onset = 0
    peak = 0.0
    triggers: List[Trigger] = []
    minimum_samples = max(1, int(round(minimum_duration_s * sampling_rate_hz)))
    for index, value in enumerate(np.asarray(ratio, dtype=float)):
        if not active and value >= on_threshold:
            active, onset, peak = True, index, value
        elif active:
            peak = max(peak, value)
            if value <= off_threshold:
                if index - onset >= minimum_samples:
                    triggers.append(Trigger(onset / sampling_rate_hz, index / sampling_rate_hz, float(peak)))
                active = False
    if active and len(ratio) - onset >= minimum_samples:
        triggers.append(Trigger(onset / sampling_rate_hz, (len(ratio) - 1) / sampling_rate_hz, float(peak)))
    return triggers
