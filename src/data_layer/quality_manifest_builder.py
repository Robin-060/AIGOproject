"""
质量清单构建器 — A 自行修复"历史基线使用假质量数据"问题

背景: 历史基线脚本对 895 条样本一律使用硬编码质量报告 (SNR=20, 无缺道),
      数据证据层从未在真实质量数据上运行过, DS4 也无法评估。
本脚本不依赖数据组: 下载 OBS 数据集 3 个 chunk → 按 sample_id 匹配原始波形 →
用数据组同款 compute_quality_report 计算真实质量指标 → 输出质量清单。

两步:
  --download  下载 chunk 201805/201806/201807 (约 6GB, 断点续传, 可反复执行)
  --build     下载完成后: 匹配 895 个 sample_id 并计算质量, 输出
              data/quality_manifest.csv

用法:
  python -m src.data_layer.quality_manifest_builder --download
  python -m src.data_layer.quality_manifest_builder --build
"""

import argparse
import csv
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_layer.download_obs_dataset import (  # noqa: E402
    ZENODO_RECORD_ID,
    download_file,
)

CACHE_ROOT = (Path.home() / ".seisbench")
DATASET_DIR = CACHE_ROOT / "datasets" / "obs"
RECORDS_PATH = ROOT / "data" / "batch_calibration" / "records_all.json"
OUT_PATH = ROOT / "data" / "quality_manifest.csv"
CHUNKS = ("201805", "201806", "201807")


def download_chunks() -> bool:
    """下载 3 个 chunk 的 metadata + waveforms (断点续传)."""
    print("=" * 60)
    print("下载 OBS 数据集 chunk: " + ", ".join(CHUNKS))
    print("=" * 60)
    api_url = f"https://zenodo.org/api/records/{ZENODO_RECORD_ID}"
    print(f"查询 Zenodo 记录: {api_url}")
    try:
        resp = requests.get(api_url, timeout=60)
        resp.raise_for_status()
    except Exception as exc:
        print(f"无法访问 Zenodo API: {exc}")
        print("请检查网络/VPN 后重跑 (已下载部分会自动续传)")
        return False

    files = {f["key"]: f for f in resp.json().get("files", [])}
    ok_all = True
    for chunk in CHUNKS:
        for name in (f"metadata{chunk}.csv", f"waveforms{chunk}.hdf5"):
            if name not in files:
                print(f"  [缺失] Zenodo 记录中没有 {name}")
                ok_all = False
                continue
            size_mb = files[name].get("size", 0) / 1024 / 1024
            print(f"\n下载 {name} ({size_mb:.0f} MB)...")
            ok = download_file(files[name]["links"]["self"],
                               DATASET_DIR / name, desc=name)
            print(f"  [{name}] {'完成' if ok else '失败 (可重跑续传)'}")
            ok_all = ok_all and ok
    return ok_all


def build_quality_manifest() -> bool:
    """匹配 sample_id → 原始波形 → compute_quality_report → CSV."""
    from src.data_layer.data_layer import (
        TASK_REQUIRED_CHANNELS,
        compute_quality_report,
        list_available_chunks,
    )
    from seisbench.data import OBS

    available = [c for c in CHUNKS if c in list_available_chunks()]
    missing = [c for c in CHUNKS if c not in available]
    if missing:
        print(f"chunk 不完整, 请先 --download: {missing}")
        return False

    print("加载 OBS 数据集 (3 个 chunk)...")
    obs = OBS(chunks=available)
    meta_df = obs.metadata
    # 数据组的 sample_id 来自 trace_name_original (trace_name 是 bucket 编号, 不能用于匹配)
    trace_index = {name: idx for idx, name in enumerate(meta_df["trace_name_original"])}
    print(f"数据集 trace 总数: {len(trace_index)}")

    records = json.loads(RECORDS_PATH.read_text(encoding="utf-8"))
    rows = []
    not_found = 0
    for i, record in enumerate(records):
        sid = record["sample_id"]
        if sid not in trace_index:
            not_found += 1
            rows.append({
                "sample_id": sid, "snr_db": "", "gap_ratio": "",
                "clipping_ratio": "", "available_channels": "",
                "missing_channels": "", "status": "TRACE_NOT_FOUND",
            })
            continue
        waveform, meta = obs.get_sample(trace_index[sid])
        quality = compute_quality_report(waveform, meta, TASK_REQUIRED_CHANNELS)
        rows.append({
            "sample_id": sid,
            "snr_db": quality["snr_db"],
            "gap_ratio": quality["gap_ratio"],
            "clipping_ratio": quality["clipping_ratio"],
            "available_channels": "|".join(quality["available_channels"]),
            "missing_channels": "|".join(quality["missing_channels"]),
            "status": "OK",
        })
        if (i + 1) % 100 == 0:
            print(f"  进度 {i + 1}/{len(records)}")

    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    ok_count = sum(1 for row in rows if row["status"] == "OK")
    print(f"\n✓ 质量清单: {OUT_PATH} ({ok_count} 条 OK, {not_found} 条未匹配)")
    return True


def main():
    parser = argparse.ArgumentParser(description="OBS 质量清单构建器")
    parser.add_argument("--download", action="store_true", help="下载 3 个 chunk")
    parser.add_argument("--build", action="store_true", help="匹配并计算质量清单")
    args = parser.parse_args()

    if args.download:
        if not download_chunks():
            sys.exit(1)
    if args.build:
        if not build_quality_manifest():
            sys.exit(1)
    if not args.download and not args.build:
        parser.print_help()


if __name__ == "__main__":
    main()
