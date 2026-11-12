# Training

Training learns a reconstruction model from two processed datasets: it fits
a **train dataset** and selects its full checkpoint on a **val dataset**. It
starts from the processed numeric interface described in
[Preparation](preparation.md) and never invokes preparation: channel count and
window length come from the train dataset's manifest, and both dataset
identities are checked before any module is built. Training uses every row of
the train dataset and every row of the val dataset, and performs no test
evaluation; scoring a full checkpoint on a test dataset is a separate step,
described in [Evaluation](evaluation.md).

Training runs on CUDA only. Choose a CUDA-capable machine before launching a
run; there is no supported CPU training path.

## What training learns

Each element example — one genomic element paired with its jointly
sum-normalized signal — passes through two independently owned pieces: a
dilated convolutional encoder and a reconstruction objective with its own
decoder. Encoder architecture and training objective are selected
independently by stable type names, so the same encoder interface can support
later training approaches.

### Dilated CNN encoder

The supported architecture type is `dilated_cnn`. It accepts a batch of
processed element examples with shape `(batch, channels, positions)` and
returns one deterministic embedding per element with shape `(batch,
embedding_dimensions)`.

Each layer applies a same-padded dilated convolution with an odd kernel size
and GELU activation at its incoming resolution, followed by local average
pooling only when the next layer declares a coarser resolution. Resolutions
are declared per layer in base pairs with an explicit spatial meaning:

- The first layer resolution is `1` base pair.
- Resolutions are nondecreasing, and each transition is an integer multiple
  of the preceding resolution. A schedule such as `1, 2, 4` denotes two-fold
  local pooling between successive convolution layers.
- The ratio between adjacent resolutions sets the pooling kernel and stride,
  and the incoming spatial length must divide evenly by it.
- Convolution kernels must be odd.

These relationships are validated semantically after schema validation and
before any PyTorch module is constructed, so an even kernel, a decreasing or
non-multiple resolution step, or a pooling ratio incompatible with the
dataset window length fails early with a contextual error. The final reduced
feature map is flattened without reordering its channel or spatial axes, then
projected to a deterministic embedding. Local pooling establishes groundwork
for local translation stability, but quantitative shift testing and
enforcement are deferred out of scope.

### Reconstruction objective

The supported objective type is `reconstruction`. It owns a training-only
decoder: the decoder maps an embedding back to the configured input shape
through a learned projection to the reduced spatial grid, deterministic
linear upsampling, same-padded convolutions at each finer resolution, and one
softmax applied jointly across channels and positions. Each reconstruction is
therefore nonnegative and sums to one, matching the prepared signal domain.

The fixed configuration must explicitly select a reconstruction loss through
`objective.loss.type`. Choose `mse` for full-window coordinate-wise mean
squared error averaged over batch, channel, and position dimensions. Choose
`alignment_tolerant_mse` to allow a bounded shared translation when comparing
each reconstructed element with its target. Missing loss selection has no
default, so existing configurations must be migrated before training or
resume.

The alignment-tolerant loss uses `objective.loss.max_shift_bp`, an optional
fixed radius that defaults to 50 bp. It must be an integer at least zero and
strictly smaller than the dataset window length. If the 50 bp default is too
large for a short window, set a smaller radius; the value is never clamped.
Radius zero is equivalent to ordinary MSE. The loss compares offsets from
`-max_shift_bp` through `+max_shift_bp`, independently choosing one offset
per element and sharing it across channels. Positive offset moves reconstructed
signal toward increasing position indices. Zero-padded extended comparisons
retain all target and reconstructed signal at window edges and divide by the
original channel count times window length. The selected loss is no greater
than unaligned MSE within floating-point tolerance because offset zero is
included. This loss relaxes reconstruction pressure on placement inside the
radius; it does not guarantee stable embeddings for translated inputs.

Both loss choices and the effective radius are fixed experiment configuration
and cannot be placed in `hp.json`. The objective exposes selected loss plus
named components and metrics through one interface; the generic trainer
backpropagates only the selected total loss and records the reported metrics
each epoch. The saved encoder and exported embeddings never depend on the
decoder: resumable checkpoints store objective state opaquely, and the
encoder-only inference artifact contains no decoder or optimizer state.

## Two configuration documents

Training accepts exactly two user-authored JSON documents with disjoint
ownership. Hyperparameters never override fixed configuration, unknown fields
are rejected in both documents, and every path is absolute — commands use
paths exactly as written.

- `config.json` declares choices held fixed for the run: the train and val
  datasets, architecture type, objective type, optimizer type, seed, epoch
  budget, output destination, and CUDA device.
- `hp.json` supplies one concrete set of tunable values — never a search
  space — under disjoint `architecture`, `objective`, `optimizer`, and
  `training` namespaces. The fixed architecture type selects which
  hyperparameter schema applies.

Both documents conform to versioned schemas, and semantic checks (resolution
transitions, dataset compatibility) run after schema validation. The run
saves both originals plus the resolved experiment configuration, so results
trace back to exact data, software, and hyperparameters.

### Fixed experiment configuration

Write the fixed configuration with absolute paths. Every path below is a
clearly marked placeholder beginning with `/absolute/path/to/`; the names are
fictional and continue the preparation journey. Substitute your own absolute
paths, keeping them absolute, and the result validates against the shipped
training configuration schema.

```json
{
  "schema_version": 3,
  "data": {
    "train_dataset_path": "/absolute/path/to/northwood_prepared/train",
    "val_dataset_path": "/absolute/path/to/northwood_prepared/val"
  },
  "architecture": {
    "type": "dilated_cnn"
  },
  "objective": {
    "type": "reconstruction",
    "loss": {
      "type": "mse"
    }
  },
  "optimizer": {
    "type": "adamw"
  },
  "run": {
    "seed": 11,
    "epochs": 40,
    "output_dir": "/absolute/path/to/northwood_run",
    "device": "cuda"
  }
}
```

`data.train_dataset_path` names the train dataset and `data.val_dataset_path`
the val dataset, usually the `train/` and `val/` directories of one
preparation. Because a dataset's role is set here rather than in the dataset,
swapping the val dataset is a path change. The val dataset must agree with the
train dataset on `channels`, `window_length`, `orientation`, `normalization`,
and `dtype`; a disagreement is rejected naming that field. Both paths may name
the same dataset, for example for an overfitting check. The configuration's
`schema_version` is `3`. Any other version is rejected by field
`schema_version`, with no fallback: a configuration with schema version `1`
and a single dataset path must be rewritten with both paths, and a
configuration with schema version `2` only needs its version set to `3`.
Full checkpoints from runs whose configuration was version `2`
cannot be resumed, but they remain valid inputs to `embed` (through the run's
encoder artifact), `reconstruct`, and `evaluate`.

`architecture.type` is always `dilated_cnn`, `objective.type` is always
`reconstruction`, and `optimizer.type` is always `adamw` in this release.
`objective.loss.type` must explicitly be `mse` or
`alignment_tolerant_mse`; the latter may include a fixed `max_shift_bp`.
Neither loss choice nor radius can be set in `hp.json`. `run.device` is always
`cuda`: CPU training is not supported.
`run.epochs` is the total epoch budget, and `run.seed` drives deterministic
batching and algorithms. Unknown fields are rejected, so a misspelled field
fails early rather than being ignored.

To select alignment-tolerant reconstruction, replace the example's
`objective` value with:

```json
{
  "type": "reconstruction",
  "loss": {
    "type": "alignment_tolerant_mse",
    "max_shift_bp": 50
  }
}
```

Omit `max_shift_bp` to use 50 bp. Set it to zero to recover ordinary MSE;
for every dataset, the effective radius must remain smaller than its window
length.

### Tunable hyperparameters

Write the hyperparameters beside the fixed configuration. The values below
are illustrative only — not tuned, not endorsed, and not defaults. They
exist so the document shape validates; choose values deliberately for your
own study. Substitute your own absolute paths (none appear here, but any
path you add must be absolute) and the result validates against the shipped
dilated-CNN hyperparameter schema.

```json
{
  "schema_version": 1,
  "architecture": {
    "layers": [
      {"channels": 12, "kernel_size": 5, "dilation": 1, "resolution_bp": 1},
      {"channels": 24, "kernel_size": 5, "dilation": 2, "resolution_bp": 2},
      {"channels": 48, "kernel_size": 3, "dilation": 2, "resolution_bp": 4}
    ],
    "embedding_dim": 16
  },
  "objective": {},
  "optimizer": {
    "learning_rate": 0.0005,
    "weight_decay": 0.00001
  },
  "training": {
    "batch_size": 16
  }
}
```

Each layer declares its channel width, odd kernel size, dilation, and
cumulative resolution in base pairs; `embedding_dim` sets the fixed embedding
length. The `objective` namespace carries no tunable fields for
reconstruction. Demonstration values kept in the code repository verify
mechanics only and are likewise not scientifically endorsed defaults.

## Run training

Launch training with the absolute paths of both documents:

```bash
track-encoder train --config /absolute/path/to/config.json --hp /absolute/path/to/hp.json
```

The command refuses a nonempty output directory: training never merges into
or overwrites existing outputs. Train dataset rows are shuffled by a seeded
generator while val dataset rows keep dataset order, and incomplete final
batches are never dropped. On invalid data or configuration the command
exits nonzero and reports the responsible document, field, track, or region
row without a traceback by default; rerun with `--debug` for the full
traceback.

A fresh run records `config.json`, `hp.json`, the resolved experiment
configuration (`resolved_experiment.json`, including effective
`max_shift_bp`), and the software environment
(`environment.json`: package, Python, PyTorch, CUDA, and genomic-element
library versions, GPU model, deterministic-algorithm setting, and Git commit
when available).

## Checkpoints, metrics, and the run summary

Each epoch appends one record to `metrics.jsonl` with the epoch number,
`train_reconstruction_loss`, `val_reconstruction_loss`,
`train_unaligned_reconstruction_mse`, and
`val_unaligned_reconstruction_mse`, plus current and best checkpoint
identities and elapsed epoch time. The `train_` values are computed over the
train dataset and the `val_` values over the val dataset. The selected loss
and ordinary unaligned MSE are reported separately. They are equal for `mse`;
aligned selected loss can be lower for `alignment_tolerant_mse`. Checkpoint
selection uses `val_reconstruction_loss`. Two resumable full checkpoints are
maintained atomically, so an interrupted write cannot corrupt recoverable
state:

| Path | Meaning |
| --- | --- |
| `latest.pt` | Replaced atomically after every epoch; holds encoder, objective, and optimizer state, completed epoch, random-number-generator state, best val loss so far, original and resolved configurations, and the train and val dataset identities |
| `best.pt` | Updated atomically only when val reconstruction loss improves; the full checkpoint selected on the val dataset |

`summary.json` records only `best_val_reconstruction_loss` and `epochs`.
Training reports no test metrics: to score `best.pt` on your test dataset,
run `track-encoder evaluate` after training (see [Evaluation](evaluation.md)).
An encoder-only inference artifact (`encoder.pt` plus its `encoder.json`
manifest) is derived from `best.pt`; it carries the encoder state, content
identity, architecture, channels, window length, normalization, and embedding
dimension needed for compatible inference. The trained encoder feeds
[Embedding](embedding.md), and the full artifact family is summarized under
[Outputs](outputs.md).

## Resume an interrupted run

Resume is explicit. Reissue the training command with identical
configuration and hyperparameters plus the checkpoint to continue from:

```bash
track-encoder train --config /absolute/path/to/config.json --hp /absolute/path/to/hp.json --resume /absolute/path/to/northwood_run/latest.pt
```

Resume compatibility is exact: the checkpoint's train and val dataset
identities, original fixed configuration, original hyperparameters, and resolved experiment must
all match the supplied documents, and random-number-generator state is
restored so continuation agrees numerically with an uninterrupted run in the
same locked software and GPU environment. The configured epoch count remains
the total target — resuming toward `epochs: 40` from epoch 25 trains epochs
26 through 40, it does not add 40 more. A missing checkpoint, a changed
train or val dataset, or any edited configuration or hyperparameter value
fails with a contextual error instead of silently starting a different
experiment; a changed dataset is reported by its own field,
`data.train_dataset_path` or `data.val_dataset_path`. Checkpoints written by
earlier releases record a single dataset identity and are rejected by field
`train_dataset_identity`, with no fallback. Resume
identity includes the resolved effective loss radius, including the default
50 bp, so changing the loss or radius is incompatible.

## Alpha limits

To avoid mistaking plans for capabilities: the current framework trains one
architecture (`dilated_cnn`) under one objective (full-window
reconstruction) with one optimizer (`adamw`) through a transparent CUDA-only
loop without mixed precision. There is no CPU training, no distributed
training, no hyperparameter search orchestration, and no early stopping. Masking,
contrastive or generative latent formulations, embedding-stability evaluation,
and downstream biological evaluation are out of scope, as summarized under
[Outputs](outputs.md). Start from verified processed datasets (see
[Preparation](preparation.md)) and keep their identities stable: resume and
inference compare dataset identities rather than trusting paths alone.
