# Outputs

Track Encoder produces four artifact families: processed datasets (see
[Preparation](preparation.md)), training runs with resumable full checkpoints
and an encoder-only artifact (see [Training](training.md)), row-aligned
embedding exports (see [Embedding](embedding.md)), and reconstructions of
selected element examples from a full checkpoint (see
[Reconstruction](reconstruction.md)).

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
