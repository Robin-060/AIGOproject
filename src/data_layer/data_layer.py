"""
数据层完整交付脚本
===================
为每个 OBS trace 生成 Trust Engine 所需的四个交付物：

  1. SampleMetadata   – 样本身份信息
  2. QualityReport    – 通道质量指标 (完整性 / SNR / 断点率 / 削波率)
  3. ModelProfile     – 每个模型的通道需求说明书
  4. ModelPrediction[]– 每个模型的 P/S 到时 + 置信度

输出: 统一 JSON，可经 src/data_layer/feed_trust_engine.py 喂入
Trust Engine 的 pipeline.run_pipeline()（冻结配置由 config_loader 读取）

用法:
    python data_layer.py                          # 处理 trace 0, 所有 chunk
    python data_layer.py --trace 5                # 处理 trace 5
    python data_layer.py --trace 5 --chunk 201805 # 指定 chunk
    python data_layer.py --output results.json    # 指定输出文件
"""

import os, sys, json, argparse
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import asdict

import numpy as np

CACHE_ROOT = (Path.home() / ".seisbench")
os.environ["SEISBENCH_CACHE_ROOT"] = str(CACHE_ROOT)

import seisbench
seisbench.cache_root = CACHE_ROOT

from obspy import Stream, Trace, UTCDateTime
from seisbench.data import OBS
from seisbench.models import PhaseNet, OBSTransformer
from seisbench.models.pickblue import PickBlue


# ═══════════════════════════════════════════════════════════════
# 0. 通道命名映射
# ═══════════════════════════════════════════════════════════════

# OBS 数据集使用的 component code → 标准地震学通道名
OBS_COMPONENT_MAP = {
    "Z": "Z",   # 垂直分量
    "1": "N",   # 水平分量 1 → 北向
    "2": "E",   # 水平分量 2 → 东向
    "H": "H",   # 水听器
}

# 任务要求的通道 (来自 TrustConfig 默认值)
TASK_REQUIRED_CHANNELS = ["Z", "N", "E"]


def map_components(component_order: str) -> Dict[str, str]:
    """将 OBS 原始 component code 映射为标准名，返回 {原始: 标准}"""
    return {raw: OBS_COMPONENT_MAP.get(raw, raw) for raw in component_order}


# ═══════════════════════════════════════════════════════════════
# 1. QualityReport — 通道质量计算
# ═══════════════════════════════════════════════════════════════

def compute_quality_report(
    waveform: np.ndarray,
    meta: dict,
    expected_channels: List[str] = None,
) -> dict:
    """
    从波形数据和元信息计算质量指标。

    参数
    ----
    waveform : np.ndarray  shape (n_channels, n_samples)
    meta : dict            OBS dataset 的 get_sample() 返回的元信息
    expected_channels :    任务需要的标准通道名列表

    返回
    ----
    dict 对应 QualityReport 字段
    """
    if expected_channels is None:
        expected_channels = TASK_REQUIRED_CHANNELS

    comp_order = meta.get("trace_component_order", "Z12H")
    comp_map = map_components(comp_order)

    # 可用通道 (标准名)
    available_channels = [comp_map[raw] for raw in comp_order]
    # 缺失的任务通道
    missing_channels = [ch for ch in expected_channels if ch not in available_channels]

    sr = float(meta["trace_sampling_rate_hz"])
    n_channels, n_samples = waveform.shape

    # ── 1a. 断点率 (gap_ratio) ──
    # 检测零值连续段 (seisbench 预处理后，gap 通常表现为全零段)
    total_elements = n_channels * n_samples
    gap_elements = 0
    for ch_idx in range(n_channels):
        data = waveform[ch_idx]
        # 连续 ≥ 5 个零值样本视为一个 gap
        is_zero = np.abs(data) < 1e-12
        # 用卷积找连续零值段
        zero_runs = np.diff(np.concatenate(([0], is_zero.astype(int), [0])))
        run_starts = np.where(zero_runs == 1)[0]
        run_ends = np.where(zero_runs == -1)[0]
        run_lengths = run_ends - run_starts
        gap_elements += np.sum(run_lengths[run_lengths >= 5])

    gap_ratio = round(gap_elements / total_elements, 4)

    # ── 1b. 削波率 (clipping_ratio) ──
    # 样本值达到 ±99.5% 动态范围时视为削波
    channel_clipping = []
    for ch_idx in range(n_channels):
        data = waveform[ch_idx]
        abs_max = np.max(np.abs(data))
        if abs_max > 1e-10:
            near_rail = np.sum(np.abs(data) >= 0.995 * abs_max)
            channel_clipping.append(near_rail / n_samples)
        else:
            channel_clipping.append(0.0)
    clipping_ratio = round(max(channel_clipping), 4)

    # ── 1c. SNR ──
    # 方法: 将每道波形等分为 20 个窗口，取 RMS 最小的窗口作为噪声估计
    #       SNR_dB = 10 * log10( (总 RMS² - 噪声 RMS²) / 噪声 RMS² )
    channel_snrs = []
    for ch_idx in range(n_channels):
        data = waveform[ch_idx].astype(np.float64)
        n_windows = 20
        window_len = max(n_samples // n_windows, 10)
        rms_list = []
        for w in range(0, n_samples, window_len):
            seg = data[w : w + window_len]
            if len(seg) < 10:
                continue
            rms_list.append(np.sqrt(np.mean(seg ** 2)))
        if not rms_list:
            channel_snrs.append(0.0)
            continue
        noise_rms = np.min(rms_list)
        total_rms = np.sqrt(np.mean(data ** 2))
        if noise_rms > 1e-15 and total_rms > noise_rms:
            snr = 10.0 * np.log10((total_rms ** 2 - noise_rms ** 2) / noise_rms ** 2)
        elif noise_rms > 1e-15:
            snr = 0.0
        else:
            snr = 30.0  # 近乎静默，给高分
        channel_snrs.append(snr)

    snr_db = round(float(np.mean(channel_snrs)), 1)

    return {
        "available_channels": available_channels,
        "missing_channels": missing_channels,
        "required_channels_for_task": expected_channels,
        "sampling_rate_hz": sr,
        "gap_ratio": gap_ratio,
        "clipping_ratio": clipping_ratio,
        "snr_db": snr_db,
        "metric_version": "v0.1",
        "source": "REAL_CALCULATION",
    }


# ═══════════════════════════════════════════════════════════════
# 2. SampleMetadata — 样本身份信息
# ═══════════════════════════════════════════════════════════════

def build_sample_metadata(meta: dict, trace_idx: int, chunk: str) -> dict:
    """
    从 OBS 元信息构建 SampleMetadata。

    返回 dict 对应 SampleMetadata 字段 (P1 扩展版)
    """
    start_time = meta.get("trace_start_time", "")
    npts = meta.get("trace_nsamples", 0)
    sr = float(meta.get("trace_sampling_rate_hz", 100.0))
    duration_s = round(npts / sr, 1) if sr > 0 else 60.0

    station = meta.get("trace_station", f"unknown_{trace_idx}")
    deployment = meta.get("trace_name", f"obs_deployment_{chunk}")

    sample_id = f"obs_{chunk}_trace{trace_idx:04d}"

    return {
        "sample_id": sample_id,
        "deployment_id": str(deployment),
        "station_id": str(station),
        "window_id": f"chunk_{chunk}",
        "start_time_utc": str(start_time),
        "duration_s": duration_s,
        "canonical_time_basis": "WINDOW_SECONDS",
        "expected_event": None,
        "data_source": "REAL",
        "preprocessing_version": "obs_raw_v1",
        "resampling_applied": False,
        "resampling_trace_id": None,
    }


# ═══════════════════════════════════════════════════════════════
# 3. ModelProfile — 模型通道需求说明书
# ═══════════════════════════════════════════════════════════════

MODEL_PROFILES: Dict[str, dict] = {
    "PhaseNet": {
        "model_name": "PhaseNet",
        # 指纹验证 (model_registry.md): 冻结数据此列为 geofon 陆地权重, 非 obs
        "model_version": "geofon_pretrained",
        "model_family": "generic_three_component",
        # geofon 为陆地三分量模型 (Z, N, E)
        "required_channels": ["Z", "N", "E"],
        "preferred_channels": [],
        "accepted_sampling_rates_hz": [100.0],
        "resampling_supported": True,
        "required_preprocessing_version": "obs_raw_v1",
        "validation_profile_id": "phasenet_geofon_v1",
        "validation_domain_known": True,
        "profile_source": "REAL_ADAPTER",
    },
    "PickBlue": {
        "model_name": "PickBlue",
        # seisbench 0.12.3: PickBlue(base="phasenet") ≡ PhaseNet.from_pretrained("obs")
        "model_version": "obs_pretrained",
        "model_family": "obs_specialized",
        # v1.2 选择程序 (semifinal_main.yaml): 实际输入契约以 H 为主, 缺 E 仍可用
        "required_channels": ["Z", "H"],
        "preferred_channels": ["N", "E"],
        "accepted_sampling_rates_hz": [100.0],
        "resampling_supported": True,
        "required_preprocessing_version": "obs_raw_v1",
        "validation_profile_id": "pickblue_obs_v1",
        "validation_domain_known": True,
        "profile_source": "REAL_ADAPTER",
    },
    "OBSTransformer": {
        "model_name": "OBSTransformer",
        "model_version": "obst2024",
        "model_family": "transformer_multicomponent",
        # OBSTransformer 2024 版: 主要用水听器 H，也能用 Z/N/E
        "required_channels": ["H"],
        "preferred_channels": ["Z", "N", "E"],
        "accepted_sampling_rates_hz": [100.0],
        "resampling_supported": True,
        "required_preprocessing_version": "obs_raw_v1",
        "validation_profile_id": "obst2024_v1",
        "validation_domain_known": True,
        "profile_source": "REAL_ADAPTER",
    },
}


# ═══════════════════════════════════════════════════════════════
# 4. 模型推理 + ModelPrediction 生成
# ═══════════════════════════════════════════════════════════════

def init_models():
    """加载三个模型，返回模型字典 + AdapterStatus 列表"""
    print("  Loading models...", flush=True)
    models = {}
    adapter_statuses = []

    try:
        # 指纹验证 (model_registry.md): 冻结数据此列为 geofon 陆地权重
        models["PhaseNet"] = PhaseNet.from_pretrained("geofon")
        adapter_statuses.append({
            "model_name": "PhaseNet",
            "loaded": True,
            "run_succeeded": True,
            "output_comparable": True,
        })
        print("    PhaseNet (geofon) ✓", flush=True)
    except Exception as e:
        print(f"    PhaseNet ✗ ({e})", flush=True)
        adapter_statuses.append({
            "model_name": "PhaseNet",
            "loaded": False,
            "run_succeeded": False,
            "output_comparable": False,
        })

    try:
        models["PickBlue"] = PickBlue(base="phasenet")
        adapter_statuses.append({
            "model_name": "PickBlue",
            "loaded": True,
            "run_succeeded": True,
            "output_comparable": True,
        })
        print("    PickBlue (phasenet base) ✓", flush=True)
    except Exception as e:
        print(f"    PickBlue ✗ ({e})", flush=True)
        adapter_statuses.append({
            "model_name": "PickBlue",
            "loaded": False,
            "run_succeeded": False,
            "output_comparable": False,
        })

    try:
        models["OBSTransformer"] = OBSTransformer.from_pretrained("obst2024")
        adapter_statuses.append({
            "model_name": "OBSTransformer",
            "loaded": True,
            "run_succeeded": True,
            "output_comparable": True,
        })
        print("    OBSTransformer (obst2024) ✓", flush=True)
    except Exception as e:
        print(f"    OBSTransformer ✗ ({e})", flush=True)
        adapter_statuses.append({
            "model_name": "OBSTransformer",
            "loaded": False,
            "run_succeeded": False,
            "output_comparable": False,
        })

    return models, adapter_statuses


def get_stream(obs_dataset, trace_idx: int):
    """从 OBS dataset 提取 trace 并构建 ObsPy Stream"""
    waveform, meta = obs_dataset.get_sample(trace_idx)
    sr = float(meta["trace_sampling_rate_hz"])
    comp_order = meta.get("trace_component_order", "Z12H")
    traces = []
    for i, comp in enumerate(comp_order):
        hdr = {
            "network": meta.get("source_network_code", ""),
            "station": meta.get("trace_station", ""),
            "channel": comp,
            "sampling_rate": sr,
            "npts": waveform.shape[-1],
            "starttime": UTCDateTime(meta["trace_start_time"]),
        }
        traces.append(Trace(data=waveform[i], header=hdr))
    return Stream(traces=traces), waveform, meta


def stream_for_model(model_name: str, stream: Stream) -> Stream:
    """按模型实测 component_order 组装输入流。

    geofon (冻结"PhaseNet"列) 为陆地三分量模型 (ZNE): 选 Z/1/2 并映射
    1→N、2→E —— 指纹复现验证 (end_to_end_verification.py) 同款逻辑。
    其余模型直接使用完整流 (PickBlue/obs 用 Z12H, OBSTransformer 兼容全流)。
    """
    if model_name == "PhaseNet":
        subset = stream.select(channel="Z") + stream.select(channel="1") \
            + stream.select(channel="2")
        for trace in subset:
            trace.stats.channel = {"Z": "Z", "1": "N", "2": "E"}[trace.stats.channel]
        return subset
    return stream


def classify(model, model_name: str, stream) -> dict:
    """在单道 stream 上运行模型，返回 {P_pick, S_pick, confidence}"""
    result = {"P_pick": None, "S_pick": None, "confidence": None}
    try:
        output = model.classify(stream)
    except Exception as exc:
        print(f"  [{model_name}] classify failed: {exc}", flush=True)
        return result

    picks = getattr(output, "picks", [])
    if not picks:
        return result

    p_time = s_time = p_val = s_val = None
    t_start = stream[0].stats.starttime
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

    if p_time is not None:
        result["P_pick"] = round(float(p_time), 2)
    if s_time is not None:
        result["S_pick"] = round(float(s_time), 2)
    vals = [v for v in (p_val, s_val) if v is not None]
    if vals:
        result["confidence"] = round(float(max(vals)), 3)

    return result


def build_model_predictions(
    sample_id: str,
    window_id: str,
    raw_results: Dict[str, dict],
    adapter_statuses: List[dict],
) -> List[dict]:
    """
    将 classify() 的原始输出转换为 ModelPrediction[] 列表。

    每个 (模型, 震相) 组合产生一条 ModelPrediction。
    """
    predictions = []
    adapter_map = {s["model_name"]: s for s in adapter_statuses}

    for model_name, result in raw_results.items():
        model_version = MODEL_PROFILES.get(model_name, {}).get("model_version", "unknown")
        adapter = adapter_map.get(model_name, {})
        adapter_ok = (
            adapter.get("loaded", False)
            and adapter.get("run_succeeded", False)
            and adapter.get("output_comparable", False)
        )

        for phase_key in ("P_pick", "S_pick"):
            time_s = result.get(phase_key)
            prediction = {
                "sample_id": sample_id,
                "window_id": window_id,
                "model_name": model_name,
                "model_version": model_version,
                "phase": "P" if phase_key == "P_pick" else "S",
                "time_s": time_s if time_s is not None else -1,
                "pick_time_utc": None,
                "source_time_basis": "WINDOW_SECONDS",
                "score": result.get("confidence"),
                "adapter_status": "OK" if adapter_ok else "FAIL",
                "preprocessing_version": "obs_raw_v1",
                "prediction_source": "REAL_MODEL",
            }
            predictions.append(prediction)

    return predictions


# ═══════════════════════════════════════════════════════════════
# 5. 主流程 — 整合所有输出
# ═══════════════════════════════════════════════════════════════

def list_available_chunks() -> List[str]:
    """扫描本地缓存，返回所有完整的 chunk 列表"""
    data_dir = CACHE_ROOT / "datasets" / "obs"
    if not data_dir.exists():
        return []
    chunks = set()
    for f in data_dir.iterdir():
        if not f.is_file():
            continue
        name = f.name
        if name.startswith("metadata") and name.endswith(".csv"):
            chunk = name.replace("metadata", "").replace(".csv", "")
            chunks.add(chunk)
    available = []
    for chunk in sorted(chunks):
        meta_file = f"metadata{chunk}.csv"
        wf_file = f"waveforms{chunk}.hdf5"
        if (data_dir / meta_file).exists() and (data_dir / wf_file).exists():
            available.append(chunk)
    return available


def process_trace(
    obs_dataset,
    trace_idx: int,
    chunk: str,
    models: dict,
    adapter_statuses: List[dict],
) -> dict:
    """
    处理单个 trace，返回完整的四合一输出字典:

        {
            "sample_metadata": {...},
            "quality_report": {...},
            "model_profiles": {...},
            "model_predictions": [...],
            "adapter_statuses": [...],
        }
    """
    # ── 获取波形和元数据 ──
    stream, waveform, meta = get_stream(obs_dataset, trace_idx)

    print(f"  Station: {meta.get('trace_station', '?')}")
    print(f"  Components: {meta.get('trace_component_order', '?')}")
    print(f"  SR: {meta.get('trace_sampling_rate_hz', '?')} Hz")
    print(f"  Samples: {waveform.shape[-1]}")

    # ── 1. SampleMetadata ──
    sample_meta = build_sample_metadata(meta, trace_idx, chunk)
    sample_id = sample_meta["sample_id"]
    window_id = sample_meta["window_id"]

    # ── 2. QualityReport ──
    quality = compute_quality_report(waveform, meta, TASK_REQUIRED_CHANNELS)

    # ── 3. ModelProfile (静态，全 trace 共用) ──
    profiles = {name: dict(profile) for name, profile in MODEL_PROFILES.items()}

    # ── 4. 模型推理 → ModelPrediction[] ──
    raw_results = {}
    for name, model in models.items():
        print(f"  Running {name}...", flush=True)
        raw_results[name] = classify(model, name, stream_for_model(name, stream))

    predictions = build_model_predictions(sample_id, window_id, raw_results, adapter_statuses)

    # ── 组装输出 ──
    output = {
        "sample_metadata": sample_meta,
        "quality_report": quality,
        "model_profiles": profiles,
        "model_predictions": predictions,
        "adapter_statuses": adapter_statuses,
    }

    # ── 打印摘要 ──
    print()
    print(f"  Quality: SNR={quality['snr_db']}dB, gap={quality['gap_ratio']:.3%}, "
          f"clip={quality['clipping_ratio']:.3%}, missing={quality['missing_channels']}")
    for p in predictions:
        if p["time_s"] > 0:
            print(f"  {p['model_name']:15s} {p['phase']}-pick @ {p['time_s']:7.2f}s  "
                  f"score={p['score']}")

    return output


def main():
    parser = argparse.ArgumentParser(description="OBS 数据层: 生成 Trust Engine 所需的全部交付物")
    parser.add_argument("--trace", type=int, default=0,
                        help="Trace 索引 (默认: 0)")
    parser.add_argument("--chunk", type=str, default=None,
                        help="指定 chunk (如 201805), 不指定则用第一个可用 chunk")
    parser.add_argument("--output", type=str, default=None,
                        help="输出 JSON 文件路径 (默认: 打印到 stdout)")
    args = parser.parse_args()

    print("=" * 60)
    print("OBS Trust Engine — 数据层完整交付")
    print("=" * 60)

    # 查找可用 chunk
    available = list_available_chunks()
    if not available:
        print("ERROR: 未找到完整 chunk。请先运行 download_obs_dataset.py")
        print(f"  检查路径: {CACHE_ROOT / 'datasets' / 'obs'}")
        sys.exit(1)

    if args.chunk:
        if args.chunk not in available:
            print(f"Chunk '{args.chunk}' 不可用。可用: {available}")
            sys.exit(1)
        use_chunk = args.chunk
    else:
        use_chunk = available[0]

    print(f"可用 chunks ({len(available)}): {available}")
    print(f"使用 chunk: {use_chunk}")
    print()

    # 加载数据
    print("Loading OBS dataset...", flush=True)
    obs = OBS(chunks=[use_chunk])
    n_traces = len(obs)
    print(f"  Chunk {use_chunk}: {n_traces} traces")
    print()

    if args.trace >= n_traces:
        print(f"ERROR: trace 索引 {args.trace} 超出范围 (0-{n_traces-1})")
        sys.exit(1)

    # 加载模型
    models, adapter_statuses = init_models()
    if not models:
        print("ERROR: 所有模型加载失败，无法继续。")
        sys.exit(1)
    print()

    # 处理 trace
    print("=" * 60)
    print(f"Trace #{args.trace}")
    print("=" * 60)
    result = process_trace(
        obs_dataset=obs,
        trace_idx=args.trace,
        chunk=use_chunk,
        models=models,
        adapter_statuses=adapter_statuses,
    )

    # 输出
    output_json = json.dumps(result, indent=2, ensure_ascii=False, default=str)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(output_json, encoding="utf-8")
        print(f"\n✓ 结果已写入: {output_path.resolve()}")
    else:
        print("\n" + "=" * 60)
        print("统一 JSON 输出:")
        print("=" * 60)
        print(output_json)

    print("\nDone.")


if __name__ == "__main__":
    main()
