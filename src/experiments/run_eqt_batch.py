"""
EQTransformer-obs 批量推理 — 第四模型 (C 已批准: 新增异构证据, 不替换)

对 895 条冻结记录跑 EQTransformer.from_pretrained("obs"),
输出 P/S 拾取与置信度, 供四模型冻结预测升版 (v1.3) 使用。

协议:
  - 通道: ZNE 三分量 (1→N, 2→E 映射), 60s 窗口 100Hz
  - 推理: 数据组同款 classify (P/S peak + max confidence)
  - 增量保存: 每 50 条写盘, 支持断点续跑 (已完成的样本自动跳过)
  - 环境: seisbench 0.12.3, torch 2.13.0+cpu

输出: data/eqt_predictions.json {sample_id: {P_pick, S_pick, confidence}}

用法:
    python -m src.experiments.run_eqt_batch
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

from seisbench.data import OBS  # noqa: E402
from seisbench.models import EQTransformer  # noqa: E402

from src.data_layer.data_layer import classify, get_stream  # noqa: E402

RECORDS_PATH = ROOT / "data" / "batch_calibration" / "records_all.json"
OUT_PATH = ROOT / "data" / "eqt_predictions.json"
SAVE_EVERY = 50


def build_zne_stream(stream):
    s3 = stream.select(channel="Z") + stream.select(channel="1") + stream.select(channel="2")
    for tr in s3:
        tr.stats.channel = {"Z": "Z", "1": "N", "2": "E"}[tr.stats.channel]
    return s3


def main():
    records = json.loads(RECORDS_PATH.read_text(encoding="utf-8"))
    sample_ids = [r["sample_id"] for r in records]

    # 断点续跑: 载入已有结果
    done = {}
    if OUT_PATH.exists():
        done = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    print(f"总样本 {len(sample_ids)} | 已完成 {len(done)} | 待跑 {len(sample_ids) - len(done)}")

    print("加载 EQTransformer-obs...", flush=True)
    eqt = EQTransformer.from_pretrained("obs")
    print("加载 OBS 数据集 (3 chunks)...", flush=True)
    obs = OBS(chunks=["201805", "201806", "201807"])
    meta = {name: i for i, name in enumerate(obs.metadata["trace_name_original"])}

    total = len(done)
    for i, sid in enumerate(sample_ids):
        if sid in done:
            continue
        stream, _, _ = get_stream(obs, meta[sid])
        result = classify(eqt, "EQTransformer-obs", build_zne_stream(stream))
        done[sid] = {
            "P_pick": result["P_pick"],
            "S_pick": result["S_pick"],
            "confidence": result["confidence"],
        }
        total += 1
        if total % SAVE_EVERY == 0:
            OUT_PATH.write_text(json.dumps(done, indent=1, ensure_ascii=False),
                                encoding="utf-8")
            print(f"  进度 {total}/{len(sample_ids)} (已存盘)", flush=True)

    OUT_PATH.write_text(json.dumps(done, indent=1, ensure_ascii=False),
                        encoding="utf-8")
    n_p = sum(1 for v in done.values() if v["P_pick"] is not None)
    n_s = sum(1 for v in done.values() if v["S_pick"] is not None)
    print(f"\n✓ {OUT_PATH} — P 拾取 {n_p}/{len(done)}, S 拾取 {n_s}/{len(done)}")


if __name__ == "__main__":
    main()
