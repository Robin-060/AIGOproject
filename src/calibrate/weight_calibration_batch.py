"""
权重校准 (大数据版) — 用批量样本重拟合证据权重

数据: data/batch_calibration/records_all.json (895 条真实标注样本)
方法: 逻辑回归, 四类证据分 → 预测"模型拾取错误"

用法:
    python -m src.calibrate.weight_calibration_batch
"""

import json
from pathlib import Path

import numpy as np

RECORDS_PATH = Path("data/batch_calibration/records_all.json")
OUT_PATH = Path("docs/experiments/weight_calibration_batch.json")

P_TOL = 0.5
S_TOL = 1.0


def extract_features(record):
    """
    从一条样本提取四类证据的"原始信号强度":

    data:         SNR 相关 (无 SNR 字段时用 0)
    single_model: 模型置信度 (低置信 = 风险信号)
    multi_model:  模型间 P 时间差 / S 时间差
    physics:      P-S 时间差是否异常 (P>=S 或 S-P 异常)
    """
    preds = record["predictions"]
    truth_p, truth_s = record["truth_p_s"], record["truth_s_s"]

    # ── data 证据: 无数据质量字段, 用 0 (这批数据没有噪声等级) ──
    data_feat = 0.0

    # ── single_model 证据: 最低置信度 (越低越危险) ──
    confs = [p["confidence"] for p in preds.values()
             if p.get("confidence") is not None]
    single_feat = 1.0 - min(confs) if confs else 0.0  # 低置信 → 特征大

    # ── multi_model 证据: P 和 S 的模型间最大时间差 ──
    p_times = [p["P_pick"] for p in preds.values() if p["P_pick"] is not None]
    s_times = [p["S_pick"] for p in preds.values() if p["S_pick"] is not None]
    p_spread = (max(p_times) - min(p_times)) if len(p_times) >= 2 else 0.0
    s_spread = (max(s_times) - min(s_times)) if len(s_times) >= 2 else 0.0
    multi_feat = max(p_spread, s_spread)

    # ── physics 证据: 每模型的 P-S 是否反常 ──
    physics_feat = 0.0
    for m, p in preds.items():
        if p["P_pick"] is not None and p["S_pick"] is not None:
            sp = p["S_pick"] - p["P_pick"]
            if sp < 0:  # P 在 S 后
                physics_feat = max(physics_feat, 1.0)
            elif sp < 5 or sp > 30:  # 超出实测合理范围
                physics_feat = max(physics_feat, 0.5)
    # 多模型 S-P 一致性
    sp_vals = [p["S_pick"] - p["P_pick"] for p in preds.values()
               if p["P_pick"] is not None and p["S_pick"] is not None]
    if len(sp_vals) >= 2:
        sp_spread = max(sp_vals) - min(sp_vals)
        physics_feat = max(physics_feat, min(sp_spread / 20.0, 1.0))

    return np.array([data_feat, single_feat, multi_feat, physics_feat])


def label_wrong(record):
    """判定: 这条样本是否包含错误拾取 (相对真值)"""
    truth_p, truth_s = record["truth_p_s"], record["truth_s_s"]
    preds = record["predictions"]
    for p in preds.values():
        if truth_p is not None and p["P_pick"] is not None:
            if abs(p["P_pick"] - truth_p) > P_TOL:
                return 1
        if truth_s is not None and p["S_pick"] is not None:
            if abs(p["S_pick"] - truth_s) > S_TOL:
                return 1
    return 0


def main():
    with open(RECORDS_PATH, encoding="utf-8") as f:
        records = json.load(f)

    X_rows, y_rows = [], []
    for r in records:
        X_rows.append(extract_features(r))
        y_rows.append(label_wrong(r))

    X = np.array(X_rows)
    y = np.array(y_rows)
    print(f"样本: {len(y)}, 错误样本: {y.sum()} ({y.mean():.1%})")

    # 标准化 + 逻辑回归 (梯度下降)
    X_mean = X.mean(axis=0, keepdims=True)
    X_std = X.std(axis=0, keepdims=True) + 1e-9
    Xn = (X - X_mean) / X_std

    def sigmoid(z):
        return 1 / (1 + np.exp(-np.clip(z, -30, 30)))

    w = np.zeros(5)
    lr = 0.5
    for _ in range(3000):
        z = w[0] + Xn @ w[1:]
        grad0 = (sigmoid(z) - y).mean()
        grad = (Xn.T @ (sigmoid(z) - y)) / len(y)
        w[0] -= lr * grad0
        w[1:] -= lr * grad

    w_orig = np.zeros(5)
    w_orig[1:] = w[1:] / X_std[0]
    w_orig[0] = w[0] - (w[1:] * X_mean[0] / X_std[0]).sum()

    names = ["bias", "data", "single_model", "multi_model", "physics"]
    print("\n逻辑回归系数 (原始尺度):")
    for n, v in zip(names, w_orig):
        print(f"  {n:14s}: {v:+.4f}")

    # 特征标准化后的系数可直接比重要性 (尺度统一)
    print("\n标准化系数 (可比重要性):")
    for n, v in zip(names[1:], w[1:]):
        print(f"  {n:14s}: {v:+.4f}")

    # 归一化权重
    pos = np.clip(w[1:], 0, None)
    total = pos.sum()
    if total > 0:
        norm = pos / total
        print("\n归一化权重 (仅正系数):")
        for n, v in zip(names[1:], norm):
            print(f"  {n:14s}: {v:.2%}")

    z = w[0] + Xn @ w[1:]
    pred = (sigmoid(z) > 0.5).astype(int)
    acc = (pred == y).mean()
    print(f"\n拟合准确率: {acc:.1%} (多数类基线: {1 - y.mean():.1%})")

    # 保存
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "method": "logistic regression, 895 real labeled samples",
            "n_samples": int(len(y)),
            "n_wrong": int(y.sum()),
            "coefficients_raw": {n: float(v) for n, v in zip(names, w_orig)},
            "coefficients_standardized": {n: float(v) for n, v in zip(names[1:], w[1:])},
            "normalized_weights": {n: float(v) for n, v in zip(names[1:], norm)} if total > 0 else None,
            "fit_accuracy": float(acc),
        }, f, indent=2, ensure_ascii=False)
    print(f"\n✅ 结果 → {OUT_PATH}")


if __name__ == "__main__":
    main()
