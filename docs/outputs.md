# Outputs

Track Encoder produces three artifact families: processed datasets (see
[Preparation](preparation.md)), training runs with resumable checkpoints and
an encoder-only artifact (see [Training](training.md)), and row-aligned
embedding exports (see [Embedding](embedding.md)).

## What the alpha framework does not do

To avoid mistaking plans for capabilities: the current framework performs no
region discovery, no peak discovery, no biological evaluation of element
membership, no alternative architectures beyond the supported dilated
convolutional encoder, and no objectives beyond full-window reconstruction.
Demonstration hyperparameters in the code repository verify mechanics only and
are not endorsed defaults. Downstream analyses such as clustering or
dimensionality reduction operate on exported embeddings outside this
framework.
