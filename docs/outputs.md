# Outputs

Track Encoder produces five artifact families: processed datasets, one per
split of your split assignment (see [Preparation](preparation.md)); training
runs with resumable full checkpoints and an encoder-only artifact (see
[Training](training.md)); evaluations of a full checkpoint on a processed
dataset, with aggregate and per-row scores (see [Evaluation](evaluation.md));
row-aligned embedding exports (see [Embedding](embedding.md)); and
reconstructions of selected element examples from a full checkpoint (see
[Reconstruction](reconstruction.md)).

## Regenerate earlier artifacts

This alpha release is a breaking change: splits are now standalone processed
datasets, evaluation is separate from training, and the training
configuration is now schema version `3`. Artifacts from earlier
releases are rejected by the field that changed, with no fallback, so
regenerate them:

| Earlier artifact | Rejected by | What to do |
| --- | --- | --- |
| Processed datasets that kept every split in one directory | `schema_version` (dataset schema version `1`) | Run `prepare` again; it writes `train/`, `val/`, and `test/` datasets |
| Training configurations with a single dataset path | that field, or `schema_version` (training configuration schema version `1`) | Set `schema_version` to `3` and name `data.train_dataset_path` and `data.val_dataset_path` |
| Training configurations with schema version `2` | `schema_version` | Set `schema_version` to `3`; nothing else changes |
| Full checkpoints from a run whose configuration was version `2` | `schema_version`, on resume only | They cannot be resumed; `embed` (through the run's encoder artifact), `reconstruct`, and `evaluate` still accept them |
| Full checkpoints with a single dataset identity | `train_dataset_identity` | Train again on the new datasets; resume, reconstruction, and evaluation all refuse them |
| Test metrics in a run's `summary.json` | — | `summary.json` now holds only `best_val_reconstruction_loss` and `epochs`; run `evaluate` on the test dataset for test metrics |

Reconstruction manifests are now schema version `2`: they no longer report a
split per row, and they report matches against both the train and the val
dataset.

## What the alpha framework does not do

To avoid mistaking plans for capabilities: the current framework performs no
region discovery, no peak discovery, no biological evaluation of element
membership, no alternative architectures beyond the supported dilated
convolutional encoder, and no objectives beyond full-window reconstruction
with explicitly selected `mse` or `alignment_tolerant_mse`
(`objective.loss.type`).
Demonstration hyperparameters in the code repository verify mechanics only and
are not endorsed defaults. Downstream analyses such as clustering or
dimensionality reduction operate on exported embeddings outside this
framework.
