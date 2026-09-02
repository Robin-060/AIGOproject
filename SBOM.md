# Software Bill of Materials

This is the human-readable dependency inventory for the OBS Trust Layer release.

Sources of dependency constraints: `requirements-core.txt`, `requirements.txt`, and `Dockerfile`.

| Component | Declared version constraint | Role | Upstream license |
|---|---|---|---|
| numpy | >=1.23,<3 | Numerical computing | BSD-3-Clause |
| streamlit | >=1.35,<2 | Web interface | Apache-2.0 |
| pandas | >=2.0,<3 | Data processing | BSD-3-Clause |
| matplotlib | >=3.7,<4 | Figures / visualization | Matplotlib/PSF-compatible |
| scipy | >=1.11,<2 | Scientific computing | BSD-3-Clause |
| pytest | >=7,<9 | Testing | MIT |
| seisbench | >=0.12.3,<0.13 | Seismological datasets/models | GPL-3.0 |
| PyYAML | >=6.0,<7 | Configuration | MIT |
| fastapi | unpinned in Dockerfile | Demo backend | MIT |
| uvicorn | unpinned in Dockerfile | ASGI server | BSD-3-Clause |
| python-multipart | unpinned in Dockerfile | Upload parsing | Apache-2.0 |
| Noto Sans CJK SC Regular | 2.004 | Embedded font in final C report | SIL OFL-1.1 |

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

The embedded Noto font is licensed separately from the report and project code. Its license text is
retained in `licenses/OFL-1.1.txt` and summarized in `THIRD_PARTY_NOTICES.md`.

## Scope note

This file records declared direct components and dependency constraints. It is not
a complete transitive or machine-generated SBOM, does not claim that every third-party
asset is redistributable, and does not replace checkpoint-specific or dataset-specific
license verification. The final release archive should retain the lockfile/environment
export and all upstream LICENSE/NOTICE files required by the resolved dependency graph.
