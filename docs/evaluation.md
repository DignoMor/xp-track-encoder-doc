# Evaluation

Evaluation scores a trained model on a processed dataset, outside of training.
`track-encoder evaluate` rebuilds the encoder and the reconstruction objective
from a **full checkpoint** written by training (see [Training](training.md)),
scores every selected element example of a processed dataset (see
[Preparation](preparation.md)), and reports the checkpoint's own
reconstruction loss and the ordinary unaligned MSE, in aggregate and per row.

Training reports no test metrics. The usual final step of an experiment is to
evaluate the val-selected `best.pt` on the **test dataset** from the same
preparation. Because a dataset's role is only how you use it, you can equally
evaluate any full checkpoint on any compatible processed dataset, again and
without retraining: for example, a dataset prepared from another cell type
with an all-test split assignment.

Evaluation does not train, select checkpoints, write reconstructions or
target signals, report metrics beyond the selected loss and the unaligned
MSE, modify the checkpoint or its run directory, or write anywhere except the
output directory.

## What you need

- **A full checkpoint file** written by `track-encoder train`, such as the
  val-selected `best.pt` or the most recent `latest.pt`. Name the file itself:
  the command never chooses a checkpoint from a run directory. An encoder
  artifact (`encoder.json` plus `encoder.pt`) carries no decoder and is
  refused. No training configuration, hyperparameter document, or train or
  val dataset path is needed.
- **A processed dataset directory**, typically the `test/` directory of your
  preparation. Its channel count and window length must fit the checkpoint
  (see [Compatibility](#compatibility)).
- **Optionally, a boolean mask** selecting the element examples to score.
  Without `--mask`, every row of the dataset is scored.
- **An empty output destination.** Evaluation never merges into or overwrites
  existing outputs.

## Run evaluation

Pass the dataset directory, the full checkpoint file, and the output
directory. Every path is absolute:

```bash
track-encoder evaluate --dataset /absolute/path/to/northwood_prepared/test --checkpoint /absolute/path/to/northwood_run/best.pt --output /absolute/path/to/northwood_evaluation
```

| Flag | Required | Default | Meaning |
| --- | --- | --- | --- |
| `--dataset` | yes | — | Processed-dataset directory to score |
| `--checkpoint` | yes | — | Full checkpoint file written by `train`, such as `best.pt` or `latest.pt` |
| `--output` | yes | — | Output destination; must be absent or empty |
| `--mask` | no | every row | Boolean mask selecting rows of the given dataset |
| `--device` | no | `cuda` | Device: `cuda` or `cpu` |
| `--batch-size` | no | `32` | Positive integer number of element examples per batch |
| `--debug` | no | off | Print the full traceback on failure |

The mask follows the boolean-mask rules described under
[Reconstruction](reconstruction.md#select-element-examples): NumPy `bool`
dtype, shape `(N,)` or `(N, 1)` where `N` is the given dataset's element
count, and at least one `True` value. Mask row `i` selects row `i` of the
dataset you pass; a mask whose length is not this dataset's element count,
such as one built for the train dataset, is refused.

Evaluation runs on CUDA by default and also on CPU with `--device cpu`. If
`cuda` is requested but unavailable, the command stops and suggests rerunning
with `--device cpu`. CPU and CUDA scores of the same checkpoint agree within
floating-point tolerance, not bitwise; the device used is recorded in the
manifest.

## What is scored

Selected rows are scored in ascending dataset row order, in evaluation mode
without gradients, by the same evaluation step training uses for its val
loss. Each row receives two values:

- its **reconstruction loss** under the checkpoint's own selected loss:
  `mse`, or `alignment_tolerant_mse` with the checkpoint's effective
  `max_shift_bp`;
- its **unaligned reconstruction MSE**, the ordinary position-exact MSE.

For an `mse` checkpoint the two are equal. For an `alignment_tolerant_mse`
checkpoint the loss can be lower, and the gap shows how much the alignment
tolerance excuses.

The aggregates are means over the selected rows, accumulated as training
accumulates its val loss. Evaluating `best.pt` on the run's val dataset with
the training batch size therefore reproduces `best_val_reconstruction_loss`
from the run's `summary.json`, within training's numerical tolerance. Other
batch sizes change the aggregates only within floating-point tolerance.

## Compatibility

The dataset passes the same validity checks as embedding export and
reconstruction: `dataset.json` must carry schema version `2`, and the
**dataset identity** recomputed over its content must match the recorded
identity. Its channel count and window length must match the encoder input
the full checkpoint was trained for; a mismatch is reported by field with the
expected (checkpoint) and actual (dataset) values before any scoring.

The manifest records the checkpoint's `train_dataset_identity` and
`val_dataset_identity`, and whether the scored dataset is either one:
`matches_train_dataset` is `true` only for the checkpoint's train dataset and
`matches_val_dataset` only for its val dataset. Both are `false` for a test
dataset or any separately prepared dataset, which is how you confirm you are
scoring data the model neither fit nor was selected on. As for
reconstruction, channel names and orientation cannot be verified against a
checkpoint: a separately prepared dataset must list the same tracks in the
same order and orientation as the train dataset for its scores to be
meaningful.

## Output files

Publication is atomic: outputs are assembled in a staging directory and
appear only on success, and a failed run leaves no output. A successful run
writes:

| Path | Meaning |
| --- | --- |
| `evaluation.json` | Versioned manifest identifying the dataset, checkpoint, objective, selected rows, aggregate scores, device, and build |
| `reconstruction_losses.npy` | `float32`, shape `(selected,)`: each selected row's reconstruction loss, aligned to `row_indices` |
| `unaligned_reconstruction_mse.npy` | `float32`, shape `(selected,)`: each selected row's unaligned MSE, aligned to `row_indices` |

Both per-row files are always written. Value `k` of each belongs to row
`row_indices[k]` of the scored dataset; join it back to your source elements
through that dataset's `source_rows.npy`. Their means equal the manifest
aggregates up to floating-point summation order and `float32` storage.

An illustrative `evaluation.json` for `best.pt` of an `mse` run scored on its
test dataset, with placeholder identities:

```json
{
  "schema_version": 1,
  "dataset_identity": "0000000000000000000000000000000000000000000000000000000000000003",
  "checkpoint_file": "/absolute/path/to/northwood_run/best.pt",
  "checkpoint_identity": "0000000000000000000000000000000000000000000000000000000000000004",
  "train_dataset_identity": "0000000000000000000000000000000000000000000000000000000000000001",
  "val_dataset_identity": "0000000000000000000000000000000000000000000000000000000000000002",
  "matches_train_dataset": false,
  "matches_val_dataset": false,
  "objective_type": "reconstruction",
  "loss_type": "mse",
  "max_shift_bp": null,
  "row_indices": [0, 1, 2, 3],
  "num_rows": 4,
  "reconstruction_loss": 0.00021,
  "unaligned_reconstruction_mse": 0.00021,
  "reconstruction_losses_file": "/absolute/path/to/northwood_evaluation/reconstruction_losses.npy",
  "unaligned_reconstruction_mse_file": "/absolute/path/to/northwood_evaluation/unaligned_reconstruction_mse.npy",
  "device": "cuda",
  "package_version": "0.0.0+example",
  "source_revision": null
}
```

The manifest is validated against the packaged evaluation schema before
publication. Its fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | Manifest schema version, `1` |
| `dataset_identity` | Dataset identity of the scored dataset |
| `checkpoint_file` | Absolute path of the full checkpoint file used |
| `checkpoint_identity` | SHA-256 of the checkpoint file bytes |
| `train_dataset_identity` | Train dataset identity recorded in the checkpoint |
| `val_dataset_identity` | Val dataset identity recorded in the checkpoint |
| `matches_train_dataset` | Whether `dataset_identity` equals `train_dataset_identity` |
| `matches_val_dataset` | Whether `dataset_identity` equals `val_dataset_identity` |
| `objective_type` | Objective rebuilt from the checkpoint, `reconstruction` |
| `loss_type` | The checkpoint's loss: `mse` or `alignment_tolerant_mse` |
| `max_shift_bp` | Effective trained radius for `alignment_tolerant_mse` (including the default of 50 when the configuration omitted it); `null` for `mse` |
| `row_indices` | Selected dataset row indices, ascending |
| `num_rows` | Number of selected rows |
| `reconstruction_loss` | Mean reconstruction loss over the selected rows |
| `unaligned_reconstruction_mse` | Mean unaligned MSE over the selected rows |
| `reconstruction_losses_file` | Absolute path of `reconstruction_losses.npy` |
| `unaligned_reconstruction_mse_file` | Absolute path of `unaligned_reconstruction_mse.npy` |
| `device` | Device used: `cuda` or `cpu` |
| `package_version` | Installed Track Encoder package version |
| `source_revision` | Git commit when run from a source checkout, otherwise `null`; determined as for training's `environment.json` |

The outputs need only NumPy and JSON to read; no Track Encoder import is
required downstream.

## Errors

On invalid inputs the command exits nonzero with a contextual message that
names the responsible file and field, without a traceback unless `--debug` is
given. Invalid flag values (a `--device` other than `cuda` or `cpu`, a
`--batch-size` that is not a positive integer, or a missing required flag)
are command-line usage errors. Checks run in this order, so the first problem
found is the one reported: output destination, dataset, mask, device,
checkpoint, then fit.

| Problem | Field | Message begins with |
| --- | --- | --- |
| Nonempty output destination | `output_dir` | `Output directory is not empty` |
| Dataset schema version is not `2`, such as a dataset prepared by an earlier release | `schema_version` | `Unsupported dataset schema version` |
| Dataset content changed since preparation | `identity` | `Dataset content identity mismatch` |
| Mask problem: wrong dtype or shape, a length that does not fit this dataset, an all-`False` selection, or an unreadable file | `mask` | as listed under [Reconstruction](reconstruction.md#errors) |
| CUDA requested but unavailable | `device` | `CUDA is not available; rerun with --device cpu` |
| Checkpoint is a run directory, an encoder artifact, missing, or not written by `train` | `checkpoint` | as listed under [Reconstruction](reconstruction.md#errors) |
| Checkpoint written by an earlier release, with a single dataset identity | `train_dataset_identity` or `val_dataset_identity` | `Checkpoint is missing current-contract content` |
| Channel count or window length mismatch | `num_channels` or `window_length` | `Dataset num_channels does not match the full checkpoint: expected 2, got 3` (expected is the checkpoint's value, got is the dataset's) |
