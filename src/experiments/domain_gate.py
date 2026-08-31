"""
修正 3: ID-only 域熟悉度门 (C 第三刀)

设计 (严格收缩版):
  - 只用 XO 主域建立"正常范围" (均值/协方差), 13 个外国台阵只作测试集
  - 特征 (5 维): log-RMS, spectral centroid, SNR, gap_ratio, clipping_ratio
  - 熟悉度 = 对 XO 分布的马氏距离; 阈值取 XO 自身的 95%/99% 分位
  - 三档: familiar(≤95%) → 正常; borderline(95-99%) → 收紧; unfamiliar(>99%) → ABSTAIN
  - DS5 新成功标准: BLANCO 上 coverage 主动下降 + retained unsafe 降低
    (不要求准确率恢复)

输出: results/domain_gate.json
用法: python -m src.experiments.domain_gate
"""

import json
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
from seisbench.data import OBS  # noqa: E402

from src.data_layer.data_layer import (  # noqa: E402
    TASK_REQUIRED_CHANNELS,
    classify,
    compute_quality_report,
    get_stream,
    init_models,
    stream_for_model,
)

OUT_JSON = ROOT / "results" / "domain_gate.json"
DEPLOYMENT = "_BLANCO"
N_SAMPLE = 200
SEED = 42

MODEL_REQUIRED_RAW = {
    "PhaseNet": {"Z", "1", "2"},
    "PickBlue": {"Z", "1", "2", "H"},
    "OBSTransformer": {"Z", "1", "2"},
    "EQTransformer": {"Z", "1", "2"},
}


def waveform_features(waveform, quality):
    """5 维稳定统计量 (C 建议的少量特征)."""
    z = np.asarray(waveform[0], dtype=np.float64)
    rms = np.sqrt(np.mean(z ** 2))
    spec = np.abs(np.fft.rfft(z - z.mean()))
    freqs = np.fft.rfftfreq(len(z), d=1.0 / 100.0)
    centroid = float(np.sum(freqs * spec) / (np.sum(spec) + 1e-12))
    return [
        float(np.log10(rms + 1e-12)),
        float(np.log10(centroid + 1e-12)),
        float(quality["snr_db"] if quality["snr_db"] else 0.0),
        float(quality["gap_ratio"] if quality["gap_ratio"] else 0.0),
        float(quality["clipping_ratio"] if quality["clipping_ratio"] else 0.0),
    ]


def main():
    print("修正 3: ID-only 域熟悉度门")

    # ── 1. XO 主域特征 (895 条) ──
    records = json.loads((ROOT / "data" / "batch_calibration"
                          / "records_all_v2.json").read_text(encoding="utf-8"))
    quality_map = {}
    import csv
    with open(ROOT / "data" / "quality_manifest.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            quality_map[row["sample_id"]] = row

    obs_xo = OBS(chunks=["201805", "201806", "201807"])
    meta_xo = {name: i for i, name in enumerate(obs_xo.metadata["trace_name_original"])}
    xo_features = []
    for n, r in enumerate(records):
        waveform, _ = obs_xo.get_sample(meta_xo[r["sample_id"]])
        xo_features.append(waveform_features(waveform, quality_map[r["sample_id"]]))
        if (n + 1) % 300 == 0:
            print(f"  XO 特征 {n + 1}/{len(records)}", flush=True)
    xo = np.array(xo_features)
    mu = xo.mean(axis=0)
    cov = np.cov(xo, rowvar=False)
    inv_cov = np.linalg.pinv(cov)
    print(f"XO 正常范围建立: n={len(xo)}, 特征 5 维")

    def mahalanobis(feats):
        d = feats - mu
        return float(np.sqrt(d @ inv_cov @ d))

    xo_d = np.array([mahalanobis(f) for f in xo])
    t95, t99 = np.percentile(xo_d, [95, 99])
    print(f"XO 马氏距离: 95% 分位 {t95:.2f}, 99% 分位 {t99:.2f} (阈值, ID-only)")

    # ── 2. BLANCO 采样 + 推理 (同 seed, 确定性重抽) ──
    obs_blanco = OBS(chunks=["000000"])
    candidates = []
    for i, row in enumerate(obs_blanco.metadata.itertuples(index=False)):
        net = getattr(row, "station_network_code")
        sr = float(getattr(row, "trace_sampling_rate_hz"))
        p_sample = getattr(row, "trace_p_arrival_sample")
        if net != DEPLOYMENT or abs(sr - 100.0) > 0.01 or not p_sample:
            continue
        candidates.append(i)
    rng = np.random.default_rng(SEED)
    sample = sorted(rng.choice(candidates, size=min(N_SAMPLE, len(candidates)),
                               replace=False).tolist())
    models, _ = init_models()

    blanco_features = []
    blanco_records = []
    for n, idx in enumerate(sample):
        stream, waveform, meta = get_stream(obs_blanco, idx)
        raw_comps = set(tr.stats.channel for tr in stream)
        sr = float(meta["trace_sampling_rate_hz"])
        p_sample = float(meta.get("trace_p_arrival_sample") or 0)
        s_sample = meta.get("trace_s_arrival_sample")
        truth_p = round(p_sample / sr, 3)
        truth_s = round(float(s_sample) / sr, 3) if s_sample else None
        quality = compute_quality_report(waveform, meta, TASK_REQUIRED_CHANNELS)
        predictions = {}
        for name, model in models.items():
            if not MODEL_REQUIRED_RAW[name].issubset(raw_comps):
                predictions[name] = {"P_pick": None, "S_pick": None, "confidence": None}
                continue
            try:
                predictions[name] = classify(model, name, stream_for_model(name, stream))
            except Exception:
                predictions[name] = {"P_pick": None, "S_pick": None, "confidence": None}
        blanco_features.append(waveform_features(waveform, quality))
        blanco_records.append({
            "sample_id": f"{DEPLOYMENT}.{idx}", "chunk": "000000",
            "truth_p_s": truth_p, "truth_s_s": truth_s,
            "predictions": predictions,
            "_quality": quality,
        })
        if (n + 1) % 50 == 0:
            print(f"  BLANCO 推理+特征 {n + 1}/{len(sample)}", flush=True)

    # ── 3. Trust 链 (BLANCO, 同主实验口径) ──
    from src.experiments.phase_evaluation import build_phase_units
    from src.experiments.run_main_experiment import build_unit_rows
    from src.trust_engine.config_loader import load_frozen_config

    units = build_phase_units(blanco_records)
    qmap = {r["sample_id"]: {
        "available_channels": "|".join(r["_quality"]["available_channels"]),
        "missing_channels": "|".join(r["_quality"]["missing_channels"]),
        "snr_db": r["_quality"]["snr_db"],
        "gap_ratio": r["_quality"]["gap_ratio"],
        "clipping_ratio": r["_quality"]["clipping_ratio"],
    } for r in blanco_records}
    frozen = load_frozen_config()
    config = frozen.trust_config(ranking_mode=True)
    rows = build_unit_rows(blanco_records, units, qmap,
                           frozen.model_profiles(), config,
                           {r["sample_id"]: r for r in blanco_records})
    print(f"BLANCO Trust 链完成: {len(rows)} 单元")

    # ── 4. 域门三档 + DS5 新成功标准 ──
    gate = []
    for r, feat in zip(blanco_records, blanco_features):
        d = mahalanobis(feat)
        level = "familiar" if d <= t95 else ("borderline" if d <= t99 else "unfamiliar")
        gate.append({"sample_id": r["sample_id"], "distance": round(d, 2),
                     "level": level})

    gated = {(g["sample_id"], ph): g["level"]
             for g in gate for ph in ("P", "S")}

    def metrics(rows, allow_levels):
        auto = wrong = total = 0
        for r in rows:
            key = (r["sample_id"], r["phase"])
            level = gated.get(key, "familiar")
            if level not in allow_levels:
                continue
            total += 1
            if r["verdict"] == "correct":
                auto += 1
            elif r["verdict"] == "wrong":
                auto += 1
                wrong += 1
        n_eval = len(rows)
        coverage = (auto) / n_eval * 100
        unsafe = wrong / auto * 100 if auto else float("nan")
        return coverage, unsafe

    from collections import Counter
    level_counts = Counter(g["level"] for g in gate)
    print(f"\nBLANCO 域门分档: {dict(level_counts)}")
    cov_all, unsafe_all = metrics(rows, {"familiar", "borderline", "unfamiliar"})
    cov_fam, unsafe_fam = metrics(rows, {"familiar"})
    cov_fb, unsafe_fb = metrics(rows, {"familiar", "borderline"})
    print(f"无门控 (全部):     coverage {cov_all:.1f}%  unsafe {unsafe_all:.1f}%")
    print(f"仅 familiar:       coverage {cov_fam:.1f}%  unsafe {unsafe_fam:.1f}%")
    print(f"familiar+border:   coverage {cov_fb:.1f}%  unsafe {unsafe_fb:.1f}%")
    # XO 参照从当前主实验结果动态读取 (不硬编码)
    import csv as _csv
    xo_rows = list(_csv.DictReader(
        open(ROOT / "results" / "main_results.csv", encoding="utf-8")))
    xo_ceiling = (sum(1 for r in xo_rows if r["verdict"] in ("correct", "wrong"))
                  / len(xo_rows) * 100)
    print(f"XO 参照 (v1.5 主实验): 天花板 {xo_ceiling:.1f}%")

    success = (cov_fam < cov_all) and (unsafe_fam < unsafe_all)
    report = {
        "xo_n": len(xo), "threshold_95": round(float(t95), 2),
        "threshold_99": round(float(t99), 2),
        "blanco_levels": dict(level_counts),
        "ungated": {"coverage": round(cov_all, 1), "unsafe": round(unsafe_all, 1)},
        "familiar_only": {"coverage": round(cov_fam, 1), "unsafe": round(unsafe_fam, 1)},
        "familiar_borderline": {"coverage": round(cov_fb, 1), "unsafe": round(unsafe_fb, 1)},
        "ds5_new_criterion": "coverage 主动下降 AND retained unsafe 降低",
        "ds5_success": bool(success),
    }
    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\nDS5 新标准判定: {'✅ 成立' if success else '❌ 未成立'}")
    print(f"✓ {OUT_JSON}")


if __name__ == "__main__":
    main()
