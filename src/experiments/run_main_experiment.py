"""
Trust Layer 主实验 (D6) — 相位级评估 + 真实质量报告 + Equal-Coverage

协议: configs/semifinal_main.yaml (semifinal_v1.5)
  - 1306 个 (sample_id, phase) 评估单元, 冻结预测
  - 质量报告来自 data/quality_manifest.csv (真实 SNR/断点/削波/缺道)
  - 冻结档案: configs/semifinal_main.yaml 的 experiment.frozen_profile
    (hydrophone_v2, v1.2 冻结) — 复现直接读取, 禁止重新选优
  - TrustConfig 参数集必须与 YAML trust_engine.parameter_set 一致, 否则拒绝运行
  - Equal-Coverage 点位从 YAML equal_coverage.points 读取
  - 门控: 以 threshold=100 运行一次后外部按 phase risk 排序选样 (与基线一致的 top-k)
  - no_pick 单元按 C 契约落 ABSTAIN, 永不进入 auto

EXP06 候选选择程序 (历史记录, 复现链不调用):
  - 仅通过 --profile-selection 显式重放: main 分片上比较 history_v1/hydrophone_v2,
    预声明准则 "50% 覆盖率点 Unsafe 更低者胜", 结果只写
    results/profile_selection_exp06.csv, 不覆盖任何正式产出

用法:
    python -m src.experiments.run_main_experiment                      # 冻结档案复现 (正式)
    python -m src.experiments.run_main_experiment --profile-selection  # EXP06 历史重放
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import warnings  # noqa: E402
warnings.filterwarnings("ignore")

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from src.experiments.phase_evaluation import (  # noqa: E402
    build_phase_units,
    load_records,
    phase_verdict,
)
from src.experiments.frozen_config import load_frozen_experiment  # noqa: E402
from src.trust_engine.schema import (  # noqa: E402
    AdapterStatus,
    ModelPrediction,
    ModelProfile,
    QualityReport,
    SampleMetadata,
    TrustConfig,
)
from src.trust_engine.data_evidence import evaluate_data_evidence  # noqa: E402
from src.trust_engine.model_suitability import evaluate_model_suitability  # noqa: E402
from src.trust_engine.single_model import evaluate_single_model_evidence  # noqa: E402
from src.trust_engine.physics import check_model_prediction  # noqa: E402
from src.trust_engine.multi_model import analyze_multi_model_consensus  # noqa: E402
from src.trust_engine.fusion import build_fusion_candidates  # noqa: E402
from src.trust_engine.reliability import evaluate_reliability  # noqa: E402

OUT_MAIN = ROOT / "results" / "main_results.csv"
OUT_BINS = ROOT / "results" / "risk_bins.csv"
OUT_EQ = ROOT / "results" / "equal_coverage_trust.csv"
OUT_FIG = ROOT / "figures" / "coverage_vs_unsafe.png"
OUT_SELECTION = ROOT / "results" / "profile_selection_exp06.csv"

# 候选适用性配置 (v2 选择程序)
PROFILE_CANDIDATES = {
    # 历史口径: PickBlue 严格要求 Z,N,E,H → 缺 E(13.6%)时被排除
    "history_v1": [
        ModelProfile(model_name="PhaseNet", required_channels=["Z", "N", "E"],
                     accepted_sampling_rates_hz=[100.0], resampling_supported=True,
                     required_preprocessing_version="obs_raw_v1"),
        ModelProfile(model_name="PickBlue", required_channels=["Z", "N", "E", "H"],
                     accepted_sampling_rates_hz=[100.0], resampling_supported=True,
                     required_preprocessing_version="obs_raw_v1"),
        ModelProfile(model_name="OBSTransformer", required_channels=["H"],
                     preferred_channels=["Z", "N", "E"],
                     accepted_sampling_rates_hz=[100.0], resampling_supported=True,
                     required_preprocessing_version="obs_raw_v1"),
        ModelProfile(model_name="EQTransformer", required_channels=["Z", "N", "E"],
                     accepted_sampling_rates_hz=[100.0], resampling_supported=True,
                     required_preprocessing_version="obs_raw_v1"),
    ],
    # 候选: PickBlue 实际输入契约以 H 为主 (OBS 权重, seisbench 对缺通道做掩码);
    # 冻结数据证明其在缺 E 样本上仍有预测且常为正确
    "hydrophone_v2": [
        ModelProfile(model_name="PhaseNet", required_channels=["Z", "N", "E"],
                     accepted_sampling_rates_hz=[100.0], resampling_supported=True,
                     required_preprocessing_version="obs_raw_v1"),
        ModelProfile(model_name="PickBlue", required_channels=["Z", "H"],
                     preferred_channels=["N", "E"],
                     accepted_sampling_rates_hz=[100.0], resampling_supported=True,
                     required_preprocessing_version="obs_raw_v1"),
        ModelProfile(model_name="OBSTransformer", required_channels=["H"],
                     preferred_channels=["Z", "N", "E"],
                     accepted_sampling_rates_hz=[100.0], resampling_supported=True,
                     required_preprocessing_version="obs_raw_v1"),
        ModelProfile(model_name="EQTransformer", required_channels=["Z", "N", "E"],
                     accepted_sampling_rates_hz=[100.0], resampling_supported=True,
                     required_preprocessing_version="obs_raw_v1"),
    ],
}
ADAPTERS = [
    AdapterStatus(model_name=m, loaded=True, run_succeeded=True,
                  output_comparable=True)
    for m in ("PhaseNet", "PickBlue", "OBSTransformer", "EQTransformer")
]


def load_quality() -> dict:
    rows = {}
    with open(ROOT / "data" / "quality_manifest.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows[row["sample_id"]] = row
    return rows


def load_split() -> dict:
    split = {}
    with open(ROOT / "data" / "manifest_phase.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            split[(row["sample_id"], row["phase"])] = row["split"]
    return split


def trust_per_record(record, quality_row, config, profiles, penalties=None):
    """单样本跑完整 Trust 链, 返回 ReliabilityResult."""
    preds = [
        ModelPrediction(
            sample_id=record["sample_id"], model_name=m, phase=ph,
            time_s=v[f"{ph}_pick"], score=v.get("confidence"),
            adapter_status="OK", preprocessing_version="obs_raw_v1",
            prediction_source="REAL_MODEL",
        )
        for m, v in record["predictions"].items()
        for ph in ("P", "S") if v.get(f"{ph}_pick") is not None
    ]
    if not preds:
        return None

    available = [c for c in (quality_row["available_channels"] or "").split("|") if c]
    missing = [c for c in (quality_row["missing_channels"] or "").split("|") if c]
    meta = SampleMetadata(sample_id=record["sample_id"], data_source="REAL",
                          preprocessing_version="obs_raw_v1")
    quality = QualityReport(
        available_channels=available or ["Z", "N", "E", "H"],
        missing_channels=missing,
        sampling_rate_hz=100.0,
        snr_db=float(quality_row["snr_db"]) if quality_row["snr_db"] else None,
        gap_ratio=float(quality_row["gap_ratio"]) if quality_row["gap_ratio"] else 0.0,
        clipping_ratio=float(quality_row["clipping_ratio"]) if quality_row["clipping_ratio"] else 0.0,
        source="REAL_CALCULATION",
    )
    data_ev = evaluate_data_evidence(quality, penalties)
    suits = evaluate_model_suitability(meta, quality, profiles, ADAPTERS)
    singles = evaluate_single_model_evidence(preds)
    physics = []
    seen = set()
    for p in preds:
        if p.model_name in seen:
            continue
        seen.add(p.model_name)
        p_ps = [x for x in preds if x.model_name == p.model_name and x.phase == "P"]
        s_ps = [x for x in preds if x.model_name == p.model_name and x.phase == "S"]
        physics.append(check_model_prediction(
            p_ps[0] if p_ps else None, s_ps[0] if s_ps else None,
            config, target_id=p.model_name,
        ))
    cons = analyze_multi_model_consensus(preds, suits, physics, config)
    fusions = build_fusion_candidates(preds, cons)
    return evaluate_reliability(
        meta, quality, profiles, preds,
        config, data_ev, suits, singles, physics, cons, fusions,
    )


def build_unit_rows(records, units, quality_map, profiles, config, record_map,
                    penalties=None):
    """逐单元产出决策与判定."""
    per_record = {}
    for i, record in enumerate(records):
        per_record[record["sample_id"]] = trust_per_record(
            record, quality_map[record["sample_id"]], config, profiles, penalties)
        if (i + 1) % 300 == 0:
            print(f"    Trust 链进度 {i + 1}/{len(records)}", flush=True)

    rows = []
    for unit in units:
        if not unit["primary_inclusion"]:
            continue
        sid, phase = unit["sample_id"], unit["phase"]
        result = per_record[sid]
        decision = (result.phase_decisions.get(phase) if result else None)
        action = decision.action if decision else "ABSTAIN"
        risk = decision.risk_score if decision else 50.0
        time_s = None
        if decision is not None:
            if decision.action == "FUSE" and decision.fused_pick is not None:
                time_s = decision.fused_pick.fused_time_s
            elif decision.selected_time_s is not None and decision.selected_time_s >= 0:
                time_s = decision.selected_time_s
            elif decision.selected_model:
                preds = (record_map[sid]["predictions"]
                         .get(decision.selected_model) or {})
                time_s = preds.get(f"{phase}_pick")
        auto_capable = action in ("ACCEPT", "ROUTE", "FUSE")
        verdict = phase_verdict(time_s if auto_capable else None,
                                unit["reference_time_s"], phase)
        rows.append({
            "sample_id": sid, "phase": phase,
            "station": unit["station"],
            "split": unit.get("split", ""),
            "reference_time_s": unit["reference_time_s"],
            "action": action, "risk": round(risk, 2),
            "selected_time_s": "" if time_s is None else round(time_s, 3),
            "auto_capable": auto_capable,
            "verdict": verdict,
        })
    return rows


def unsafe_at_coverage(rows, target_pct):
    """top-k 精确覆盖率下的 Unsafe (%), 与基线协议一致."""
    output_rows = [r for r in rows if r["verdict"] in ("correct", "wrong")]
    output_sorted = sorted(output_rows,
                           key=lambda r: (r["risk"], r["sample_id"], r["phase"]))
    k = int(round(target_pct / 100 * len(rows)))
    k = min(k, len(output_sorted))
    accepted = {(r["sample_id"], r["phase"]) for r in output_sorted[:k]}
    auto = wrong = 0
    for row in rows:
        if (row["sample_id"], row["phase"]) in accepted:
            auto += 1
            if row["verdict"] == "wrong":
                wrong += 1
    return wrong / auto * 100 if auto else float("inf"), len(output_rows) / len(rows) * 100


def main():
    frozen_profile, points, param_set = load_frozen_experiment()
    if frozen_profile not in PROFILE_CANDIDATES:
        raise ValueError(f"冻结档案 {frozen_profile} 不在候选定义中 — 冻结配置失效")

    records = load_records()
    quality_map = load_quality()
    split_map = load_split()
    units = build_phase_units(records)
    for unit in units:
        unit["split"] = split_map.get((unit["sample_id"], unit["phase"]), "main")
    record_map = {r["sample_id"]: r for r in records}

    config = TrustConfig()
    if config.config_version != param_set:
        raise ValueError(
            f"TrustConfig 参数集 {config.config_version} 与冻结配置 "
            f"trust_engine.parameter_set={param_set} 不一致 — 冻结配置失效, 拒绝运行")
    config.automatic_risk_threshold = 100.0  # top-k 协议: 全量产出后按风险排序对齐覆盖率点

    main_units = [u for u in units if u["split"] == "main" and u["primary_inclusion"]]
    holdout_units = [u for u in units if u["split"] == "holdout" and u["primary_inclusion"]]
    print(f"评估单元: main={len(main_units)}, holdout={len(holdout_units)}, "
          f"共 {len(main_units) + len(holdout_units)}")
    print(f"冻结档案: {frozen_profile} "
          f"(configs/semifinal_main.yaml experiment.frozen_profile)")
    print("复现纪律: 直接读取冻结档案, 不重新比较候选 "
          "(EXP06 历史程序见 --profile-selection)")

    # ── holdout 一致性确认 (冻结档案, 不作选择) ──
    print(f"\nholdout 一致性确认 (冻结档案 {frozen_profile})...")
    hold_rows = build_unit_rows(records, holdout_units, quality_map,
                                PROFILE_CANDIDATES[frozen_profile], config,
                                record_map)
    h_unsafe, h_ceiling = unsafe_at_coverage(hold_rows, 50)
    if h_ceiling + 1e-9 < 50.0:
        print(f"  holdout: 50% 点位 NOT_EVALUABLE (天花板 {h_ceiling:.1f}%)")
    else:
        print(f"  holdout: 50%覆盖率 Unsafe = {h_unsafe:.1f}% | "
              f"天花板 = {h_ceiling:.1f}%")

    # ── 正式产出 (冻结档案, 全单元) ──
    print(f"\n正式产出 ({frozen_profile}, 全部单元)...")
    final_rows = build_unit_rows(records, units, quality_map,
                                 PROFILE_CANDIDATES[frozen_profile], config,
                                 record_map)
    write_outputs(final_rows, frozen_profile, points)


def profile_selection_history():
    """EXP06 预注册候选选择程序 (历史重放, 复现链不调用).

    在 main 分片上比较 history_v1 与 hydrophone_v2, 按预声明准则
    "50% 覆盖率点 Unsafe 更低者胜" 报告结果; 只写历史记录文件, 不覆盖正式产出。
    """
    records = load_records()
    quality_map = load_quality()
    split_map = load_split()
    units = build_phase_units(records)
    for unit in units:
        unit["split"] = split_map.get((unit["sample_id"], unit["phase"]), "main")
    record_map = {r["sample_id"]: r for r in records}
    config = TrustConfig()
    config.automatic_risk_threshold = 100.0
    main_units = [u for u in units if u["split"] == "main" and u["primary_inclusion"]]

    print("EXP06 历史程序重放 (预注册准则: main 50% 点 Unsafe 更低者胜)")
    results_by_candidate = {}
    for name, profiles in PROFILE_CANDIDATES.items():
        rows = build_unit_rows(records, main_units, quality_map, profiles, config,
                               record_map)
        unsafe50, ceiling = unsafe_at_coverage(rows, 50)
        results_by_candidate[name] = (unsafe50, ceiling)
        print(f"  {name}: 50%覆盖率 Unsafe = {unsafe50:.1f}% | "
              f"天花板 = {ceiling:.1f}%")
    winner = min(results_by_candidate, key=lambda n: results_by_candidate[n][0])
    print(f"==> main 上胜者: {winner} "
          f"(Unsafe50 = {results_by_candidate[winner][0]:.1f}%)")
    print("注意: 本结果为历史记录; 正式复现直接使用 YAML 冻结档案, 不再选优")

    with open(OUT_SELECTION, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate", "unsafe50_pct", "ceiling_pct", "decided"])
        for name, (unsafe, ceiling) in results_by_candidate.items():
            writer.writerow([name, f"{unsafe:.2f}", f"{ceiling:.2f}",
                             "winner" if name == winner else ""])
    print(f"✓ 历史记录: {OUT_SELECTION}")


def write_outputs(unit_rows, profile_name, points):
    with open(OUT_MAIN, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(unit_rows[0].keys()))
        writer.writeheader()
        writer.writerows(unit_rows)
    print(f"✓ {OUT_MAIN} ({len(unit_rows)} 行)")

    output_rows = [r for r in unit_rows if r["verdict"] in ("correct", "wrong")]
    output_sorted = sorted(output_rows,
                           key=lambda r: (r["risk"], r["sample_id"], r["phase"]))
    print(f"Trust 覆盖率天花板: {len(output_rows)}/{len(unit_rows)} "
          f"= {len(output_rows)/len(unit_rows)*100:.1f}%")

    print(f"\n{'目标Cov':>8} {'有效阈值':>8} {'实际Cov':>8} {'Unsafe':>8} {'Burden':>8} {'拦截率':>8} {'状态':>24}")
    eq_rows = []
    trust_curve = {"cov": [], "unsafe": []}
    for target in points:
        requested_k = int(round(target / 100 * len(unit_rows)))
        feasible = requested_k <= len(output_sorted)
        k = min(requested_k, len(output_sorted))
        accepted = {(r["sample_id"], r["phase"]) for r in output_sorted[:k]}
        eff_threshold = output_sorted[k - 1]["risk"] if k else 0.0
        auto_correct = auto_wrong = intercepted = total_errors = 0
        for row in unit_rows:
            is_error = row["verdict"] in ("wrong", "no_pick")
            if is_error:
                total_errors += 1
            if (row["sample_id"], row["phase"]) in accepted:
                if row["verdict"] == "correct":
                    auto_correct += 1
                elif row["verdict"] == "wrong":
                    auto_wrong += 1
            elif is_error:
                intercepted += 1
        auto = auto_correct + auto_wrong
        cov = auto / len(unit_rows) * 100
        unsafe = auto_wrong / auto * 100 if auto else 0.0
        burden = (len(unit_rows) - auto) / len(unit_rows) * 100
        inter = intercepted / total_errors * 100 if total_errors else 0.0
        status = "COMPARABLE" if feasible else "NOT_COMPARABLE_AT_TARGET"
        eq_rows.append({
            "strategy": "TrustLayer", "target_coverage_pct": target,
            "coverage_pct": round(cov, 2),
            "unsafe_output_rate_pct": round(unsafe, 2) if feasible else "",
            "review_burden_pct": round(burden, 2),
            "error_interception_rate_pct": round(inter, 2) if feasible else "",
            "risk_threshold": round(eff_threshold, 2) if feasible else "",
            "profile": profile_name,
            "feasible": str(feasible).lower(),
            "comparison_status": status,
        })
        if feasible:
            trust_curve["cov"].append(cov)
            trust_curve["unsafe"].append(unsafe)
            print(f"{target:>7}% {eff_threshold:>8.2f} {cov:>7.1f}% {unsafe:>7.1f}% "
                  f"{burden:>7.1f}% {inter:>7.1f}% {status:>24}")
        else:
            print(f"{target:>7}% {'—':>8} {cov:>7.1f}% {'—':>8} {burden:>7.1f}% "
                  f"{'—':>8} NOT_EVALUABLE (天花板 {len(output_sorted)/len(unit_rows)*100:.1f}%)")

    with open(OUT_EQ, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(eq_rows[0].keys()))
        writer.writeheader()
        writer.writerows(eq_rows)
    print(f"✓ {OUT_EQ}")

    # 风险分箱 (仅有效输出单元, 主图2 数据)
    bins = [(0, 10), (10, 20), (20, 30), (30, 40), (40, 51)]
    bin_rows = []
    for lo, hi in bins:
        members = [r for r in output_rows if lo <= r["risk"] < hi]
        errors = sum(1 for r in members if r["verdict"] == "wrong")
        reliable = len(members) >= 10
        bin_rows.append({
            "risk_bin": f"{lo}-{hi - 1}", "n": len(members),
            "wrong": errors,
            "error_rate_pct": (round(errors / len(members) * 100, 2)
                               if members and reliable else ""),
            "reliable": str(reliable).lower(),
        })
    with open(OUT_BINS, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(bin_rows[0].keys()))
        writer.writeheader()
        writer.writerows(bin_rows)
    print(f"✓ {OUT_BINS}")
    for row in bin_rows:
        flag = "" if row["reliable"] == "true" else " (n<10 不可靠)"
        print(f"  risk {row['risk_bin']:>6}: n={row['n']:4d} "
              f"错误率={row['error_rate_pct'] or '—'}{flag}")

    # 主图更新 (跳过不可达点位行)
    base_csv = ROOT / "results" / "baseline_results.csv"
    strategies = {}
    with open(base_csv, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row["strategy"]
            if row.get("feasible", "true").lower() != "true":
                continue
            strategies.setdefault(name, {"cov": [], "unsafe": []})
            strategies[name]["cov"].append(float(row["coverage_pct"]))
            strategies[name]["unsafe"].append(float(row["unsafe_output_rate_pct"]))
    colors = {
        "Single-PhaseNet": "#9E9E9E", "Single-PickBlue": "#9E9E9E",
        "Single-OBSTransformer": "#607D8B", "MaxConf": "#FF9800",
        "Voting": "#2196F3", "Traditional-STA/LTA": "#795548",
        "Random": "#F44336", "TrustLayer": "#4CAF50",
    }
    fig, ax = plt.subplots(figsize=(10, 6))
    for name, data in strategies.items():
        ax.plot(data["cov"], data["unsafe"], "o-", label=name,
                color=colors.get(name, "#999999"), linewidth=2, markersize=6)
    ax.plot(trust_curve["cov"], trust_curve["unsafe"], "o-",
            label="Trust Layer", color="#4CAF50", linewidth=3, markersize=9)
    ax.set_xlabel("Coverage (%)")
    ax.set_ylabel("Unsafe Output Rate (%)")
    ax.set_title("Equal-Coverage Comparison on 1306 Phase Units "
                 f"(semifinal_v1.5, profile={profile_name})")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_FIG, dpi=150)
    plt.close(fig)
    print(f"✓ {OUT_FIG}")


if __name__ == "__main__":
    if "--profile-selection" in sys.argv:
        profile_selection_history()
    else:
        main()
