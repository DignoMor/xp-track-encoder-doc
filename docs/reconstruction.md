# Reconstruction

Reconstruction shows what a trained model retains about particular element
examples. `track-encoder reconstruct` rebuilds the encoder and the
reconstruction decoder from a **full checkpoint** written by training (see
[Training](training.md)), passes each selected element example of a processed
dataset (see [Preparation](preparation.md)) through both, and writes the raw
decoder output. Each **reconstruction** is expressed in the same jointly
normalized signal units as the element example it came from, so it overlays
the matching rows of `signals.npy` directly.

Reconstruction performs no training, checkpoint selection, alignment, or
scoring. It never computes a loss or aggregate metric, never modifies the
checkpoint or its run directory, and writes nothing outside the output
directory. Held-out scores remain the ones training recorded in
`summary.json`.

## What you need

- **A full checkpoint file** written by `track-encoder train`, such as the
  validation-selected `best.pt` or the most recent `latest.pt`. Name the file
  itself: the command never chooses a checkpoint from a run directory. The
  encoder and decoder are rebuilt from the checkpoint's own resolved
  experiment and saved state, so no training configuration, hyperparameter
  document, or training dataset path is needed.
- **A processed dataset directory** holding `dataset.json`, `signals.npy`,
  the region table, and `split.npy`. It may be the checkpoint's training
  dataset or a separately prepared dataset that fits the model (see
  [Compatibility](#compatibility)).
- **A boolean mask** selecting the element examples to reconstruct (see
  [Select element examples](#select-element-examples)).
- **An empty output destination.** Reconstruction never merges into or
  overwrites existing outputs.

An **encoder artifact** (`encoder.json` plus `encoder.pt`) cannot be used
here. It carries only the encoder, with no decoder, so it cannot produce
reconstructions; [Embedding](embedding.md) is its consumer.

Both `mse` and `alignment_tolerant_mse` checkpoints are accepted. A checkpoint
must follow the current training contract, including an explicit
`objective.loss.type`; checkpoints that predate it are rejected with the
missing field named, and there is no fallback.

## Select element examples

The selection is an RGTools boolean mask in the xp-genomic-tools
boolean-mask format, aligned to the processed dataset's rows:

- A `.npy` file, or a `.npz` archive holding exactly one array (any member
  name). The container is recognized by content, not by file extension.
- NumPy `bool` dtype only. Integer `0`/`1`, float, and object arrays are
  rejected, never coerced.
- Shape `(N,)` or `(N, 1)`, where `N` is the processed dataset's element
  count in `dataset.json`.
- At least one `True` value.

Mask row `i` selects dataset row `i`. The mask is a row-aligned array, not a
region table; no region format is interpreted. Rows may come from any split,
so choosing held-out element examples is your analysis decision; each
selected row's split is recorded in the output manifest. Every mask problem is
reported against the mask file before the checkpoint is loaded.

## Run reconstruction

Pass the dataset directory, the full checkpoint file, the mask, and the output
directory. All four are required and every path is absolute:

```bash
track-encoder reconstruct --dataset /absolute/path/to/northwood_dataset --checkpoint /absolute/path/to/northwood_run/best.pt --mask /absolute/path/to/northwood_heldout_mask.npy --output /absolute/path/to/northwood_reconstructions
```

| Flag | Required | Default | Meaning |
| --- | --- | --- | --- |
| `--dataset` | yes | — | Processed-dataset directory |
| `--checkpoint` | yes | — | Full checkpoint file written by `train`, such as `best.pt` or `latest.pt` |
| `--mask` | yes | — | Boolean mask selecting dataset rows |
| `--output` | yes | — | Output destination; must be absent or empty |
| `--device` | no | `cuda` | Inference device: `cuda` or `cpu` |
| `--batch-size` | no | `32` | Positive integer number of element examples per inference batch |
| `--debug` | no | off | Print the full traceback on failure |

Selected rows are reconstructed in ascending processed-dataset row order,
regardless of how the mask was built, in evaluation mode without gradients.
`--batch-size` controls only memory use; results do not depend on it beyond
floating-point tolerance.

## Device

Reconstruction runs on CUDA by default and also supports CPU with
`--device cpu`, for example beside a CPU-only downstream analysis. Training
itself remains CUDA-only. `--device` accepts only `cuda` or `cpu`; there is no
GPU index option, so choose a GPU with `CUDA_VISIBLE_DEVICES`. If `cuda` is
requested but unavailable, the command stops after validating the dataset and
mask and suggests rerunning with `--device cpu`. Outputs are always written
from host memory, and CPU and CUDA reconstructions of the same checkpoint
agree within floating-point tolerance. The device used is recorded in the
manifest.

## Compatibility

The processed dataset passes the same validity checks as embedding export:
`dataset.json` must carry schema version `1`, and the **dataset identity**
recomputed over its content must match the recorded identity, so a changed or
hand-edited dataset is refused even at an unchanged path.

The dataset need not be the checkpoint's training dataset. Its channel count
and window length must match the model rebuilt from the checkpoint; a mismatch
is reported by field with the expected (model) and actual (dataset) values
before any inference. The manifest records the checkpoint's
`training_dataset_identity` and `matches_training_dataset`, which is `true`
only when the dataset identity equals it.

Channel names and orientation cannot be verified against a checkpoint. They
are copied from `dataset.json` into the
manifest, but **channel semantics and orientation are your responsibility**:
a separately prepared dataset must list the same tracks in the same order, in
the same orientation, as the training dataset for its reconstructions to be
meaningful.

## Interpreting reconstructions

Reconstructions are raw decoder output in the dataset's jointly normalized
units: each one is nonnegative and sums to one across all channels and
positions, like the processed signals. They are not denormalized, rescaled,
aligned, or otherwise post-processed.

Decoding is the same for both loss types: no shift search, alignment, or
canonicalization is applied. A model trained with `alignment_tolerant_mse` was
not penalized for placing signal anywhere within its trained radius, so its
reconstructions may be offset from the target by up to `max_shift_bp`
positions, shared across all channels of an element example. Read absolute
placement within that radius as incidental; signal morphology and relative
channel arrangement remain meaningful. The radius used in training is recorded
in the manifest.

## Output files

Publication is atomic: outputs are assembled in a staging directory and
appear only on success, and a failed run leaves no output. A successful run
writes:

| Path | Meaning |
| --- | --- |
| `reconstructions.npy` | `float32` reconstructions, shape `(selected, channels, window_length)` |
| Region table rows | The selected rows of the processed region table, in output order, under the original file name and format, plus the copied custom region schema when one was used |
| `reconstruction.json` | Versioned manifest identifying the rows, channels, dataset, checkpoint, objective, device, and build |

Target signals are not written. Read them from the one authoritative copy by
indexing `signals.npy` with the recorded `row_indices`: row `k` of
`reconstructions.npy` reconstructs row `row_indices[k]` of `signals.npy`, and
is the same genomic element as row `k` of the written region table.

An illustrative `reconstruction.json` from an `mse` checkpoint, with
placeholder identities:

```json
{
  "schema_version": 1,
  "reconstructions_file": "/absolute/path/to/northwood_reconstructions/reconstructions.npy",
  "regions": {
    "path": "/absolute/path/to/northwood_reconstructions/northwood_elements.bed3",
    "type": "bed3"
  },
  "row_alignment": "selected_processed_dataset_rows",
  "row_indices": [12, 305, 1840],
  "row_splits": ["validation", "test", "test"],
  "channels": ["northwood_track_alpha", "northwood_track_beta"],
  "orientation": "genomic",
  "normalization": "joint_sum",
  "window_length": 1000,
  "shape": [3, 2, 1000],
  "dtype": "float32",
  "dataset_identity": "0000000000000000000000000000000000000000000000000000000000000001",
  "checkpoint_file": "/absolute/path/to/northwood_run/best.pt",
  "checkpoint_identity": "0000000000000000000000000000000000000000000000000000000000000002",
  "training_dataset_identity": "0000000000000000000000000000000000000000000000000000000000000001",
  "matches_training_dataset": true,
  "objective_type": "reconstruction",
  "loss_type": "mse",
  "max_shift_bp": null,
  "device": "cuda",
  "package_version": "0.0.0+example",
  "source_revision": null
}
```

The manifest is validated against the packaged reconstruction schema before
publication. Its fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | Manifest schema version, `1` |
| `reconstructions_file` | Absolute path of `reconstructions.npy` |
| `regions` | Absolute `path` of the written region rows, plus the region `type`, or the absolute `schema` path of the copied custom region schema |
| `row_alignment` | Always `selected_processed_dataset_rows` |
| `row_indices` | Selected processed-dataset row indices, ascending, one per reconstruction |
| `row_splits` | Split of each selected row: `train`, `validation`, or `test` |
| `channels` | Channel names in order, copied from `dataset.json` |
| `orientation` | Dataset orientation, `genomic` |
| `normalization` | Dataset normalization, `joint_sum` |
| `window_length` | Positions per element example |
| `shape` | `[selected, channels, window_length]` |
| `dtype` | `float32` |
| `dataset_identity` | Dataset identity of the reconstructed dataset |
| `checkpoint_file` | Absolute path of the full checkpoint file used |
| `checkpoint_identity` | SHA-256 of the checkpoint file bytes |
| `training_dataset_identity` | Dataset identity recorded in the checkpoint at training time |
| `matches_training_dataset` | Whether `dataset_identity` equals `training_dataset_identity` |
| `objective_type` | Objective rebuilt from the checkpoint, `reconstruction` |
| `loss_type` | Training loss: `mse` or `alignment_tolerant_mse` |
| `max_shift_bp` | Effective trained radius for `alignment_tolerant_mse` (including the default of 50 when the configuration omitted it); `null` for `mse` |
| `device` | Device used: `cuda` or `cpu` |
| `package_version` | Installed Track Encoder package version |
| `source_revision` | Git commit when run from a source checkout, otherwise `null`; determined as for training's `environment.json` |

The outputs need only NumPy and JSON to read; no Track Encoder import is
required downstream.

## Errors

On invalid inputs the command exits nonzero with a contextual message that
names the responsible file and field, without a traceback unless `--debug` is
given. Invalid flag values (a `--device` other than `cuda` or `cpu`, or a
`--batch-size` that is not a positive integer) are command-line usage errors.
Checks run in this order, so the first problem found is the one reported:
output destination, dataset, mask, device, checkpoint, then fit.

| Problem | Field | Message begins with |
| --- | --- | --- |
| Nonempty output destination | `output_dir` | `Output directory is not empty` |
| Dataset content changed since preparation | `identity` | `Dataset content identity mismatch` |
| Mask dtype is not `bool` | `mask` | `Mask must have NumPy bool dtype` |
| Mask shape or length does not fit the dataset | `mask` | `Mask shape ... does not match dataset rows` |
| `.npz` archive with zero or several arrays | `mask` | `Mask .npz archive must contain exactly one array` |
| All-`False` mask | `mask` | `Mask selects no rows` |
| Missing or unreadable mask | `mask` | `Mask is not a readable .npy file or single-array .npz archive` |
| CUDA requested but unavailable | `device` | `CUDA is not available; rerun with --device cpu` |
| Checkpoint path is a directory, such as a run directory | `checkpoint` | `Expected a full checkpoint file but got a directory` |
| Checkpoint is `encoder.json` | `checkpoint` | `Got an encoder artifact manifest, not a full checkpoint` |
| Checkpoint is `encoder.pt` | `checkpoint` | `Got encoder-only state, not a full checkpoint` |
| Checkpoint file does not exist | `checkpoint` | `Full checkpoint file not found` |
| File is not a checkpoint written by `train` | `checkpoint` | `Not a full checkpoint written by train` |
| Checkpoint predates the current contract | first missing field, such as `objective.loss.type` | `Checkpoint is missing current-contract content` |
| Objective type unknown | `objective.type` | `Unsupported objective type` |
| Objective cannot reconstruct | `objective.type` | `Objective type ... does not support reconstruction` |
| Channel count or window length mismatch | `num_channels` or `window_length` | `Dataset num_channels does not match checkpoint model: expected 2, got 3` (expected is the model's value, got is the dataset's) |

The three encoder-artifact and directory errors all explain that encoder
artifacts carry no decoder and ask for a full checkpoint file written by
`train`, such as `best.pt`.
