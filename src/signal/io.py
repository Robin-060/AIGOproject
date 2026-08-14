"""Standard waveform container and CSV/MiniSEED/SEG-Y readers."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd


@dataclass
class WaveformBundle:
    """Canonical in-memory waveform representation (channels x samples)."""

    data: np.ndarray
    sampling_rate_hz: float
    channels: List[str]
    start_time_utc: str = ""
    source_format: str = "ARRAY"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.data = np.asarray(self.data, dtype=np.float32)
        if self.data.ndim == 1:
            self.data = self.data[np.newaxis, :]
        if self.data.ndim != 2 or self.data.shape[1] == 0:
            raise ValueError("waveform data must have shape (channels, non-empty samples)")
        if self.sampling_rate_hz <= 0:
            raise ValueError("sampling_rate_hz must be positive")
        if len(self.channels) != self.data.shape[0]:
            raise ValueError("channel labels must match waveform channel count")

    @property
    def duration_s(self) -> float:
        return self.data.shape[1] / self.sampling_rate_hz

    @property
    def time_s(self) -> np.ndarray:
        return np.arange(self.data.shape[1], dtype=np.float64) / self.sampling_rate_hz

    def to_frame(self) -> pd.DataFrame:
        frame = pd.DataFrame({"time_s": self.time_s})
        for name, values in zip(self.channels, self.data):
            frame[name] = values
        return frame


def _canonical_channel(channel: str, position: int) -> str:
    value = str(channel).strip().upper()
    aliases = {"HHZ": "Z", "BHZ": "Z", "EHZ": "Z", "HHN": "N", "BHN": "N", "HHE": "E", "BHE": "E", "HH1": "N", "HH2": "E", "HHH": "H"}
    return aliases.get(value, value or f"CH{position + 1}")


def _from_csv_text(text: str, sampling_rate_hz: Optional[float]) -> WaveformBundle:
    frame = pd.read_csv(StringIO(text))
    if frame.empty:
        raise ValueError("CSV contains no waveform rows")
    time_column = next((name for name in frame.columns if name.lower() in {"time", "time_s", "seconds"}), None)
    if sampling_rate_hz is None and time_column and len(frame) > 1:
        differences = np.diff(pd.to_numeric(frame[time_column], errors="coerce"))
        differences = differences[np.isfinite(differences) & (differences > 0)]
        if len(differences):
            sampling_rate_hz = 1.0 / float(np.median(differences))
    if sampling_rate_hz is None:
        raise ValueError("CSV needs a time_s column or an explicit sampling rate")
    value_columns = [name for name in frame.columns if name != time_column]
    numeric = frame[value_columns].apply(pd.to_numeric, errors="coerce")
    numeric = numeric.dropna(axis=1, how="all")
    if numeric.empty:
        raise ValueError("CSV contains no numeric waveform channels")
    numeric = numeric.interpolate(limit_direction="both").fillna(0.0)
    channels = [_canonical_channel(name, i) for i, name in enumerate(numeric.columns)]
    return WaveformBundle(numeric.to_numpy(dtype=np.float32).T, float(sampling_rate_hz), channels, source_format="CSV")


def _from_obspy(source: Union[str, Path, BytesIO], format_name: Optional[str] = None) -> WaveformBundle:
    try:
        from obspy import read
    except ImportError as exc:  # pragma: no cover - optional format dependency
        raise RuntimeError("MiniSEED/SEG-Y reading requires ObsPy") from exc
    stream = read(source, format=format_name)
    if not stream:
        raise ValueError("waveform file contains no traces")
    sampling_rates = {round(float(trace.stats.sampling_rate), 6) for trace in stream}
    if len(sampling_rates) != 1:
        raise ValueError("all traces must use the same sampling rate")
    size = min(len(trace.data) for trace in stream)
    data = np.stack([np.asarray(trace.data[:size], dtype=np.float32) for trace in stream])
    channels = [_canonical_channel(getattr(trace.stats, "channel", ""), i) for i, trace in enumerate(stream)]
    start = str(min(trace.stats.starttime for trace in stream))
    return WaveformBundle(data, sampling_rates.pop(), channels, start_time_utc=start, source_format=format_name or "OBSPY")


def read_waveform(path: Union[str, Path], sampling_rate_hz: Optional[float] = None) -> WaveformBundle:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _from_csv_text(path.read_text(encoding="utf-8-sig"), sampling_rate_hz)
    formats = {".mseed": "MSEED", ".miniseed": "MSEED", ".sgy": "SEGY", ".segy": "SEGY"}
    if suffix not in formats:
        raise ValueError(f"unsupported waveform format: {suffix or 'unknown'}")
    return _from_obspy(str(path), formats[suffix])


def read_waveform_bytes(data: bytes, filename: str, sampling_rate_hz: Optional[float] = None) -> WaveformBundle:
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        return _from_csv_text(data.decode("utf-8-sig"), sampling_rate_hz)
    formats = {".mseed": "MSEED", ".miniseed": "MSEED", ".sgy": "SEGY", ".segy": "SEGY"}
    if suffix not in formats:
        raise ValueError(f"unsupported waveform format: {suffix or 'unknown'}")
    return _from_obspy(BytesIO(data), formats[suffix])


def write_waveform_csv(bundle: WaveformBundle, path: Union[str, Path]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    bundle.to_frame().to_csv(path, index=False)
