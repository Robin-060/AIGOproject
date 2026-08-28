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
- config_version = "calibrated_v1.0"

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
- Evidence weight -> final approved backend evidence-weight field

Available backend weight fields are:

- data_weight
- single_model_weight
- multi_model_weight
- physics_weight

The final evidence-weight field must be confirmed with A before wiring.

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
- config_version = calibrated_v1.0
- Real pipeline entry point
- Existing analysis chain

Still requiring final A-side confirmation:

- Exact evidence-weight field exposed to the Demo
- Final output location for risk / action / metrics
- Exact config/version ID returned with each run

Status:

Gate 0 interface contract drafted from the current repository implementation.
