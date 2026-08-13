"""
仿真 OBS 地震波形生成器

产出: 带精确 P/S 标签的合成波形 + labels.csv

用法:
    python generate.py                      # 默认 60 条
    python generate.py --count 100          # 100 条
    python generate.py --noise L2 --count 20 # L2 噪声 20 条
"""

import numpy as np
import csv
import argparse
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent
EVENTS_DIR = OUT_DIR / "events"
LABELS_PATH = OUT_DIR / "labels.csv"

SAMPLING_RATE = 100.0  # Hz
N_SAMPLES = 6000       # 60 秒窗口

# 噪声等级: std
NOISE_LEVELS = {
    "L0": 0.03,   # ~20dB
    "L1": 0.10,   # ~10dB
    "L2": 0.25,   # ~5dB
    "L3": 0.45,   # ~2dB
}


def ricker_wavelet(length: int, dt: float = 0.01, center_freq: float = 5.0):
    """生成 Ricker 子波"""
    t = np.arange(length) * dt - (length * dt / 2)
    t2 = (np.pi * center_freq * t) ** 2
    return (1 - 2 * t2) * np.exp(-t2)


def make_earthquake(P_time_s: float, S_time_s: float,
                    n_channels: int = 4, noise_level: str = "L0",
                    seed: int = None):
    """
    生成含地震信号的多通道波形

    Args:
        P_time_s: P 波到达时间 (窗口相对秒)
        S_time_s: S 波到达时间 (窗口相对秒)
        n_channels: 通道数 (3=ZNE, 4=ZNEH)
        noise_level: "L0"|"L1"|"L2"|"L3"
        seed: 随机种子

    Returns:
        waveform: (6000, n_channels)
    """
    if seed is not None:
        np.random.seed(seed)

    noise_std = NOISE_LEVELS[noise_level]
    waveform = np.random.randn(N_SAMPLES, n_channels) * noise_std

    # P 波信号
    p_idx = int(P_time_s * SAMPLING_RATE)
    p_wavelet = ricker_wavelet(100, center_freq=6.0) * 3.0
    half = len(p_wavelet) // 2
    start = max(0, p_idx - half)
    end = min(N_SAMPLES, p_idx + half)
    w_start = half - (p_idx - start)
    w_end = half + (end - p_idx)
    if end > start:
        waveform[start:end, :] += p_wavelet[w_start:w_end, None]

    # S 波信号 (振幅略小)
    s_idx = int(S_time_s * SAMPLING_RATE)
    s_wavelet = ricker_wavelet(120, center_freq=3.0) * 2.0
    half = len(s_wavelet) // 2
    start = max(0, s_idx - half)
    end = min(N_SAMPLES, s_idx + half)
    w_start = half - (s_idx - start)
    w_end = half + (end - s_idx)
    if end > start:
        waveform[start:end, :] += s_wavelet[w_start:w_end, None]

    return waveform.astype(np.float32)


def make_noise(n_channels: int = 4, noise_level: str = "L0",
               seed: int = None):
    """生成纯噪声波形"""
    if seed is not None:
        np.random.seed(seed)
    noise_std = NOISE_LEVELS[noise_level]
    return (np.random.randn(N_SAMPLES, n_channels) * noise_std).astype(np.float32)


def make_clipped(P_time_s: float, S_time_s: float,
                 n_channels: int = 4, noise_level: str = "L0",
                 seed: int = None):
    """生成含削波的波形"""
    wf = make_earthquake(P_time_s, S_time_s, n_channels, noise_level, seed)
    clip_val = np.max(np.abs(wf)) * 0.3
    wf = np.clip(wf, -clip_val, clip_val)
    return wf.astype(np.float32)


def generate_dataset(total: int = 60):
    """
    生成完整数据集:
      - 15 清晰地震 (M3.0@50km)
      - 15 弱地震 (低 SNR)
      - 15 纯噪声
      - 10 缺通道 (仅有 Z/N/E)
      - 10 削波
    """
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    idx = 0

    def save(wf, p_time, s_time, label, noise_lvl, channels):
        nonlocal idx
        fname = f"syn_{idx:04d}.npy"
        np.save(EVENTS_DIR / fname, wf)
        rows.append([f"syn_{idx:04d}", p_time, s_time, label, noise_lvl, channels])
        idx += 1

    # 清晰地震
    for i in range(15):
        p = round(10.0 + np.random.uniform(0, 20), 2)
        s = round(p + np.random.uniform(8, 20), 2)
        noise = np.random.choice(["L0", "L1"])
        wf = make_earthquake(p, s, 4, noise, seed=i)
        save(wf, p, s, "EARTHQUAKE", noise, "ZNEH")

    # 弱地震
    for i in range(15):
        p = round(10.0 + np.random.uniform(0, 25), 2)
        s = round(p + np.random.uniform(5, 30), 2)
        noise = np.random.choice(["L2", "L3"])
        wf = make_earthquake(p, s, 4, noise, seed=i+100)
        save(wf, p, s, "EARTHQUAKE", noise, "ZNEH")

    # 纯噪声
    for i in range(15):
        noise = np.random.choice(["L0", "L1", "L2"])
        wf = make_noise(4, noise, seed=i+200)
        save(wf, -1, -1, "NOISE", noise, "ZNEH")

    # 缺通道 (只有 Z/N/E, 无 H)
    for i in range(10):
        p = round(10.0 + np.random.uniform(0, 20), 2)
        s = round(p + np.random.uniform(8, 20), 2)
        noise = np.random.choice(["L0", "L1"])
        wf_4ch = make_earthquake(p, s, 4, noise, seed=i+300)
        wf_3ch = wf_4ch[:, :3]  # 去掉 H
        save(wf_3ch, p, s, "EARTHQUAKE", noise, "ZNE")

    # 削波
    for i in range(10):
        p = round(10.0 + np.random.uniform(0, 20), 2)
        s = round(p + np.random.uniform(8, 20), 2)
        noise = np.random.choice(["L0", "L1"])
        wf = make_clipped(p, s, 4, noise, seed=i+400)
        save(wf, p, s, "EARTHQUAKE", noise, "ZNEH")

    # 写 labels.csv
    with open(LABELS_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sample_id", "P_time_s", "S_time_s", "label", "noise_level", "channels"])
        writer.writerows(rows)

    print(f"✅ 生成 {idx} 条仿真数据 → {EVENTS_DIR}")
    print(f"✅ 标签文件 → {LABELS_PATH}")
    _print_stats(rows)


def _print_stats(rows):
    labels = {}
    for r in rows:
        lbl = r[3]
        labels[lbl] = labels.get(lbl, 0) + 1
    print("  类别分布:", labels)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=65)
    args = parser.parse_args()
    generate_dataset(args.count)
