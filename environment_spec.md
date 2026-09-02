# GOAI OBS 开放探索环境规格（最终版）

> 状态：**FROZEN / IMPLEMENTED / VERIFIED**
> 用途：将真实 Trust Engine、冻结实验反馈与可控搜索面组成可检查的最小探索环境。

## 1. 环境目标

评委应能在同一环境中完成六件事：

1. 读取真实 OBS 案例及冻结模型拾取；
2. 查看波形、P/S 拾取和数据质量；
3. 检查四类证据、risk score、reason codes 和最终 action；
4. 在允许边界内修改参数，触发真实后端重算；
5. 将 Coverage/Unsafe 与 Review/Interception 成对观察；
6. 查看冻结正结果、负结果、反例与复现身份。

环境优先保证真实计算、证据身份和失败可见性，不以视觉复杂度代替科研反馈。

## 2. Fixed / Searchable / Feedback

| 类型 | 定义 | 环境中的实现 |
|---|---|---|
| Fixed | 不在交互中更改的证据身份 | 冻结预测、Primary phase units、错误定义、v1.5.1/EXP16/EXP17 产物与 hash |
| Searchable | 用户可显式修改的候选维度 | risk threshold、P/S consensus tolerance、data evidence weight |
| Feedback | 后端返回的可观察结果 | action、reason codes、risk decomposition、Coverage/Unsafe、Review/Interception |

搜索面仅用于环境探索和机制说明。改参后的 Demo 输出不自动升级为冻结科学结论。

## 3. 模型与数据契约

当前评价使用四套 checkpoint 输出：

- PhaseNet `geofon`（PhaseNet 架构，GEOFON 陆地训练域）；
- PickBlue `obs`（在当前 SeisBench 路径中实际为 PhaseNet `obs`）；
- OBSTransformer `obst2024`；
- EQTransformer `obs`。

核心数据层一次运行 PhaseNet/PickBlue/OBSTransformer 三个 adapter；EQT 由独立批处理入口生成，
在 `records_all_v2.json` 中与前三者合并为四模型冻结评价输入。详细身份见
`docs/model_registry.md`。

Demo 的最小输入字段：

- `sample`、`predictions`、`evidence`、`risk`、`action`、`metrics`；
- `config_id`、`version_id`、`reason_codes`；
- 模型拾取的 `model_name`、`phase`、`pick_time`、`confidence`、`adapter_status`。

完整字段和容错规则见 `schema_contract.md`。

## 4. 真实后端与参数控制

交互计算必须调用 `run_pipeline(...) -> ReliabilityResult`，前端不重写 Trust 逻辑。

| 控件 | 后端字段 | 冻结默认值 |
|---|---|---:|
| Risk threshold | `automatic_risk_threshold` | 10.0 |
| P consensus tolerance | `consensus_tolerance_p_s` | 0.34 s |
| S consensus tolerance | `consensus_tolerance_s_s` | 0.51 s |
| Data evidence weight | `data_weight` | 30.0 |

其他证据权重保持配置值，除非显式设计新的版本化实验。

## 5. 主视图与 Case Explorer

主视图展示：

- 原始/预处理波形、各模型 P/S 拾取和最终 selected pick；
- 四证据分解、overall risk、action 和确定性 reason codes；
- Fixed Feedback：Review Efficiency、v1.5.1 ceiling、EXP17-A/B 与 R1；
- Case Explorer：真实高置信错误、模型分歧、数据质量问题和 Trust 未截获反例。

ABSTAIN 自然语言解释由 `reason code + evidence + fixed template` 确定生成，不使用 LLM 自由生成科学原因。

## 6. 指标展示纪律

- Coverage 必须与 Unsafe 同时展示；
- Error Interception 必须与 Review Burden 同时展示；
- 不可达目标点显示 `NOT_EVALUABLE`，不用伪数值补齐；
- `R1 PASS` 在同一位置说明“显式参数重跑与冻结结果一致”，并明确标注
  `R1 PASS ≠ EXP17 safety Gate PASS`；
- EXP17 总裁决固定为
  **Coverage recovery supported; safety non-inferiority inconclusive.**

## 7. 错误处理

下列情况必须显式报错，不得静默使用替代数值：

- 输入格式不符合 schema；
- 后端或服务不可用；
- 候选模型没有目标相位的有效 prediction；
- 关键字段、配置身份或冻结结果缺失；
- 不支持的文件、波形或参数。

## 8. 实现与验收状态

| 项目 | 状态 | 验收证据 |
|---|---|---|
| Backend schema | COMPLETE | `schema_contract.md`、FastAPI tests |
| Scientific presentation boundary | COMPLETE | `docs/scope_and_compliance.md`、前端 c2/R1 范围说明 |
| Fixed / Searchable / Feedback | COMPLETE | Streamlit 主视图与参数重算 |
| Case Explorer / ABSTAIN explanation | COMPLETE | 真实案例 + 确定性模板 |
| Docker frontend/backend | COMPLETE | `Dockerfile`、`docker-compose.yml` |
| CI / tests | PASS | GitHub Actions + 76 tests |
| Core / EXP17 reproduction | PASS | `reproduce_core.sh`、`reproduce_exp17.sh` |

## 9. 启动入口

```bash
python3 -m pip install -r requirements.txt
bash scripts/run_demo.sh
```

或：

```bash
docker compose up --build
```

默认端口：Streamlit `8501`，FastAPI `8000`。评委最短验收路径见 `JUDGE_QUICKSTART.md`。
