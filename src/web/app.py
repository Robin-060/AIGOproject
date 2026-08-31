"""Interactive Streamlit front end for data-team result JSON files."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

# `src.*` imports require the repo root on sys.path; Streamlit Cloud does not
# add it automatically (a local `python -m streamlit run` does).
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.signal.io import WaveformBundle, read_waveform_bytes
from src.signal.preprocessing import PreprocessConfig, preprocess_waveform
from src.signal.stalta import classic_sta_lta, detect_triggers
from src.signal.triage import classify_event
from src.trust_engine.data_evidence import evaluate_data_evidence
from src.trust_engine.model_suitability import evaluate_model_suitability
from src.trust_engine.multi_model import analyze_multi_model_consensus
from src.trust_engine.physics import check_model_prediction
from src.trust_engine.pipeline import load_from_mapping, run_pipeline, _load_config
from src.trust_engine.schema import DEMO_CONFIG
from src.trust_engine.single_model import evaluate_single_model_evidence


NOISE_CURVE = ROOT / "docs" / "experiments" / "noise_curve.png"
NOISE_SUMMARY = ROOT / "docs" / "experiments" / "noise_summary_seisbench.csv"
STALTA_SUMMARY = ROOT / "docs" / "experiments" / "stalta_summary.json"
CPU_BENCHMARK = ROOT / "docs" / "experiments" / "cpu_benchmark.json"
BASELINE_CHARTS = (
    ROOT / "docs" / "experiments" / "real_baseline.png",
    ROOT / "docs" / "experiments" / "real_ablation.png",
    ROOT / "docs" / "experiments" / "calibration_curve.png",
    ROOT / "docs" / "experiments" / "risk_calibration_curve.png",
)

STATUS_LABELS = {
    "COMPATIBLE": "兼容",
    "DEGRADED": "降级可用",
    "INCOMPATIBLE": "不兼容",
    "INLIER": "共识内",
    "OUTLIER": "离群",
    "NOT_COMPARABLE": "不可比较",
    "ACCEPT": "接受",
    "ROUTE": "路由",
    "FUSE": "融合",
    "ABSTAIN": "拒绝自动决策",
}


def run_analysis(
    raw: Dict[str, Any],
    risk_threshold: float = 10.0,
    p_tolerance: float = 0.34,
    s_tolerance: float = 0.51,
    data_weight: float = 30.0,
) -> Dict[str, Any]:
    """Pure analysis entry point used by the UI and integration tests."""
    return analyze_payload(
        raw,
        risk_threshold,
        p_tolerance,
        s_tolerance,
        data_weight,
    )


def _to_dict(value: Any) -> Dict[str, Any]:
    return asdict(value)


@st.cache_data(show_spinner=False)
def analyze_payload(
    raw: Dict[str, Any],
    risk_threshold: float,
    p_tolerance: float,
    s_tolerance: float,
    data_weight: float,
) -> Dict[str, Any]:
    inputs = load_from_mapping(raw)

    config = _load_config()
    config.automatic_risk_threshold = risk_threshold
    config.consensus_tolerance_p_s = p_tolerance
    config.consensus_tolerance_s_s = s_tolerance
    config.data_weight = data_weight

    result = run_pipeline(**inputs, config=config)

    data_evidence = evaluate_data_evidence(inputs["quality"])
    suitabilities = evaluate_model_suitability(
        inputs["metadata"],
        inputs["quality"],
        inputs["profiles"],
        inputs["adapter_statuses"],
    )
    single_evidence = evaluate_single_model_evidence(inputs["predictions"])
    physics = []
    for prediction in inputs["predictions"]:
        if prediction.phase != "P":
            continue
        s_prediction = next(
            (
                candidate
                for candidate in inputs["predictions"]
                if candidate.phase == "S"
                and candidate.model_name == prediction.model_name
            ),
            None,
        )
        physics.append(check_model_prediction(prediction, s_prediction, DEMO_CONFIG))
    consensus = analyze_multi_model_consensus(
        inputs["predictions"], suitabilities, physics
    )

    return {
        "inputs": inputs,
        "result": json.loads(result.to_json()),
        "data_evidence": _to_dict(data_evidence),
        "suitabilities": [_to_dict(item) for item in suitabilities],
        "single_evidence": [_to_dict(item) for item in single_evidence],
        "physics": [_to_dict(item) for item in physics],
        "consensus": [_to_dict(item) for item in consensus],
    }


def _model_rows(raw: Dict[str, Any], analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    adapters = {
        item["model_name"]: item for item in raw.get("adapter_statuses", [])
    }
    assessments = {
        item["model_name"]: item
        for item in analysis["result"].get("model_assessments", [])
    }
    suitabilities = {
        item["model_name"]: item for item in analysis["suitabilities"]
    }
    rows = []
    for name in raw.get("model_profiles", {}):
        adapter = adapters.get(name, {})
        assessment = assessments.get(name, {})
        suitability = suitabilities.get(name, {})
        rows.append(
            {
                "模型": name,
                "加载": "✓" if adapter.get("loaded") else "✗",
                "运行": "✓" if adapter.get("run_succeeded") else "✗",
                "可比较": "✓" if adapter.get("output_comparable") else "✗",
                "适用性": STATUS_LABELS.get(
                    suitability.get("suitability_level"),
                    suitability.get("suitability_level", "未知"),
                ),
                "共识角色": STATUS_LABELS.get(
                    assessment.get("consensus_role"),
                    assessment.get("consensus_role", "未知"),
                ),
                "风险": assessment.get("model_risk_score", 0),
                "原因": "、".join(suitability.get("reasons", [])) or "无",
            }
        )
    return rows


def _render_overview(raw: Dict[str, Any], analysis: Dict[str, Any]) -> None:
    result = analysis["result"]
    metadata = raw["sample_metadata"]
    quality = raw["quality_report"]

    cols = st.columns(5)
    cols[0].metric("样本", metadata.get("sample_id", "—"))
    cols[1].metric("总体风险", f"{result['overall_risk_score']:.1f} / 100")
    cols[2].markdown("**风险等级**")
    cols[2].markdown(_risk_badge(result["overall_risk_level"]), unsafe_allow_html=True)
    cols[3].metric("P/S 完整性", result["final_pair_status"])
    cols[4].metric("证据状态", result["evidence_status"])

    st.subheader("数据质量")
    quality_cols = st.columns(5)
    quality_cols[0].metric("采样率", f"{quality.get('sampling_rate_hz', 0):g} Hz")
    quality_cols[1].metric("SNR", f"{quality.get('snr_db', 0):g} dB")
    quality_cols[2].metric("断点率", f"{quality.get('gap_ratio', 0):.2%}")
    quality_cols[3].metric("削波率", f"{quality.get('clipping_ratio', 0):.2%}")
    quality_cols[4].metric(
        "可用通道", "/".join(quality.get("available_channels", [])) or "—"
    )

    if quality.get("missing_channels"):
        st.warning("缺失通道：" + "、".join(quality["missing_channels"]))
    else:
        st.success("必需通道完整。")

    triage = classify_event(result, quality)
    st.info(f"事件分流：{triage['display']} · {triage['basis']}（透明规则，并非训练分类器）")


def waveform_frame(bundle: WaveformBundle, max_points: int = 6000) -> pd.DataFrame:
    """Long-form, downsampled frame shared by UI and tests."""
    stride = max(1, bundle.data.shape[1] // max_points)
    records = []
    times = bundle.time_s[::stride]
    for channel, values in zip(bundle.channels, bundle.data):
        records.extend(
            {"时间 (s)": float(time), "振幅": float(value), "通道": channel}
            for time, value in zip(times, values[::stride])
        )
    return pd.DataFrame(records)


def _render_waveform(raw: Dict[str, Any], bundle: WaveformBundle) -> None:
    st.subheader("波形与拾取结果")
    upper_limit = max(0.2, float(min(40.0, bundle.sampling_rate_hz / 2 - 0.1)))
    default_low = max(0.1, min(1.0, upper_limit / 3))
    default_high = max(default_low + 0.1, min(20.0, upper_limit))
    low, high = st.slider(
        "带通范围 (Hz)",
        min_value=0.1,
        max_value=upper_limit,
        value=(default_low, default_high),
        step=0.1,
    )
    processed, report = preprocess_waveform(
        bundle,
        PreprocessConfig(bandpass_low_hz=low, bandpass_high_hz=high),
    )
    original_tab, processed_tab, trigger_tab = st.tabs(["原始波形", "预处理后", "STA/LTA 基线"])
    with original_tab:
        st.line_chart(waveform_frame(bundle), x="时间 (s)", y="振幅", color="通道")
    with processed_tab:
        st.line_chart(waveform_frame(processed), x="时间 (s)", y="振幅", color="通道")
        st.json(report)
    with trigger_tab:
        vertical_index = next((i for i, name in enumerate(processed.channels) if name == "Z"), 0)
        ratio = classic_sta_lta(processed.data[vertical_index], processed.sampling_rate_hz)
        triggers = detect_triggers(ratio, processed.sampling_rate_hz)
        stride = max(1, len(ratio) // 6000)
        st.line_chart(
            pd.DataFrame({"时间 (s)": processed.time_s[::stride], "STA/LTA": ratio[::stride]}),
            x="时间 (s)",
            y="STA/LTA",
        )
        st.dataframe(pd.DataFrame([trigger.__dict__ for trigger in triggers]), hide_index=True, use_container_width=True)

    picks = pd.DataFrame(raw.get("model_predictions", []))
    if not picks.empty:
        st.subheader("模型拾取位置")
        import matplotlib.pyplot as plt

        figure, axes = plt.subplots(len(processed.channels), 1, figsize=(12, 2.1 * len(processed.channels)), sharex=True)
        if len(processed.channels) == 1:
            axes = [axes]
        colors = {"P": "#dc2626", "S": "#2563eb"}
        for axis, channel, values in zip(axes, processed.channels, processed.data):
            axis.plot(processed.time_s, values, color="#334155", linewidth=0.55)
            for item in picks.to_dict("records"):
                axis.axvline(float(item["time_s"]), color=colors.get(item.get("phase"), "#f59e0b"), alpha=0.35, linewidth=1)
            axis.set_ylabel(channel)
            axis.grid(alpha=0.15)
        axes[-1].set_xlabel("Time (s)")
        figure.tight_layout()
        st.pyplot(figure, clear_figure=True)
        st.caption("红线为各模型 P 拾取，蓝线为各模型 S 拾取；相近竖线表示模型共识。")
        st.dataframe(picks[["model_name", "phase", "time_s", "score"]], hide_index=True, use_container_width=True)


RISK_COLORS = {"LOW": "#2E7D32", "MEDIUM": "#F57F17", "HIGH": "#C62828"}


def _risk_badge(level: str) -> str:
    """彩色风险等级徽标"""
    color = RISK_COLORS.get(level, "#666666")
    return (f"<span style='background:{color}; color:white; "
            f"padding:2px 10px; border-radius:10px; font-weight:bold'>{level}</span>")


def _render_decisions(analysis: Dict[str, Any]) -> None:
    st.subheader("P / S 最终决策")
    columns = st.columns(2)
    for column, phase in zip(columns, ("P", "S")):
        decision = analysis["result"]["phase_decisions"][phase]
        action = STATUS_LABELS.get(decision["action"], decision["action"])
        with column:
            st.markdown(f"#### {phase} 波 · {action}")
            st.metric("选定时间", f"{decision['selected_time_s']:.3f} s")
            st.caption(
                f"风险 {decision['risk_score']:.1f}（{decision['risk_level']}）"
            )
            st.markdown(_risk_badge(decision["risk_level"]), unsafe_allow_html=True)
            contributors = (decision.get("fused_pick") or {}).get("contributors", [])
            if contributors:
                st.write("融合模型：" + "、".join(contributors))
            elif decision.get("selected_model"):
                st.write("选定模型：" + decision["selected_model"])
            st.write("原因码：" + "、".join(decision.get("reason_codes", [])))


def _render_risk(analysis: Dict[str, Any]) -> None:
    st.subheader("四证据风险分解")
    labels = {
        "data": "数据质量",
        "single_model": "单模型置信",
        "multi_model": "多模型一致性",
        "physics": "物理约束",
    }
    budgets = {"data": 30, "single_model": 24, "multi_model": 37, "physics": 40}

    breakdown = analysis["result"]["evidence_breakdown"]
    rows = []
    for key, label in labels.items():
        p_val = breakdown.get("P", {}).get(key, 0.0)
        s_val = breakdown.get("S", {}).get(key, 0.0)
        rows.append({
            "证据": label,
            "P 风险分": p_val,
            "S 风险分": s_val,
            "预算": budgets[key],
        })
    frame = pd.DataFrame(rows)
    st.dataframe(frame, hide_index=True, use_container_width=True)
    st.caption("各证据独立计分封顶（数据 30 / 单模型 24 / 多模型 37 / 物理 40），"
               "总风险分封顶 100。")


def _render_models(raw: Dict[str, Any], analysis: Dict[str, Any]) -> None:
    st.subheader("模型评估状态")
    st.dataframe(
        pd.DataFrame(_model_rows(raw, analysis)),
        hide_index=True,
        use_container_width=True,
    )

    with st.expander("查看各模型 P/S 预测"):
        rows = []
        for item in raw.get("model_predictions", []):
            rows.append(
                {
                    "模型": item.get("model_name"),
                    "相位": item.get("phase"),
                    "时间 (s)": item.get("time_s"),
                    "置信度": item.get("score"),
                    "状态": item.get("adapter_status"),
                    "来源": item.get("prediction_source"),
                }
            )
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def _render_batch_statistics(items: List[Dict[str, Any]]) -> None:
    if len(items) < 2:
        return
    rows = []
    for item in items:
        result = item["analysis"]["result"]
        triage = classify_event(result, item["raw"]["quality_report"])
        rows.append(
            {
                "样本": result["sample_id"],
                "事件分流": triage["display"],
                "风险": result["overall_risk_score"],
                "风险等级": result["overall_risk_level"],
                "P/S 状态": result["final_pair_status"],
            }
        )
    frame = pd.DataFrame(rows)
    st.subheader("批量事件统计")
    st.bar_chart(frame["事件分流"].value_counts())
    st.dataframe(frame, hide_index=True, use_container_width=True)
    st.download_button(
        "下载批量摘要 CSV",
        frame.to_csv(index=False).encode("utf-8-sig"),
        file_name="trust_batch_summary.csv",
        mime="text/csv",
    )


def _render_experiments() -> None:
    st.subheader("离线实验证据")
    st.caption("以下为离线实验固定结果：基于 895 条真实标注数据预先计算，与上传文件无关。")
    existing = [path for path in (NOISE_CURVE,) + BASELINE_CHARTS if path.exists()]
    if not existing:
        st.info("实验图尚未生成。请先运行噪声实验脚本。")
        return
    for path in existing:
        st.image(str(path), caption=path.stem.replace("_", " ").title())
    if NOISE_SUMMARY.exists():
        summary = pd.read_csv(NOISE_SUMMARY)
        columns = [
            "noise_level", "method", "accuracy_rate", "coverage_rate",
            "selective_accuracy", "abstention_rate", "unsafe_output_rate",
            "safe_handling_rate",
        ]
        st.subheader("严格指标拆分")
        st.dataframe(summary[columns], hide_index=True, use_container_width=True)
        st.caption("安全处置率必须与覆盖率、拒绝率一起阅读；全部拒绝不会被表述为 100% 准确率。")
    if STALTA_SUMMARY.exists():
        st.subheader("STA/LTA 传统基线")
        st.json(json.loads(STALTA_SUMMARY.read_text(encoding="utf-8")))
    if CPU_BENCHMARK.exists():
        benchmark = json.loads(CPU_BENCHMARK.read_text(encoding="utf-8"))
        st.subheader("CPU 本地运行实测")
        st.dataframe(pd.DataFrame(benchmark["models"]), hide_index=True, use_container_width=True)
        st.caption("单机、单样本、热缓存工程测量；不是跨设备性能承诺，也未进行量化或剪枝。")


def main() -> None:
    st.set_page_config(
        page_title="OBS Trust Layer",
        page_icon="🌊",
        layout="wide",
    )
    st.title("OBS Trust Layer 可信分析台")
    st.markdown(
        "**模型无关的可信 AI 调度层** —— 综合数据质量、多模型一致性与物理约束，"
        "对每次拾取结果给出风险等级与决策：自动接受（ACCEPT）、模型融合（FUSE）或人工复核（ABSTAIN）。"
    )
    st.caption("上传数据组产出的 result.json，或点击下方示例按钮体验完整流程。")


        # ---------------------------------------------------------
    # Exploration Environment - Gate 0 control skeleton
    # ---------------------------------------------------------
    st.divider()
    st.subheader("Exploration Controls")

    st.caption(
        "Gate 0 control skeleton. "
        "Backend recalculation wiring will use the frozen A-side schema."
    )

    control_cols = st.columns(4)

    risk_threshold = control_cols[0].slider(
        "Risk threshold",
        min_value=0.0,
        max_value=100.0,
        value=10.0,
        step=1.0,
    )
    p_tolerance = control_cols[1].slider(
        "P tolerance (s)",
        min_value=0.05,
        max_value=1.00,
        value=0.30,
        step=0.05,
    )

    s_tolerance = control_cols[2].slider(
        "S tolerance (s)",
        min_value=0.05,
        max_value=2.00,
        value=0.50,
        step=0.05,
    )

    data_weight = control_cols[3].slider(
        "Evidence weight",
        min_value=0.0,
        max_value=2.0,
        value=1.0,
        step=0.1,
    )
    upload_columns = st.columns(2)
    uploaded_files = upload_columns[0].file_uploader(
        "上传一个或多个 result.json",
        type=["json"],
        accept_multiple_files=True,
    )
    waveform_upload = upload_columns[1].file_uploader(
        "可选：上传对应波形",
        type=["csv", "mseed", "miniseed", "sgy", "segy"],
        help="CSV 需要 time_s 列，或使用左侧 JSON 中的采样率。MiniSEED/SEG-Y 由 ObsPy 读取。",
    )

    if not uploaded_files:
        if waveform_upload is not None:
            st.warning(
                "边界提示：原始波形文件（SEG-Y/MiniSEED/CSV）不含模型预测，无法直接分析。"
                "请先在左侧上传数据层产出的 result.json（含三模型 P/S 预测），"
                "再上传波形用于绘制与拾取位置标注。"
            )
        # 一键示例
        example_cols = st.columns([1, 1, 3])
        if example_cols[0].button("示例 1：三模型共识 → 融合"):
            st.session_state["example_file"] = "example_1.json"
        if example_cols[1].button("示例 2：模型分歧 → 拒绝"):
            st.session_state["example_file"] = "example_2.json"

        example_file = st.session_state.get("example_file")
        example_path = (
            ROOT / "data" / "examples" / example_file
            if example_file
            else None
        )

        if example_path and example_path.exists():
            try:
                uploaded_raw = json.loads(
                    example_path.read_text(encoding="utf-8-sig")
                )

                uploaded_analysis = run_analysis(
                    uploaded_raw,
                    risk_threshold=risk_threshold,
                    p_tolerance=p_tolerance,
                    s_tolerance=s_tolerance,
                    data_weight=data_weight,
                )

                items = [{
                    "name": example_file,
                    "raw": uploaded_raw,
                    "analysis": uploaded_analysis,
                }]

                raw = items[0]["raw"]
                analysis = items[0]["analysis"]

                # 加载配套波形 CSV（若存在）
                waveform = None
                csv_path = example_path.with_suffix(".csv")

                if csv_path.exists():
                    try:
                        waveform = read_waveform_bytes(
                            csv_path.read_bytes(),
                            csv_path.name,
                            sampling_rate_hz=float(
                                raw["quality_report"]["sampling_rate_hz"]
                            ),
                        )
                    except Exception:
                        waveform = None

                st.success(
                    f"已加载内置示例：{example_file}"
                    f"（{len(analysis['inputs']['predictions'])} 条模型预测）"
                )
                _render_full(raw, analysis, waveform)

            except Exception as exc:
                st.exception(exc)

        else:
            st.info("上传 JSON 开始分析，或点击上方按钮加载内置示例。")
            _render_experiments()

        return

    items = []

    for uploaded in uploaded_files:
        try:
            uploaded_raw = json.loads(
                uploaded.getvalue().decode("utf-8-sig")
            )

            uploaded_analysis = run_analysis(
                uploaded_raw,
                risk_threshold=risk_threshold,
                p_tolerance=p_tolerance,
                s_tolerance=s_tolerance,
                data_weight=data_weight,
            )

            items.append({
                "name": uploaded.name,
                "raw": uploaded_raw,
                "analysis": uploaded_analysis,
            })

        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            st.error(f"{uploaded.name} 无法解析：{exc}")
            return

        except (TypeError, ValueError, KeyError) as exc:
            st.error(f"{uploaded.name} 不符合数据契约：{exc}")
            return

        except Exception as exc:
            st.exception(exc)
            return

    selected = 0

    if len(items) > 1:
        selected = st.selectbox(
            "当前查看样本",
            range(len(items)),
            format_func=lambda index: items[index]["analysis"]["result"]["sample_id"],
        )

    raw = items[selected]["raw"]
    analysis = items[selected]["analysis"]

    waveform = None
    if waveform_upload is not None:
        try:
            waveform = read_waveform_bytes(
                waveform_upload.getvalue(),
                waveform_upload.name,
                sampling_rate_hz=float(raw["quality_report"]["sampling_rate_hz"]),
            )
        except Exception as exc:
            st.error(f"波形文件无法读取：{exc}")

    overview, waveform_tab, models, evidence, experiments, raw_tab = st.tabs(
        ["总览", "波形", "模型状态", "风险分解", "离线实验证据", "JSON 结果"]
    )
    with overview:
        _render_batch_statistics(items)
        _render_overview(raw, analysis)
        _render_decisions(analysis)
    with waveform_tab:
        if waveform is None:
            st.info("上传对应 CSV、MiniSEED 或 SEG-Y 波形后，可查看预处理前后、拾取点和 STA/LTA 触发结果。")
        else:
            _render_waveform(raw, waveform)
    with models:
        _render_models(raw, analysis)
    with evidence:
        _render_risk(analysis)
        with st.expander("查看共识与物理证据"):
            st.json(
                {
                    "data_evidence": analysis["data_evidence"],
                    "consensus": analysis["consensus"],
                    "physics": analysis["physics"],
                }
            )
    with experiments:
        _render_experiments()
    with raw_tab:
        st.download_button(
            "下载 Trust Engine 结果",
            json.dumps(analysis["result"], ensure_ascii=False, indent=2),
            file_name=f"{analysis['result']['sample_id']}_trust_result.json",
            mime="application/json",
        )
        st.json(analysis["result"])


def _render_full(raw: Dict[str, Any], analysis: Dict[str, Any],
                 waveform: Any) -> None:
    """渲染完整分析视图 (示例按钮和上传文件共用)"""
    overview, waveform_tab, models, evidence, experiments, raw_tab = st.tabs(
        ["总览", "波形", "模型状态", "风险分解", "离线实验证据", "JSON 结果"]
    )
    with overview:
        _render_batch_statistics([{"name": "当前样本", "raw": raw,
                                   "analysis": analysis}])
        _render_overview(raw, analysis)
        _render_decisions(analysis)
    with waveform_tab:
        if waveform is None:
            st.info("上传对应 CSV、MiniSEED 或 SEG-Y 波形后，可查看预处理前后、拾取点和 STA/LTA 触发结果。")
        else:
            _render_waveform(raw, waveform)
    with models:
        _render_models(raw, analysis)
    with evidence:
        _render_risk(analysis)
        with st.expander("查看共识与物理证据"):
            st.json(
                {
                    "data_evidence": analysis["data_evidence"],
                    "consensus": analysis["consensus"],
                    "physics": analysis["physics"],
                }
            )
    with experiments:
        _render_experiments()
    with raw_tab:
        st.download_button(
            "下载 Trust Engine 结果",
            json.dumps(analysis["result"], ensure_ascii=False, indent=2),
            file_name=f"{analysis['result']['sample_id']}_trust_result.json",
            mime="application/json",
        )
        st.json(analysis["result"])


if __name__ == "__main__":
    main()
