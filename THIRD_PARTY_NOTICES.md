# Third-Party Notices

This repository contains team-authored code together with references to third-party
datasets, libraries, pretrained model architectures, and model checkpoints.

The repository-level MIT License applies only to code authored by the OBS Trust
Engine team. It does not override licenses or terms attached to third-party data,
libraries, pretrained weights, or other external assets.

## Data

- SeisBench OBS dataset
  - Source/provenance: documented in `docs/data_and_model_sources.md`
  - Dataset rights and redistribution terms remain governed by the upstream source.
  - No claim is made that the dataset is covered by this repository's MIT License.

## Model / checkpoint sources

Model and checkpoint provenance is documented in:

- `docs/model_registry.md`
- `docs/data_and_model_sources.md`

The project uses or evaluates SeisBench-accessible model families including
PhaseNet, PickBlue, EQTransformer, and OBSTransformer.

Checkpoint-specific license and redistribution rights must be verified against the
corresponding upstream model/source before redistributing model weights.

No third-party model weight is relicensed under this repository's MIT License.

## Python dependencies

Runtime / analysis dependencies are declared in `requirements.txt`.

Each dependency remains governed by its own upstream license. This repository does
not relicense those packages.

## Redistribution boundary

Before publishing a release bundle:

1. verify dataset redistribution rights;
2. verify each checkpoint-specific license;
3. do not bundle restricted model weights or datasets unless redistribution is allowed;
4. retain applicable upstream notices and attribution.

