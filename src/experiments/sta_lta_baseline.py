"""
STA/LTA 传统基线 — 五类参照系最后一块 (Traditional)

协议 (冻结, 可复现, 标准做法):
  - 通道: Z (trace_component_order 第一道)
  - 预处理: Butterworth 带通 2-15 Hz (4 阶, 零相位), 幅值归一化
  - classic_sta_lta: sta=0.5s, lta=5.0s; 触发: on=5.0, off=1.2, min_duration=0.05s
  - 起始修正: 取触发段内比值上升最陡点 (经典斜率法)
  - P 候选 = 第一个触发 onset
  - S 候选 = P 之后第一个 onset ≥ P+1.5s 的触发
  - 风险排序: risk = 1 / (1 + peak_ratio) (ratio 越高越可信); 无拾取 → risk=1

输出: data/sta_lta_picks.csv (895 条) + 直接跑 Equal-Coverage 5 个点

用法:
    python -m src.experiments.sta_lta_baseline
"""

import csv
import os
import sys
from pathlib import Path

os.environ["SEISBENCH_CACHE_ROOT"] = os.path.expanduser("~/.seisbench")
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import warnings  # noqa: E402
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
from scipy.signal import butter, sosfiltfilt  # noqa: E402
from seisbench.data import OBS  # noqa: E402

from src.experiments.phase_evaluation import (  # noqa: E402
    build_phase_units,
    evaluate_units,
    load_records,
)
from src.experiments.run_baselines import top_k_gate  # noqa: E402
from src.signal.stalta import classic_sta_lta, detect_triggers  # noqa: E402

PICKS_PATH = ROOT / "data" / "sta_lta_picks.csv"
COVERAGE_POINTS = [50, 60, 70, 80, 90]
MIN_PS_SEPARATION_S = 1.5
BAND_LOW_HZ = 2.0
BAND_HIGH_HZ = 15.0
ON_THRESHOLD = 5.0


def refine_onsets(ratio: np.ndarray, triggers) -> list:
    """经典斜率法: 触发段内比值上升最陡点作为 onset."""
    refined = []
    sr = 100.0
    for trigger in triggers:
        on_i = int(round(trigger.onset_s * sr))
        off_i = min(int(round(trigger.offset_s * sr)), len(ratio) - 1)
        if off_i <= on_i + 1:
            continue
        seg = ratio[on_i:off_i + 1]
        step = int(np.argmax(np.diff(seg)))
        refined.append((round((on_i + step) / sr, 3), trigger.peak_ratio))
    return refined


def compute_picks() -> dict:
    """对 895 条记录跑带通滤波 + STA/LTA + 斜率修正, 返回
    {sample_id: (p_onset, s_onset, p_ratio, s_ratio)}."""
    records = load_records()
    obs = OBS(chunks=["201805", "201806", "201807"])
    meta = {name: i for i, name in enumerate(obs.metadata["trace_name_original"])}
    sos = butter(4, [BAND_LOW_HZ, BAND_HIGH_HZ], btype="band", fs=100.0, output="sos")

    picks = {}
    for i, record in enumerate(records):
        sid = record["sample_id"]
        waveform, _ = obs.get_sample(meta[sid])
        z = waveform[0].astype(np.float64)
        if np.any(np.abs(z) > 1e-8):
            z = z / np.max(np.abs(z))
        zf = sosfiltfilt(sos, z)
        ratio = classic_sta_lta(zf, 100.0, sta_s=0.5, lta_s=5.0)
        triggers = detect_triggers(ratio, 100.0, on_threshold=ON_THRESHOLD,
                                   off_threshold=1.2, minimum_duration_s=0.05)
        refined = refine_onsets(ratio, triggers)
        p_onset = p_ratio = s_onset = s_ratio = None
        if refined:
            p_onset, p_ratio = refined[0]
            for onset, peak in refined[1:]:
                if onset >= p_onset + MIN_PS_SEPARATION_S:
                    s_onset, s_ratio = onset, peak
                    break
        picks[sid] = (p_onset, s_onset, p_ratio, s_ratio)
        if (i + 1) % 200 == 0:
            print(f"  进度 {i + 1}/{len(records)}")
    return picks


def save_picks(picks: dict) -> None:
    with open(PICKS_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["sample_id", "p_onset_s", "s_onset_s",
                         "p_peak_ratio", "s_peak_ratio"])
        for sid, (p, s, pr, sr_) in sorted(picks.items()):
            writer.writerow([sid,
                             "" if p is None else p,
                             "" if s is None else s,
                             "" if pr is None else pr,
                             "" if sr_ is None else sr_])


def build_functions(picks: dict):
    def output(unit):
        p, s, _, _ = picks[unit["sample_id"]]
        return p if unit["phase"] == "P" else s

    def risk(unit):
        p, s, pr, sr_ = picks[unit["sample_id"]]
        ratio = pr if unit["phase"] == "P" else sr_
        if ratio is None:
            return 1.0
        return float(1.0 / (1.0 + ratio))

    return output, risk


def main():
    print("STA/LTA 传统基线 (895 条, Z 通道, sta=0.5s/lta=5.0s)")
    picks = compute_picks()
    save_picks(picks)
    n_p = sum(1 for v in picks.values() if v[0] is not None)
    n_s = sum(1 for v in picks.values() if v[1] is not None)
    print(f"✓ {PICKS_PATH} — P 触发 {n_p}/895, S 触发 {n_s}/895")

    units = build_phase_units(load_records())
    output_fn, risk_fn = build_functions(picks)
    print(f"\n{'策略':>20} {'目标Cov':>7} {'实际Cov':>8} {'Unsafe':>8} {'Burden':>8} {'拦截率':>8}")
    for target in COVERAGE_POINTS:
        risks = {(u["sample_id"], u["phase"]): risk_fn(u)
                 for u in units if u["primary_inclusion"]}
        gate = top_k_gate(units, risks, target / 100.0)
        stats = evaluate_units(units, output_fn, gate)
        print(f"{'Traditional-STA/LTA':>20} {target:>6}% {stats['coverage']*100:>7.1f}% "
              f"{stats['unsafe_output_rate']*100:>7.1f}% "
              f"{stats['review_burden']*100:>7.1f}% "
              f"{stats['error_interception_rate']*100:>7.1f}%")


if __name__ == "__main__":
    main()
