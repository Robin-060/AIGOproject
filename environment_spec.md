# GOAI OBS Exploration Environment Spec

## 1. Goal

Build a minimal runnable exploration environment that turns the real backend computation chain into an interactive Demo.

The Demo must allow judges to:

1. Load a real sample
2. View waveform and model picks
3. Inspect evidence, risk and action
4. Change allowed parameters
5. Re-run the real backend
6. Observe updated feedback and metrics

The Demo prioritises reproducibility and real feedback over visual complexity.

---

## 2. Backend Input Contract

The Demo consumes backend outputs only and does not independently recompute scientific metrics.

Required fields:

- sample
- predictions
- evidence
- risk
- action
- metrics
- config_id
- version_id

### Predictions

Expected information:

- model_name
- phase
- pick_time
- confidence

Target models:

- PhaseNet
- PickBlue
- Third supported model

### Trust Output

Expected information:

- evidence
- risk score
- reason codes
- final action

Supported actions:

- ACCEPT
- FUSE
- ABSTAIN

---

## 3. User Controls

The exploration environment must allow users to modify:

- Risk threshold
- P-wave tolerance
- S-wave tolerance
- At least one evidence weight

Parameter changes must trigger real backend recalculation.

The frontend must not generate fake or locally recomputed scientific results.

---

## 4. Main Demo View

The main Demo should display:

### Waveform Panel

- Waveform
- P/S picks from three models
- Fused pick when available

### Trust Panel

- Evidence
- Risk score
- Reason codes
- Action

### Parameter Panel

- Risk threshold
- P tolerance
- S tolerance
- Evidence weight

---

## 5. Feedback Panel

The Demo must expose paired evaluation feedback:

- Coverage + Unsafe
- Interception + Review
- Selective Risk

The displayed values must come from the real experiment/backend output.

---

## 6. Baseline Comparison

The Demo must support switching between:

- Trust-enabled system
- Baseline system

Where available, comparison should use Equal-Coverage results.

---

## 7. Case Explorer

The Case Explorer should provide real failure cases including:

- High-confidence incorrect prediction
- Model disagreement
- Poor-quality data
- A real case where Trust failed to intercept the error

No fake failure case should be presented as a verified result.

---

## 8. ABSTAIN Explanation

ABSTAIN explanations must be deterministic.

Generation format:

reason code + evidence + fixed template -> natural-language explanation

LLM free-form scientific explanations are not allowed.

---

## 9. Error Handling

The Demo should handle:

- Invalid input file
- Backend/service failure
- No prediction result
- Missing fields
- Unsupported input

Errors should be visible to the user and must not silently generate replacement values.

---

## 10. Engineering Requirements

Final environment should provide:

- README startup instructions
- requirements.txt
- Docker support
- CI/test status
- Clean-environment reproducibility

---

## 11. Gate 0 Interface Freeze

Before implementation, confirm with A:

- Exact field names
- Data types
- Config/version identifiers
- Recalculation entry point

Confirm with C:

- Fixed / Searchable / Feedback definitions
- Discovery Signals shown in Demo
- Scientific explanation boundaries

Status:

- Environment structure: defined
- Backend schema: pending final confirmation with A
- Scientific presentation boundary: pending final confirmation with C
