"""
真实三模型推理 — 对仿真 mseed 波形跑 PhaseNet / PickBlue / OBSTransformer

产出: predictions.json — 每个样本的真实模型预测 + 真值标签合并

用法:
    python data/synthetic/run_real_models.py
    # 首次运行会下载三个模型权重 (约几百MB)
"""

import json
from pathlib import Path

from obspy import read

from seisbench.models import PhaseNet, OBSTransformer
from seisbench.models.pickblue import PickBlue

OUT_DIR = Path(__file__).resolve().parent
STREAMS_DIR = OUT_DIR / "streams"
META_PATH = STREAMS_DIR / "metadata.json"
OUTPUT_PATH = OUT_DIR / "predictions.json"

# 模型缓存位置 (默认 ~/.seisbench, 可改)
import os
os.environ.setdefault("SEISBENCH_CACHE_ROOT", str(Path.home() / ".seisbench"))


def load_models():
    """加载三个预训练模型 (首次运行自动下载权重)"""
    print("加载模型 (首次运行需下载权重)...", flush=True)
    phasenet = PhaseNet.from_pretrained("obs")
    pickblue = PickBlue(base="phasenet")
    obst = OBSTransformer.from_pretrained("obst2024")
    print("✅ 三个模型加载完成\n", flush=True)
    return phasenet, pickblue, obst


def classify_one(model, model_name, stream):
    """对单条 stream 跑一个模型, 返回 {P_pick, S_pick, confidence}"""
    result = {"P_pick": None, "S_pick": None, "confidence": None}
    try:
        output = model.classify(stream)
    except Exception as e:
        print(f"    [{model_name}] 失败: {e}", flush=True)
        return result

    picks = getattr(output, "picks", [])
    if not picks:
        return result

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

    if p_time is not None:
        result["P_pick"] = round(float(p_time), 3)
    if s_time is not None:
        result["S_pick"] = round(float(s_time), 3)
    vals = [v for v in (p_val, s_val) if v is not None]
    if vals:
        result["confidence"] = round(float(max(vals)), 3)
    return result


def main():
    with open(META_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    print(f"待处理样本: {len(metadata)} 条\n")

    phasenet, pickblue, obst = load_models()
    models = [
        ("PhaseNet", phasenet),
        ("PickBlue", pickblue),
        ("OBSTransformer", obst),
    ]

    results = []
    for i, meta in enumerate(metadata):
        sample_id = meta["sample_id"]
        mseed_path = Path(meta["mseed_path"])
        if not mseed_path.exists():
            print(f"  [跳过] {sample_id}: mseed 不存在", flush=True)
            continue

        print(f"[{i+1}/{len(metadata)}] {sample_id} "
              f"(真值 P={meta['P_time_s']} S={meta['S_time_s']})", flush=True)

        stream = read(str(mseed_path))

        sample_result = {
            "sample_id": sample_id,
            "label": meta["label"],
            "noise_level": meta["noise_level"],
            "ground_truth": {
                "P_time_s": meta["P_time_s"],
                "S_time_s": meta["S_time_s"],
            },
            "predictions": {},
        }

        for name, model in models:
            r = classify_one(model, name, stream)
            sample_result["predictions"][name] = r
            if r["P_pick"] is not None:
                print(f"    {name}: P={r['P_pick']} S={r['S_pick']} "
                      f"conf={r['confidence']}", flush=True)
            else:
                print(f"    {name}: 无检出", flush=True)

        results.append(sample_result)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n✅ 推理完成 → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
