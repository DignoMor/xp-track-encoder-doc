# Track Encoder

Track Encoder learns compact representations of genomic signal associated with
selected genomic regions. Each **genomic element** — a region on a reference
genome considered as one biological object — is paired with its
nucleotide-resolution signal measurements to form an **element example**. The
framework encodes each element example as a fixed-length learned
representation called an **embedding**.

## Whether this workflow applies to you

This guide applies if you already have genomic elements of interest and the
**signal tracks** — nucleotide-resolution measurements over genomic
coordinates — that you want to represent. Region selection happens upstream:
Track Encoder does not select regions, call transcriptional elements, or
create data partitions. It starts from your elements, your tracks, and your
split assignments, and carries them through three stages:

1. **Prepare** your elements and tracks into a processed dataset.
2. **Train** a reconstruction model on the processed dataset.
3. **Export** one embedding per genomic element from a compatible encoder.

The [Inputs](inputs.md) page describes everything you must supply. The
[Preparation](preparation.md) page walks from those inputs to a verified
processed dataset. Training and embedding guidance follows the same journey;
see [Training](training.md) and [Embedding](embedding.md).

## What you must supply

This documentation bundles no input data. You supply every input file:
regions, signal tracks, split assignments, and the reference FASTA. The
examples use fictional names such as `northwood_elements` with clearly marked
`/absolute/path/to/` placeholders. Substitute your own absolute paths before
running any command.

The code repository keeps a small deterministic synthetic fixture for
mechanical verification of the workflow. It is not scientific input, not
biological evidence, and not part of the researcher journey described here.

## Installation

Track Encoder is installed from the code repository. Follow its maintained
instructions:

- [xp-track-encoder installation](https://github.com/haiyuan-yu-lab/xp-track-encoder)

Training runs on CUDA, so choose a CUDA-capable machine before preparing a
run. Preparation and embedding export do not train models, but the dataset you
prepare here is consumed by CUDA training.

## Current scope

This site describes only the implemented alpha framework: preparation of
row-aligned genomic signals, reconstruction training with a dilated
convolutional encoder, and embedding export. Planned architectures,
objectives, region discovery, and biological evaluation are out of scope and
are named as unsupported in the [Outputs](outputs.md) page.
