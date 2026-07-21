#!/usr/bin/env python3
"""
Download OBS Dataset & Models Script
共34 GB，建议更改在空间宽裕的路径 

"""

import os
import sys
import time
import shutil
from pathlib import Path
import requests

CACHE_ROOT = Path("D:/seisbench_cache")
DATASET_DIR = CACHE_ROOT / "datasets" / "obs"
ZENODO_RECORD_ID = "10277799"

OBS_CHUNKS = [
    "201805", "201806", "201807", "201808",
    "201809", "201810", "201811", "201812",
    "201901", "201902", "201903", "201904",
    "201905", "201906", "201907", "201908",
    "000000",
]


def download_file(url, target_path, desc=""):

    MAX_RETRIES = 5
    RETRY_DELAY = 5

    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # ?????????? -> ??
    if target_path.exists() and target_path.stat().st_size > 0:
        print(f"  [??] {desc} - ?????")
        return True

    temp_path = target_path.with_suffix(target_path.suffix + ".part")
    existing_size = temp_path.stat().st_size if temp_path.exists() else 0

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            headers = {}
            if existing_size > 0:
                headers["Range"] = f"bytes={existing_size}-"

            with requests.get(
                url, stream=True, timeout=(60, 300), headers=headers
            ) as resp:
                if resp.status_code == 416:
                    # Range not satisfiable -> file already complete
                    os.replace(str(temp_path), str(target_path))
                    print(f"  [??] {desc}")
                    return True

                if resp.status_code not in (200, 206):
                    print(f"  [??] {desc} - HTTP {resp.status_code}")
                    return False

                total_size = int(resp.headers.get("Content-Length", 0))
                if resp.status_code == 206:
                    total_size = existing_size + total_size

                mode = "ab" if (resp.status_code == 206 and existing_size > 0) else "wb"
                downloaded = existing_size if mode == "ab" else 0

                with open(temp_path, mode) as f:
                    for chunk in resp.iter_content(chunk_size=1024*1024):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0 and desc:
                                pct = downloaded * 100 / total_size
                                mb_d = downloaded / 1024 / 1024
                                mb_t = total_size / 1024 / 1024
                                sys.stdout.write(f"\r  [{desc}] {mb_d:.1f}/{mb_t:.1f} MB ({pct:.1f}%)")
                                sys.stdout.flush()

                if desc:
                    print()

                if total_size > 0 and downloaded < total_size:
                    raise IOError(f"?????: {downloaded} < {total_size} ??")

                # ? os.replace ???????? (Windows ??)
                os.replace(str(temp_path), str(target_path))
                return True

        except Exception as e:
            msg = str(e)
            print(f"")
            print(f"  [?? {attempt}/{MAX_RETRIES}] {desc}")
            print(f"    ??: {msg}")
            if attempt < MAX_RETRIES:
                existing_size = temp_path.stat().st_size if temp_path.exists() else 0
                wait_time = RETRY_DELAY * (2 ** (attempt - 1))
                print(f"    ?? {wait_time} ????...")
                time.sleep(wait_time)
            else:
                print(f"  [??] {desc} - ?? {MAX_RETRIES} ?????")
                return False

    return False


def download_obs_from_zenodo():
    print("=" * 60)
    print("?? 1: ?? OBS ??? (? Zenodo)")
    print(f"????: {DATASET_DIR}")
    print(f"?????: ~34 GB (? {len(OBS_CHUNKS)} ? chunk)")
    print("=" * 60)

    DATASET_DIR.mkdir(parents=True, exist_ok=True)

    api_url = f"https://zenodo.org/api/records/{ZENODO_RECORD_ID}"
    print(f"")
    print(f"??????: {api_url}")
    resp = requests.get(api_url, timeout=30)
    if resp.status_code != 200:
        print(f"????????: HTTP {resp.status_code}")
        return False

    record = resp.json()
    files = record.get("files", [])
    print(f"Zenodo ????? {len(files)} ???")

    obs_files = {}
    for f in files:
        key = f["key"]
        if key.startswith("metadata") or key.startswith("waveforms"):
            obs_files[key] = f

    print(f"OBS ?????: {len(obs_files)} ?")

    success_count = 0
    fail_count = 0

    print("")
    print("--- ???: ??????? (???) ---")
    for chunk in OBS_CHUNKS:
        metadata_name = f"metadata{chunk}.csv"
        if metadata_name in obs_files:
            dl_url = obs_files[metadata_name]["links"]["self"]
            target = DATASET_DIR / metadata_name
            if download_file(dl_url, target, desc=metadata_name):
                success_count += 1
            else:
                fail_count += 1

    print("")
    print("--- ???: ?????? (???) ---")
    for chunk in OBS_CHUNKS:
        waveform_name = f"waveforms{chunk}.hdf5"
        if waveform_name in obs_files:
            dl_url = obs_files[waveform_name]["links"]["self"]
            target = DATASET_DIR / waveform_name
            if download_file(dl_url, target, desc=waveform_name):
                success_count += 1
            else:
                fail_count += 1

    chunks_path = DATASET_DIR / "chunks"
    if not chunks_path.exists():
        with open(chunks_path, "w", encoding="utf-8") as f:
            for chunk in OBS_CHUNKS:
                f.write(chunk + "")
        print(f"")
        print(f"??? chunks ??: {chunks_path}")

    print(f"")
    print(f"????: {success_count} ??, {fail_count} ??")
    return fail_count == 0


def download_models():
    print("")
    print("=" * 60)
    print("?? 2: ???????")
    print("=" * 60)

    os.environ["SEISBENCH_CACHE_ROOT"] = str(CACHE_ROOT)

    import seisbench
    seisbench.cache_root = CACHE_ROOT

    import seisbench.models as sbm

    models_info = [
        ("PhaseNet (obs)", lambda: sbm.PhaseNet.from_pretrained("obs")),
        ("PickBlue (phasenet base)", lambda: sbm.PickBlue(base="phasenet")),
        ("OBSTransformer (obst2024)", lambda: sbm.OBSTransformer.from_pretrained("obst2024")),
    ]

    for name, loader in models_info:
        print(f"")
        print(f"--- ?? {name} ---")
        try:
            model = loader()
            print(f"  [??] {name}")
            print(f"  ????: {type(model).__name__}")
        except Exception as e:
            print(f"  [??] {name} - {e}")


def verify_dataset():
    print("")
    print("=" * 60)
    print("?? 3: ?? OBS ???")
    print("=" * 60)

    os.environ["SEISBENCH_CACHE_ROOT"] = str(CACHE_ROOT)

    import seisbench
    seisbench.cache_root = CACHE_ROOT

    from seisbench.data import OBS

    try:
        obs = OBS()
        print(f"  [??] OBS ???????")
        print(f"  ?? {len(obs)} ?????")
        print(f"  ???: {obs.chunks}")
        print(f"  ????: {obs.path}")
        return True
    except Exception as e:
        print(f"  [??] ???????: {e}")
        return False


def main():
    start_time = time.time()

    print("=" * 60)
    print("SeisBench OBS ??????????")
    print("=" * 60)
    print()
    print(f"?????: {CACHE_ROOT}")
    print(f"?????: {DATASET_DIR}")
    print()

    dataset_ok = download_obs_from_zenodo()
    download_models()

    if dataset_ok:
        verify_dataset()

    elapsed = time.time() - start_time
    print(f"")
    print(f"???: {elapsed/60:.1f} ??")
    print("")
    print("???????")


if __name__ == "__main__":
    main()
