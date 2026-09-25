# Training

Training consumes a prepared dataset and learns a reconstruction model. It
starts from the processed numeric interface described in
[Preparation](preparation.md) and never invokes preparation: channel count,
window length, and split assignments all come from the dataset manifest, and
the dataset identity is checked before any module is built.

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

The loss is full-window coordinate-wise mean squared error between the
reconstructed and input jointly normalized signals, averaged over batch,
channel, and position dimensions. The objective exposes total loss plus named
components and metrics through one interface; the generic trainer
backpropagates only the total loss and records every named component and
metric each epoch. The saved encoder and exported embeddings never depend on
the decoder: resumable checkpoints store objective state opaquely, and the
encoder-only inference artifact contains no decoder or optimizer state.

## Two configuration documents

Training accepts exactly two user-authored JSON documents with disjoint
ownership. Hyperparameters never override fixed configuration, unknown fields
are rejected in both documents, and every path is absolute — commands use
paths exactly as written.

- `config.json` declares choices held fixed for the run: the processed
  dataset, architecture type, objective type, optimizer type, seed, epoch
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
  "schema_version": 1,
  "data": {
    "dataset_path": "/absolute/path/to/northwood_dataset"
  },
  "architecture": {
    "type": "dilated_cnn"
  },
  "objective": {
    "type": "reconstruction"
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

`architecture.type` is always `dilated_cnn`, `objective.type` is always
`reconstruction`, and `optimizer.type` is always `adamw` in the current
framework. `run.device` is always `cuda`: CPU training is not supported.
`run.epochs` is the total epoch budget, and `run.seed` drives deterministic
batching and algorithms. Unknown fields are rejected, so a misspelled field
fails early rather than being ignored.

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
or overwrites existing outputs. Training rows are shuffled by a seeded
generator while validation and test rows keep dataset order, and incomplete
final batches are never dropped. On invalid data or configuration the command
exits nonzero and reports the responsible document, field, track, or region
row without a traceback by default; rerun with `--debug` for the full
traceback.

A fresh run records `config.json`, `hp.json`, the resolved experiment
configuration (`resolved_experiment.json`), and the software environment
(`environment.json`: package, Python, PyTorch, CUDA, and genomic-element
library versions, GPU model, deterministic-algorithm setting, and Git commit
when available).

## Checkpoints, metrics, and the one-time test

Each epoch appends one record to `metrics.jsonl` with the epoch number, mean
training and validation reconstruction losses, current and best checkpoint
identities, and elapsed epoch time. Two resumable checkpoints are maintained
atomically, so an interrupted write cannot corrupt recoverable state:

| Path | Meaning |
| --- | --- |
| `latest.pt` | Replaced atomically after every epoch; holds encoder, objective, and optimizer state, completed epoch, random-number-generator state, original and resolved configurations, and the processed-dataset identity |
| `best.pt` | Updated atomically only when validation reconstruction loss improves; the model is selected by validation loss without consulting the test split |

After the epoch budget completes, the best validation checkpoint is loaded
once and evaluated on the test split. That single held-out score is written
to `summary.json` alongside the best validation loss and epoch count, and it
does not affect model selection. An encoder-only inference artifact
(`encoder.pt` plus its `encoder.json` manifest) is derived from `best.pt`;
it carries the encoder state, content identity, architecture, channels,
window length, normalization, and embedding dimension needed for compatible
inference. The trained encoder feeds [Embedding](embedding.md), and the full
artifact family is summarized under [Outputs](outputs.md).

## Resume an interrupted run

Resume is explicit. Reissue the training command with identical
configuration and hyperparameters plus the checkpoint to continue from:

```bash
track-encoder train --config /absolute/path/to/config.json --hp /absolute/path/to/hp.json --resume /absolute/path/to/northwood_run/latest.pt
```

Resume compatibility is exact: the checkpoint's dataset identity, original
fixed configuration, original hyperparameters, and resolved experiment must
all match the supplied documents, and random-number-generator state is
restored so continuation agrees numerically with an uninterrupted run in the
same locked software and GPU environment. The configured epoch count remains
the total target — resuming toward `epochs: 40` from epoch 25 trains epochs
26 through 40, it does not add 40 more. A missing checkpoint, a changed
dataset, or any edited configuration or hyperparameter value fails with a
contextual error instead of silently starting a different experiment.

## Alpha limits

To avoid mistaking plans for capabilities: the current framework trains one
architecture (`dilated_cnn`) under one objective (full-window
reconstruction) with one optimizer (`adamw`) through a transparent CUDA-only
loop without mixed precision. There is no CPU training, no distributed
training, no hyperparameter search orchestration, and no early stopping. Masking,
contrastive or generative latent formulations, shift-aware reconstruction,
and downstream biological evaluation are out of scope, as summarized under
[Outputs](outputs.md). Start from a verified processed dataset (see
[Preparation](preparation.md)) and keep its identity stable: resume and
inference compare dataset identities rather than trusting paths alone.
