"""
批量多 chunk 真实模型推理 + 权重校准

做法 1+2:
  1. 遍历多个 OBS chunk (201805-201908 中选若干)
  2. 对每个 chunk 的 test split 跑三模型推理
  3. 汇总所有样本的预测 + 真值
  4. 用逻辑回归重新拟合证据权重

注意: 首次运行会下载 chunk 数据 (每 chunk ~2GB), 模型权重已缓存。

用法:
    python -m src.calibrate.batch_calibration --chunks 201805 201806 201807
    python -m src.calibrate.batch_calibration --max-samples 500
"""

import argparse
import json
import csv
from collections import defaultdict
from pathlib import Path

import numpy as np

OUT_DIR = Path("data/batch_calibration")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_chunk_data(chunk):
    """载入一个 chunk 的 test split 数据 (通过 SeisBench OBS)"""
    import seisbench
    from seisbench.data import OBS

    print(f"  载入 chunk {chunk} (test split)...", flush=True)
    obs = OBS(chunks=[chunk], split="test")
    return obs


def run_models_on_stream(models, stream):
    """对一条 stream 跑三个模型, 返回 {model: {P, S, score}}"""
    from seisbench.models import PhaseNet, OBSTransformer
    from seisbench.models.pickblue import PickBlue

    results = {}
    for name, model in models.items():
        try:
            output = model.classify(stream)
            picks = getattr(output, "picks", [])
            t_start = stream[0].stats.starttime
            p_time = s_time = p_val = s_val = None
            for pick in picks:
                phase = getattr(pick, "phase", "")
                peak_value = getattr(pick, "peak_value", None)
                peak_time = getattr(pick, "peak_time", None)
                if peak_time is None:
                    continue
                rel_sec = peak_time - t_start
                if phase.upper() == "P":
                    p_time = rel_sec
                    p_val = peak_value
                elif phase.upper() == "S":
                    s_time = rel_sec
                    s_val = peak_value
            vals = [v for v in (p_val, s_val) if v is not None]
            results[name] = {
                "P_pick": round(float(p_time), 3) if p_time is not None else None,
                "S_pick": round(float(s_time), 3) if s_time is not None else None,
                "confidence": round(float(max(vals)), 3) if vals else None,
            }
        except Exception as e:
            print(f"    [{name}] 失败: {e}", flush=True)
            results[name] = {"P_pick": None, "S_pick": None, "confidence": None}
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", nargs="+", default=["201805", "201806", "201807"])
    parser.add_argument("--max-samples", type=int, default=200,
                        help="每个 chunk 最多跑多少条 (0=不限)")
    args = parser.parse_args()

    from obspy import Stream, Trace, UTCDateTime
    from seisbench.models import PhaseNet, OBSTransformer
    from seisbench.models.pickblue import PickBlue

    print("加载三个模型...", flush=True)
    models = {
        "PhaseNet": PhaseNet.from_pretrained("geofon"),
        "PickBlue": PickBlue(base="phasenet"),
        "OBSTransformer": OBSTransformer.from_pretrained("obst2024"),
    }
    print("✅ 模型就绪\n", flush=True)

    all_records = []
    for chunk in args.chunks:
        print(f"=== chunk {chunk} ===", flush=True)
        try:
            obs = load_chunk_data(chunk)
        except Exception as e:
            print(f"  chunk {chunk} 载入失败: {e}", flush=True)
            continue

        n = len(obs)
        limit = min(n, args.max_samples) if args.max_samples else n
        print(f"  共 {n} 条, 跑前 {limit} 条", flush=True)

        for idx in range(limit):
            try:
                waveform, meta = obs.get_sample(idx)
            except Exception:
                continue

            sr = float(meta["trace_sampling_rate_hz"])
            comp_order = meta.get("trace_component_order", "Z12H")
            traces = []
            for i, comp in enumerate(comp_order):
                tr = Trace(data=waveform[i], header={
                    "network": meta.get("source_network_code", ""),
                    "station": meta.get("trace_station", ""),
                    "channel": comp,
                    "sampling_rate": sr,
                    "npts": waveform.shape[-1],
                    "starttime": UTCDateTime(meta["trace_start_time"]),
                })
                traces.append(tr)
            stream = Stream(traces=traces)

            # 真值 (若存在)
            truth_p = meta.get("trace_P_arrival_sample") if "trace_P_arrival_sample" in meta else None
            truth_s = meta.get("trace_S_arrival_sample") if "trace_S_arrival_sample" in meta else None

            sample_id = f"{chunk}_{idx}"
            preds = run_models_on_stream(models, stream)
            all_records.append({
                "sample_id": sample_id,
                "chunk": chunk,
                "truth_p_s": round(float(truth_p) / sr, 3) if truth_p else None,
                "truth_s_s": round(float(truth_s) / sr, 3) if truth_s else None,
                "predictions": preds,
            })
            if (idx + 1) % 20 == 0:
                print(f"    {idx+1}/{limit}", flush=True)

        # 每 chunk 存一份
        with open(OUT_DIR / f"records_{chunk}.json", "w", encoding="utf-8") as f:
            json.dump(all_records[-limit:], f, indent=2, ensure_ascii=False)

    # 汇总
    total = len(all_records)
    with_label = sum(1 for r in all_records
                     if r["truth_p_s"] and r["truth_s_s"])
    print(f"\n✅ 总计 {total} 条, 带 P/S 标注 {with_label} 条")
    print(f"✅ 已存 → {OUT_DIR}")
    print("\n下一步: 用这批数据重跑 src/calibrate/weight_calibration.py")


if __name__ == "__main__":
    main()
