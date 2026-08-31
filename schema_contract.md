# GOAI OBS Demo Schema Contract

## 1. Purpose

This document freezes the minimum interface between the backend computation chain and the exploration Demo.

The frontend consumes backend outputs and must not independently recompute scientific metrics.

## 2. ModelPrediction

Source: src/trust_engine/schema.py

Fields:

- sample_id: str
- window_id: str
- model_name: str
- model_version: str
- phase: str
- time_s: float
- pick_time_utc: Optional[str]
- source_time_basis: str
- score: Optional[float]
- adapter_status: str
- preprocessing_version: str
- prediction_source: str

Current conventions:

- model_version = "unknown"
- time_s = -1
- source_time_basis = "WINDOW_SECONDS"
- adapter_status = "OK"
- prediction_source = "REAL_MODEL"

Minimum Demo display:

- model_name
- phase
- time_s
- score

## 3. AdapterStatus

Fields:

- model_name: str
- loaded: bool
- run_succeeded: bool
- output_comparable: bool

These fields determine whether a model result is usable.

## 4. TrustConfig

Confirmed current backend parameters:

- fusion_enabled = True
- consensus_tolerance_p_s = 0.34
- consensus_tolerance_s_s = 0.51
- automatic_risk_threshold = 10.0
- risk_low_max = 10.0
- risk_medium_max = 30.0
- min_sp_s = 5.7
- max_sp_s = 33.42
- required_channels_for_task = ["Z", "N", "E"]
- data_weight = 30.0
- single_model_weight = 24.0
- multi_model_weight = 37.0
- physics_weight = 40.0
- config_version = "calibrated_v1.0"          # TrustConfig 参数集版本
- data evidence penalties = "natural_v1.0"     # DS4 自然重校准 (NATURAL_PENALTIES)
- experiment protocol = "semifinal_v1.5"       # configs/semifinal_main.yaml

v1.5.1 (2026-08-31) 新增冻结字段 — 全部由 `src/trust_engine/config_loader.py`
从 `configs/semifinal_main.yaml` 的 `trust_engine.parameters` 单一来源读取,
Demo 不得硬编码复刻:

- config_hash = 冻结配置全文件 SHA-256（每个结果行携带, 供追溯）
- parent_config = "semifinal_v1.5"
- severe_disagreement_p_s = 1.0 / severe_disagreement_s_s = 2.0
- fusion_confidence_floor = 0.70
- single_low_confidence_score = 5.0
- p_after_s_score = 10.0 / sp_interval_score = 5.0
- data_penalties = 自然罚分全表（含 moderate_signal=1.0, 见 ds4_natural_hazard.json）
- experiment protocol 升版为 `semifinal_v1.5.1`

## 5. Demo-Adjustable Parameters

The Gate 0 Demo skeleton exposes:

- Risk threshold
- P-wave tolerance
- S-wave tolerance
- Evidence weight

Backend mapping:

- Risk threshold -> automatic_risk_threshold
- P tolerance -> consensus_tolerance_p_s
- S tolerance -> consensus_tolerance_s_s
- Evidence weight -> data_weight

Available backend weight fields are:

- data_weight
- single_model_weight
- multi_model_weight
- physics_weight

The final evidence-weight field was confirmed with A on 2026-08-28: `data_weight`.
Other weights stay fixed at backend values unless explicitly exposed later.

## 6. Backend Recalculation Entry Point

Current Streamlit integration uses:

run_pipeline(**inputs)

All parameter changes must eventually trigger this real backend recalculation path.

The frontend must not generate replacement scientific results.

## 7. Existing Analysis Chain

The current Web Demo already uses:

- load_from_mapping(...)
- run_pipeline(...)
- evaluate_data_evidence(...)
- evaluate_model_suitability(...)
- evaluate_single_model_evidence(...)
- check_model_prediction(...)
- analyze_multi_model_consensus(...)

The exploration environment should reuse this existing computation chain.

## 8. Required Demo Output

The B-side Demo expects:

- sample
- predictions
- evidence
- risk
- action
- metrics
- config/version id

Core display targets:

- waveform
- model picks
- confidence / score
- evidence
- risk
- reason codes
- action

## 9. Scientific Boundary

The frontend may:

- display backend values
- select samples
- change approved configuration values
- trigger backend recalculation
- visualise returned results

The frontend must not:

- independently recompute scientific metrics
- invent missing results
- replace failed calculations with fake values
- freely generate scientific failure reasons with an LLM

## 10. Gate 0 Freeze Status

Confirmed from the current repository:

- ModelPrediction schema
- AdapterStatus schema
- Main TrustConfig parameters
- config_version = calibrated_v1.0 (TrustConfig 参数集); 实验协议 semifinal_v1.5.1
- Real pipeline entry point
- Existing analysis chain

## 11. Gate 0 Final Interface Freeze

The B-side interface is frozen against the current backend implementation.

### Demo control mapping

The initial Demo exposes:

- `automatic_risk_threshold`
- `consensus_tolerance_p_s`
- `consensus_tolerance_s_s`
- `data_weight`

Other evidence weights remain fixed at their backend configuration values unless explicitly exposed later.

### Backend result contract

The Demo calls:

`run_pipeline(...) -> ReliabilityResult`

Final outputs are read directly from the backend result:

- Risk score: `overall_risk_score`
- Risk level: `overall_risk_level`
- Phase action: `phase_decisions[phase].action`
- Evidence: `evidence_breakdown`
- Reasons: `reason_codes`
- Configuration version: `config_version`

Phase actions are:

- `ACCEPT`
- `ROUTE`
- `FUSE`
- `ABSTAIN`

### Metrics

Input/data quality metrics are provided by `QualityReport`, including:

- `sampling_rate_hz`
- `gap_ratio`
- `clipping_ratio`
- `snr_db`
- `metric_version`

The frontend displays backend-provided values and does not independently recompute scientific metrics.

### Configuration version behaviour

The pipeline loads ALL engine parameters from the single frozen config via
`src/trust_engine/config_loader.py` (`configs/semifinal_main.yaml`,
`trust_engine.parameters`):

```
load_frozen_config().trust_config()
```

The historical parameter file `src/calibrate/thresholds_calibrated.json` is no
longer read (kept as legacy record only). The loaded config carries
`config_version = "calibrated_v1.0"` (parameter set), `config_hash`
(frozen-config SHA-256) and `parent_config = "semifinal_v1.5"`.

The Demo must display the `config_version` / `config_hash` returned by the active
backend result rather than hard-coding a version.

### Gate 0 Status

**FROZEN**

The Environment Spec, backend schema contract, control mapping, recalculation entry point, and result mapping are defined from the current repository implementation.

## 12. A-side contract additions (merged 2026-08-28)

The following A-owned content was merged from the parallel draft
`docs/experiments/output_schema.md` (that duplicate file is removed; this is the
single canonical contract).

### 12.1 Action values

Confirmed from `src/trust_engine/schema.py` (`class Action`): the router emits
exactly four values — `ACCEPT`, `ROUTE`, `FUSE`, `ABSTAIN`. `ROUTE` is emitted
when a single non-primary model is selected (`policy_router.py`).

v1.5 reason codes B may encounter (display as-is, do not reinterpret):

- `SEVERE_DISAGREEMENT` / `MINOR_DISAGREEMENT` — 分歧三级 (第二刀)
- `FUSION_CALIBRATED_CONFIDENCE_BELOW_FLOOR` — FUSE 被校准置信度门槛拦截
- `LOW_CALIBRATED_CONFIDENCE_<model>_<phase>` — 校准后正确率 < 0.70
- `CONSENSUS_WITHOUT_ADMISSIBLE_FUSION` — v1.5.1 fail-closed: 共识但无通过
  全部门槛的融合候选 → ABSTAIN（第 4.5 步, 不再回退主模型）

Model identities (four frozen prediction columns): PhaseNet=geofon、
PickBlue=PhaseNet obs、OBSTransformer=obst2024、EQTransformer=obs —
见 `docs/model_registry.md`。

### 12.2 Weight calibration provenance (for slider labels)

| Parameter | Frozen default | Provenance |
|---|---|---|
| automatic_risk_threshold | 10.0 | risk calibration curve, n=891 (≤10 → 12.6% error) |
| consensus_tolerance_p_s | 0.34 | 95th percentile, n=674 |
| consensus_tolerance_s_s | 0.51 | 95th percentile, n=455 |
| data_weight | 30.0 | conservative floor |
| single_model_weight | 24.0 | logistic regression, n=895 |
| multi_model_weight | 37.0 | logistic regression, n=895 |
| physics_weight | 40.0 | logistic regression, n=895 |

The Demo must label each slider with its frozen default and provenance, and mark
"偏离 calibrated_v1.0" with the deviation list after any user change.
数据证据罚分来自 `natural_v1.0`（NATURAL_PENALTIES，DS4 自然重校准，v1.5.1 起
内嵌于 trust_engine.parameters.data_penalties），实验协议为 `semifinal_v1.5.1`
（configs/semifinal_main.yaml，`config_hash` 全程随行）——版本层级按字段区分，
Demo 展示时不得混用。

### 12.3 Batch metrics source (Feedback panel)

Coverage / Unsafe Output Rate / Interception / Review Burden are batch
statistics. They are NOT part of a single `run_pipeline()` return. The Feedback
panel reads A's batch result files:

- `results/baseline_results.csv` — 8 strategies (含 4 单模型基线) × 5 coverage points
- `results/main_results.csv` — Trust main experiment per-sample decisions
- `results/risk_bins.csv` — risk-bin error rates
- `results/domain_gate.json` — ID-only 域门 (XO 阈值 95%=3.94 / 99%=5.27)

Metric definitions and pairing rules: `docs/experiments/evaluation_protocol.md`.
Evaluation subset: **N_eval = 1306 phase units (P 657 + S 649)** — 相位级 Primary
(成对判定仅作 Secondary)，见 `configs/semifinal_main.yaml`。
The frontend must not recompute these metrics.
