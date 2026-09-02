# Software Bill of Materials

This is the human-readable dependency inventory for the OBS Trust Layer release.

Source of dependency constraints: `requirements.txt`.

| Component | Declared version constraint | Role |
|---|---|---|
| streamlit | >=1.35,<2 | Web interface |
| pandas | >=2.0,<3 | Data processing |
| matplotlib | >=3.7,<4 | Figures / visualization |
| scipy | >=1.11,<2 | Scientific computing |
| pytest | >=7,<9 | Testing |
| seisbench | >=0.12.3,<0.13 | Seismological datasets/models |
| PyYAML | >=6.0,<7 | Configuration |

## Project code

- OBS Trust Engine / Trust Layer
- Repository license: MIT
- MIT applies only to team-authored project code.

## External data and model assets

Dataset and model/checkpoint provenance are tracked in:

- `docs/data_and_model_sources.md`
- `docs/model_registry.md`
- `THIRD_PARTY_NOTICES.md`

External datasets, pretrained checkpoints, and third-party libraries retain their
own upstream licenses and redistribution conditions.

## Scope note

This file records declared project components and dependency constraints.
It is not a claim that every third-party asset is redistributable, and it does not
replace checkpoint-specific or dataset-specific license verification.

