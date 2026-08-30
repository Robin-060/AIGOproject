"""
第二数据域泛化验证 (DS5) — _BLANCO 台阵 (Blanco Fracture Zone OBS)

协议: 与主实验同口径 — 相位级, 容差 P0.5/S1.0, 四模型, hydrophone_v2 档案,
      自然罚分 (v1.4), Equal-Coverage 50% 点
数据: chunk 000000 的 _BLANCO deployment, 100Hz 子集, seed 42 抽样 200 条
模型通道资格 (与信任层适用性同语义):
  geofon / EQT / OBSTransformer: 需 Z,1,2 齐全
  PickBlue(obs): 需 Z,1,2,H 齐全
  (缺通道的 trace 跳过该模型, 预测留 None)

输出: results/generalization_blanco.json
用法: python -m src.experiments.run_generalization
"""

import json
import os
import sys
from pathlib import Path

os.environ["SEISBENCH_CACHE_ROOT"] = "D:/seisbench_cache"
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

OUT_JSON = ROOT / "results" / "generalization_blanco.json"
DEPLOYMENT = "_BLANCO"
N_SAMPLE = 200
SEED = 42

MODEL_REQUIRED_RAW = {
    "PhaseNet": {"Z", "1", "2"},           # geofon (ZNE)
    "PickBlue": {"Z", "1", "2", "H"},      # obs (Z12H)
    "OBSTransformer": {"Z", "1", "2"},     # obst2024 (ZNE)
    "EQTransformer": {"Z", "1", "2"},      # EQT-obs (ZNE)
}


def main():
    print(f"第二数据域: {DEPLOYMENT} | 抽样 {N_SAMPLE} | seed {SEED}")
    obs = OBS(chunks=["000000"])
    meta_df = obs.metadata
    candidates = []
    for i, row in enumerate(meta_df.itertuples(index=False)):
        net = getattr(row, "station_network_code")
        comps = getattr(row, "trace_component_order")
        sr = float(getattr(row, "trace_sampling_rate_hz"))
        p_sample = getattr(row, "trace_p_arrival_sample")
        if net != DEPLOYMENT or abs(sr - 100.0) > 0.01 or not p_sample:
            continue
        candidates.append(i)
    rng = np.random.default_rng(SEED)
    sample = sorted(rng.choice(candidates, size=min(N_SAMPLE, len(candidates)),
                               replace=False).tolist())
    print(f"候选 {len(candidates)} 条 (100Hz + 有P拾取), 抽样 {len(sample)} 条")

    models, _ = init_models()
    records = []
    for n, idx in enumerate(sample):
        stream, waveform, meta = get_stream(obs, idx)
        raw_comps = set(tr.stats.channel for tr in stream)
        sr = float(meta["trace_sampling_rate_hz"])
        p_sample = float(meta.get("trace_p_arrival_sample") or 0)
        s_sample = meta.get("trace_s_arrival_sample")
        truth_p = round(p_sample / sr, 3)
        truth_s = round(float(s_sample) / sr, 3) if s_sample else None

        predictions = {}
        for name, model in models.items():
            if not MODEL_REQUIRED_RAW[name].issubset(raw_comps):
                predictions[name] = {"P_pick": None, "S_pick": None, "confidence": None}
                continue
            try:
                result = classify(model, name, stream_for_model(name, stream))
            except Exception:
                result = {"P_pick": None, "S_pick": None, "confidence": None}
            predictions[name] = result

        quality = compute_quality_report(waveform, meta, TASK_REQUIRED_CHANNELS)
        records.append({
            "sample_id": f"{DEPLOYMENT}.{idx}",
            "chunk": "000000",
            "truth_p_s": truth_p,
            "truth_s_s": truth_s,
            "predictions": predictions,
            "_quality": quality,
        })
        if (n + 1) % 50 == 0:
            print(f"  推理进度 {n + 1}/{len(sample)}", flush=True)

    # ── 相位级评估: Trust (hydrophone_v2 + 自然罚分) vs Voting ──
    from src.experiments.phase_evaluation import build_phase_units, phase_verdict
    from src.experiments.run_main_experiment import (
        PROFILE_CANDIDATES, build_unit_rows,
    )
    from src.experiments.run_baselines import strat_vote, with_confidence
    from src.trust_engine.schema import TrustConfig

    units = with_confidence(build_phase_units(records), records)
    n_eval = sum(1 for u in units if u["primary_inclusion"])
    print(f"相位级评估单元: {n_eval}")

    quality_map = {r["sample_id"]: {
        "available_channels": "|".join(r["_quality"]["available_channels"]),
        "missing_channels": "|".join(r["_quality"]["missing_channels"]),
        "snr_db": r["_quality"]["snr_db"],
        "gap_ratio": r["_quality"]["gap_ratio"],
        "clipping_ratio": r["_quality"]["clipping_ratio"],
    } for r in records}
    config = TrustConfig()
    config.automatic_risk_threshold = 100.0
    rows = build_unit_rows(records, units, quality_map,
                           PROFILE_CANDIDATES["hydrophone_v2"], config,
                           {r["sample_id"]: r for r in records})

    def unsafe_at(row_list, target):
        out = [r for r in row_list if r["verdict"] in ("correct", "wrong")]
        out_sorted = sorted(out, key=lambda r: (r["risk"], r["sample_id"], r["phase"]))
        k = min(int(round(target / 100 * len(row_list))), len(out_sorted))
        accepted = {(r["sample_id"], r["phase"]) for r in out_sorted[:k]}
        wrong = total = 0
        for r in row_list:
            if (r["sample_id"], r["phase"]) in accepted:
                total += 1
                if r["verdict"] == "wrong":
                    wrong += 1
        return wrong / total * 100 if total else float("nan"), total / len(row_list) * 100

    t_unsafe, t_cov = unsafe_at(rows, 50)
    ceiling = sum(1 for r in rows if r["verdict"] in ("correct", "wrong")) / len(rows) * 100

    # Voting
    vote_output, vote_risk = strat_vote()
    v_rows = []
    for u in units:
        if not u["primary_inclusion"]:
            continue
        out = vote_output(u)
        verdict = phase_verdict(out, u["reference_time_s"], u["phase"])
        v_rows.append({"sample_id": u["sample_id"], "phase": u["phase"],
                       "risk": vote_risk(u), "verdict": verdict})
    v_unsafe, v_cov = unsafe_at(v_rows, 50)

    report = {
        "deployment": DEPLOYMENT, "n_sampled": len(sample), "n_eval": n_eval,
        "trust_unsafe_50": round(t_unsafe, 2), "trust_ceiling": round(ceiling, 1),
        "voting_unsafe_50": round(v_unsafe, 2),
        "xo_reference": {"trust_unsafe_50": 5.4, "voting_unsafe_50": 4.6,
                         "ceiling": 54.2},
    }
    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\n{DEPLOYMENT} (跨域): Trust {t_unsafe:.1f}%@50 | Voting {v_unsafe:.1f}%@50 "
          f"| 天花板 {ceiling:.1f}%")
    print(f"XO (主域):     Trust 5.4%@50 | Voting 4.6%@50 | 天花板 54.2%")
    print(f"✓ {OUT_JSON}")


if __name__ == "__main__":
    main()
