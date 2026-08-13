"""
仿真波形 → ObsPy Stream 桥接脚本

把 data/synthetic/events/*.npy 转成数据组能跑三模型推理的 ObsPy Stream，
并导出推理所需的元信息。

用法:
    python data/synthetic/export_streams.py --output data/synthetic/streams
    会为每条仿真波形生成一个 .mseed 文件 + metadata.json

数据组拿到后:
    from obspy import read
    stream = read("data/synthetic/streams/syn_0000.mseed")
    # 然后跑 PhaseNet / PickBlue / OBSTransformer 的 classify()
"""

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from obspy import Stream, Trace, UTCDateTime

OUT_DIR = Path(__file__).resolve().parent
EVENTS_DIR = OUT_DIR / "events"
LABELS_PATH = OUT_DIR / "labels.csv"

# 通道命名: 与数据组 data_layer.py 保持一致 (Z/N/E/H)
CHANNEL_NAMES = ["Z", "N", "E", "H"]

BASE_TIME = UTCDateTime("2018-01-01T00:00:00")


def npy_to_stream(waveform: np.ndarray, sample_id: str,
                  sampling_rate: float = 100.0) -> Stream:
    """
    将 (n_samples, n_channels) numpy 数组转成 ObsPy Stream

    Args:
        waveform: shape (n_samples, n_channels)
        sample_id: 样本 ID，用于设置 station 名
        sampling_rate: 采样率 Hz

    Returns:
        ObsPy Stream，每个通道一个 Trace
    """
    if waveform.ndim == 1:
        waveform = waveform.reshape(-1, 1)

    n_samples, n_channels = waveform.shape
    traces = []
    for i in range(n_channels):
        tr = Trace(data=waveform[:, i].astype(np.float64))
        tr.stats.network = "SYN"
        tr.stats.station = sample_id
        tr.stats.channel = CHANNEL_NAMES[i]
        tr.stats.sampling_rate = sampling_rate
        tr.stats.starttime = BASE_TIME
        traces.append(tr)

    return Stream(traces=traces)


def main():
    parser = argparse.ArgumentParser(description="仿真波形 → ObsPy Stream")
    parser.add_argument("--output", type=str,
                        default=str(OUT_DIR / "streams"),
                        help="输出目录")
    args = parser.parse_args()

    out_path = Path(args.output)
    out_path.mkdir(parents=True, exist_ok=True)

    # 读取标签
    labels = []
    with open(LABELS_PATH, "r") as f:
        for row in csv.DictReader(f):
            labels.append(row)

    metadata_list = []
    for row in labels:
        sample_id = row["sample_id"]
        wf_path = EVENTS_DIR / f"{sample_id}.npy"
        if not wf_path.exists():
            print(f"  [跳过] {sample_id}.npy 不存在")
            continue

        waveform = np.load(wf_path)
        stream = npy_to_stream(waveform, sample_id)

        # 写出 mseed
        mseed_path = out_path / f"{sample_id}.mseed"
        stream.write(str(mseed_path), format="MSEED")

        # 收集元信息 (数据组跑模型需要)
        metadata_list.append({
            "sample_id": sample_id,
            "n_channels": waveform.shape[1],
            "channels": CHANNEL_NAMES[:waveform.shape[1]],
            "sampling_rate_hz": 100.0,
            "P_time_s": row["P_time_s"],
            "S_time_s": row["S_time_s"],
            "label": row["label"],
            "noise_level": row["noise_level"],
            "mseed_path": str(mseed_path),
        })

    # 写元信息文件
    meta_path = out_path / "metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata_list, f, indent=2, ensure_ascii=False)

    print(f"✅ 转换 {len(metadata_list)} 条 → {out_path}")
    print(f"✅ 元信息 → {meta_path}")
    print()
    print("数据组用法:")
    print("  from obspy import read")
    print("  st = read('data/synthetic/streams/syn_0000.mseed')")
    print("  output = model.classify(st)  # PhaseNet / PickBlue / OBSTransformer")


if __name__ == "__main__":
    main()
