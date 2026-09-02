# Third-Party Notices

This repository contains original project code and documentation under the top-level MIT License.
That license does not relicense third-party software, datasets, pretrained model weights,
publications, or trademarks.

## Data

- **OBS / PickBlue dataset** — Zenodo record 10277799,
  <https://doi.org/10.5281/zenodo.10277799>, version v1-12/2023,
  licensed under **CC BY 4.0**. The repository does not redistribute the approximately 35 GB
  source waveform archive. Dataset attribution, DOI, license, and modification notices must be
  retained when the data or identifiable derivatives are shared.

## Software and model architectures

- **SeisBench** — GPL-3.0: <https://github.com/seisbench/seisbench>
- **PhaseNet architecture** — MIT: <https://github.com/AI4EPS/PhaseNet>
- **OBSTransformer architecture** — MIT: <https://github.com/alirezaniki/OBSTransformer>
- **EQTransformer architecture** — MIT: <https://github.com/smousavi05/EQTransformer>
- **ObsPy** — LGPL-3.0: <https://github.com/obspy/obspy>
- **PyTorch** — BSD-style license and upstream notices: <https://github.com/pytorch/pytorch>

Additional direct and transitive dependencies remain subject to the licenses shipped with their
installed distributions. The final release should include a generated SBOM or license report.

## Pretrained checkpoints

PhaseNet `geofon`, PhaseNet/PickBlue `obs`, OBSTransformer `obst2024`, and EQTransformer `obs`
are obtained through SeisBench and cached by the user. No checkpoint file is redistributed in this
repository. An architecture repository's license must not be assumed to be the license of a hosted
checkpoint; checkpoint-specific redistribution status is therefore recorded as UNKNOWN unless
explicit upstream terms are available.

## Project boundaries

- No commercial API or closed model service is used.
- No restricted, classified, or unauthorized OBS data is included.
- The top-level MIT License covers only material that the project team has the right to license.
- Full data/model provenance and scientific-use boundaries are documented in
  [`docs/data_and_model_sources.md`](docs/data_and_model_sources.md) and
  [`docs/scope_and_compliance.md`](docs/scope_and_compliance.md).

This notice is an attribution and release-boundary record, not legal advice.
