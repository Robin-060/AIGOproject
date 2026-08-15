"""
证据权重校准 — 逻辑回归 (路线 B)

方法: 把四类证据分当作预测"模型拾取错误"的特征,
      用逻辑回归拟合权重。拟合系数 = 有数据背书的权重。

原理:
  P(错误 | 证据) = sigmoid( b0 + w1·data + w2·single + w3·multi + w4·physics )
  拟合出的 w 越大 = 该证据越能预示错误 = 应该给更高权重。

用法:
    python -m src.calibrate.weight_calibration
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from src.trust_engine.schema import (
    SampleMetadata, QualityReport, ModelPrediction, ModelProfile,
    AdapterStatus, TrustConfig,
)
from src.trust_engine.reliability import evaluate_reliability
from src.trust_engine.data_evidence import evaluate_data_evidence
from src.trust_engine.model_suitability import evaluate_model_suitability
from src.trust_engine.single_model import evaluate_single_model_evidence
from src.trust_engine.physics import check_model_prediction
from src.trust_engine.multi_model import analyze_multi_model_consensus
from src.trust_engine.fusion import build_fusion_candidates

PRED_PATH = Path("data/phase3/noise_predictions_seisbench.json")
TRUTH_PATH = Path("data/phase3/noise_records_seisbench.csv")
OUT_PATH = Path("docs/experiments/weight_calibration.json")

PROFILES = [
    ModelProfile(model_name="PhaseNet", required_channels=["Z", "N", "E"],
                 accepted_sampling_rates_hz=[100.0], resampling_supported=True,
                 required_preprocessing_version="seisbench_v0.12"),
    ModelProfile(model_name="PickBlue", required_channels=["Z", "N", "E", "H"],
                 accepted_sampling_rates_hz=[100.0], resampling_supported=True,
                 required_preprocessing_version="seisbench_v0.12"),
    ModelProfile(model_name="OBSTransformer", required_channels=["H"],
                 preferred_channels=["Z", "N", "E"],
                 accepted_sampling_rates_hz=[100.0], resampling_supported=True,
                 required_preprocessing_version="seisbench_v0.12"),
]
ADAPTERS = [
    AdapterStatus(model_name=m, loaded=True, run_succeeded=True, output_comparable=True)
    for m in ("PhaseNet", "PickBlue", "OBSTransformer")
]


def load_data():
    truth_map = {}
    with open(TRUTH_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (row["sample_id"], row["noise_level"])
            if key in truth_map:
                continue
            truth_map[key] = {
                "P": float(row["truth_p_s"]) if row["truth_p_s"] else None,
                "S": float(row["truth_s_s"]) if row["truth_s_s"] else None,
            }
    pred_map = defaultdict(list)
    with open(PRED_PATH, encoding="utf-8") as f:
        for p in json.load(f):
            pred_map[(p["sample_id"], p["noise_level"])].append(
                ModelPrediction(**{k: v for k, v in p.items() if k != "noise_level"})
            )
    samples = []
    for key, gt in truth_map.items():
        if key not in pred_map or gt["P"] is None or gt["S"] is None:
            continue
        noise = key[1]
        meta = SampleMetadata(
            sample_id=key[0], data_source="REAL",
            preprocessing_version="seisbench_v0.12",
        )
        quality = QualityReport(
            available_channels=["Z", "N", "E", "H"], missing_channels=[],
            snr_db={"L0": 20.0, "L1": 10.0, "L2": 5.0, "L3": 2.0}[noise],
            source="REAL_CALCULATION",
        )
        samples.append((meta, quality, pred_map[key], gt))
    return samples


def build_evidence_features(meta, quality, preds, config):
    """为一条样本计算四类证据分 + 该样本模型是否犯错"""
    data_ev = evaluate_data_evidence(quality)
    suits = evaluate_model_suitability(meta, quality, PROFILES, ADAPTERS)
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
    cons = analyze_multi_model_consensus(preds, suits, physics)
    fusions = build_fusion_candidates(preds, cons)

    result = evaluate_reliability(
        meta, quality, PROFILES, preds,
        config, data_ev, suits, singles, physics, cons, fusions,
    )

    # 四类证据分 (从 evidence_breakdown 提取)
    brk = result.evidence_breakdown.get("P", {})
    features = np.array([
        brk.get("data", 0.0),
        brk.get("single_model", 0.0),
        brk.get("multi_model", 0.0),
        brk.get("physics", 0.0),
    ], dtype=float)

    # 标签: 这条样本的模型拾取是否错误 (放宽口径)
    label = _model_wrong(meta, quality, preds, config)
    return features, label


def _model_wrong(meta, quality, preds, config):
    """判定: 模型在这条样本上是否产出错误拾取"""
    from src.trust_engine.reliability import evaluate_reliability
    # 简化: 用 Trust Layer 的 phase 决策 vs 真值
    data_ev = evaluate_data_evidence(quality)
    suits = evaluate_model_suitability(meta, quality, PROFILES, ADAPTERS)
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
    cons = analyze_multi_model_consensus(preds, suits, physics)
    fusions = build_fusion_candidates(preds, cons)
    result = evaluate_reliability(
        meta, quality, PROFILES, preds,
        config, data_ev, suits, singles, physics, cons, fusions,
    )
    # 放宽口径: 任一相位输出且超容差 = wrong
    for d, phase in [(result.phase_decisions.get("P"), "P"),
                     (result.phase_decisions.get("S"), "S")]:
        if not d or d.action == "ABSTAIN" or d.selected_time_s is None:
            continue
        # 无真值无法判断 → 不算错
    return 0  # 占位, 主函数里单独算


def main():
    samples = load_data()
    print(f"有效样本: {len(samples)}")
    config = TrustConfig()

    X_rows = []
    y_rows = []
    for meta, quality, preds, gt in samples:
        feats, _ = build_evidence_features(meta, quality, preds, config)

        # 标签: 任一模型拾取超出容差 = 错误样本
        wrong = 0
        for p in preds:
            tol = 0.5 if p.phase == "P" else 1.0
            if abs(p.time_s - gt[p.phase]) > tol:
                wrong = 1
                break
        X_rows.append(feats)
        y_rows.append(wrong)

    X = np.array(X_rows)
    y = np.array(y_rows)
    print(f"错误样本: {y.sum()}/{len(y)}")

    # 手写逻辑回归 (梯度下降, 避免依赖 sklearn)
    # 标准化特征
    X_mean = X.mean(axis=0, keepdims=True)
    X_std = X.std(axis=0, keepdims=True) + 1e-9
    Xn = (X - X_mean) / X_std

    def sigmoid(z):
        return 1 / (1 + np.exp(-np.clip(z, -30, 30)))

    w = np.zeros(5)  # b0 + 4 weights
    lr = 0.5
    for _ in range(3000):
        z = w[0] + Xn @ w[1:]
        grad = np.zeros(5)
        grad[0] = (sigmoid(z) - y).mean()
        grad[1:] = (Xn.T @ (sigmoid(z) - y)) / len(y)
        w -= lr * grad

    # 反标准化到原始尺度
    w_orig = np.zeros(5)
    w_orig[1:] = w[1:] / X_std[0]
    w_orig[0] = w[0] - (w[1:] * X_mean[0] / X_std[0]).sum()

    print("\n逻辑回归拟合结果:")
    names = ["bias", "data", "single_model", "multi_model", "physics"]
    for n, val in zip(names, w_orig):
        print(f"  {n:14s}: {val:+.4f}")

    # 归一化为权重占比 (取正值部分)
    pos = np.clip(w_orig[1:], 0, None)
    total = pos.sum()
    if total > 0:
        normalized = pos / total
        print("\n归一化权重 (仅正系数):")
        for n, val in zip(names[1:], normalized):
            print(f"  {n:14s}: {val:.2%}")
    else:
        print("\n所有系数非正 → 证据对错误无区分力 (样本太少)")

    # 简单准确率
    z = w[0] + Xn @ w[1:]
    pred = (sigmoid(z) > 0.5).astype(int)
    acc = (pred == y).mean()
    print(f"\n拟合准确率: {acc:.1%} (基线: 多数类 {1 - y.mean():.1%})")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "method": "logistic regression on evidence scores",
            "n_samples": int(len(y)),
            "n_wrong": int(y.sum()),
            "coefficients": {n: float(v) for n, v in zip(names, w_orig)},
            "normalized_weights": {n: float(v) for n, v in zip(names[1:], normalized)} if total > 0 else None,
            "fit_accuracy": float(acc),
            "note": "n=64, 初步估计, 置信区间宽",
        }, f, indent=2, ensure_ascii=False)
    print(f"\n✅ 结果 → {OUT_PATH}")


if __name__ == "__main__":
    main()
