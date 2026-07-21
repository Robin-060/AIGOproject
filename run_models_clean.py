import os, sys, json
from pathlib import Path

CACHE_ROOT = Path("D:/seisbench_cache")
os.environ["SEISBENCH_CACHE_ROOT"] = str(CACHE_ROOT)

import seisbench
seisbench.cache_root = CACHE_ROOT

from obspy import Stream, Trace, UTCDateTime
from seisbench.data import OBS
from seisbench.models import PhaseNet, OBSTransformer
from seisbench.models.pickblue import PickBlue


def find_available_chunks():
    data_dir = CACHE_ROOT / "datasets" / "obs"
    if not data_dir.exists():
        print(f"  [ERROR] Data dir not found: {data_dir}", flush=True)
        return []
    chunks_seen = set()
    for f in data_dir.iterdir():
        if not f.is_file():
            continue
        name = f.name
        if name.startswith("metadata") and name.endswith(".csv"):
            chunk = name.replace("metadata", "").replace(".csv", "")
            chunks_seen.add(chunk)
    available = []
    for chunk in sorted(chunks_seen):
        meta_file = f"metadata{chunk}.csv"
        wf_file = f"waveforms{chunk}.hdf5"
        if (data_dir / meta_file).exists() and (data_dir / wf_file).exists():
            available.append(chunk)
    return available


def init_models():
    print("  Loading models...", flush=True)
    phasenet = PhaseNet.from_pretrained("obs")
    pickblue = PickBlue(base="phasenet")
    obst = OBSTransformer.from_pretrained("obst2024")
    print("  Models ready\n", flush=True)
    return phasenet, pickblue, obst


def get_stream(obs_dataset, trace_idx):
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
    return Stream(traces=traces)


def classify(model, model_name, stream):
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


def main():
    trace_idx = 0
    chunk_filter = None
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--trace" and i + 1 < len(args):
            trace_idx = int(args[i + 1])
            i += 2
        elif args[i] == "--chunk" and i + 1 < len(args):
            chunk_filter = args[i + 1]
            i += 2
        else:
            i += 1

    print("=" * 60)
    print("SeisBench OBS inference")
    print("=" * 60)
    print(f"Cache: {CACHE_ROOT}")
    print()
    print("Scanning for available chunks...", flush=True)
    available = find_available_chunks()
    if not available:
        print("No complete chunks found.")
        print(f"Check: {CACHE_ROOT / 'datasets' / 'obs'}")
        return
    print(f"Available chunks ({len(available)}): {available}")

    if chunk_filter:
        if chunk_filter not in available:
            print(f"Chunk '{chunk_filter}' not available. Try: {available}")
            return
        load_chunks = [chunk_filter]
    else:
        load_chunks = available

    print(f"Loading chunks: {load_chunks}")
    print("Loading OBS dataset...", flush=True)
    obs = OBS(chunks=load_chunks)
    n = len(obs)
    print(f"  Total traces: {n}")

    if trace_idx >= n:
        print(f"  ERROR: index {trace_idx} out of range (0-{n-1})")
        return

    print()
    print("=" * 60)
    print(f"Trace #{trace_idx}")
    print("=" * 60)

    print("Extracting waveform...", flush=True)
    stream = get_stream(obs, trace_idx)
    _, meta = obs.get_sample(trace_idx)
    sr = float(meta["trace_sampling_rate_hz"])
    duration = stream[0].stats.npts / sr
    print(f"  Station: {meta.get('trace_station', '?')}, SR: {sr} Hz, Duration: {duration:.1f}s")
    print()

    phasenet, pickblue, obst = init_models()

    print("=" * 60)
    print("Results")
    print("=" * 60)

    json_out = {}
    for name, model in [
        ("PhaseNet", phasenet),
        ("PickBlue", pickblue),
        ("OBSTransformer", obst),
    ]:
        print(f"--- {name} ---")
        r = classify(model, name, stream)
        json_out[name] = r
        parts = []
        for k in ("P_pick", "S_pick", "confidence"):
            v = r.get(k)
            if v is not None:
                parts.append(f'"{k}":{v}')
        if parts:
            print(f"  {name}: " + ", ".join(parts))
        else:
            print(f"  {name}: [no picks]")

    print()
    print("=" * 60)
    print("Unified JSON:")
    print(json.dumps(json_out, indent=2))
    print("Done.")


if __name__ == "__main__":
    main()
