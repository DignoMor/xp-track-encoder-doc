# Track Encoder

**Current release: 0.1.0a2 (alpha).**

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
split assignment, and carries them through four stages:

1. **Prepare** your elements and tracks into processed datasets: each split
   of your split assignment becomes its own standalone processed dataset.
2. **Train** a reconstruction model on a **train dataset**, selecting its full
   checkpoint on a **val dataset**.
3. **Evaluate** the selected full checkpoint on a **test dataset**, or on any
   other compatible processed dataset.
4. **Export** one embedding per genomic element from a compatible encoder.

Train, val, and test are roles you give a processed dataset when you pass it
to a command; nothing in the dataset itself marks its role.

The [Inputs](inputs.md) page describes everything you must supply. The
[Preparation](preparation.md) page walks from those inputs to verified
processed datasets. Training, evaluation, and embedding guidance follows the
same journey; see [Training](training.md), [Evaluation](evaluation.md), and
[Embedding](embedding.md). To inspect what a trained model retains,
[Reconstruction](reconstruction.md) reconstructs selected element examples
from a full checkpoint.

## What you must supply

This documentation bundles no input data. You supply every input file:
regions, signal tracks, a split assignment, and the reference FASTA. The
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
run. Preparation and embedding export do not train models, but the datasets
you prepare here are consumed by CUDA training. Evaluation and reconstruction
run on CUDA or CPU.

## Current scope

This site describes only the implemented alpha framework: preparation of
row-aligned genomic signals, reconstruction training with a dilated
convolutional encoder, evaluation of full checkpoints, embedding export, and
reconstruction of selected element examples from full checkpoints. Planned architectures,
objectives, region discovery, and biological evaluation are out of scope and
are named as unsupported in the [Outputs](outputs.md) page.

This alpha release changes the processed-dataset layout, the training
configuration, and the full-checkpoint contract. Datasets, configurations, and
checkpoints from earlier releases are rejected by field; see
[Outputs](outputs.md#regenerate-earlier-artifacts) for what to regenerate.

## Agent map

Agents can start from the concise [llms.txt](llms.txt) link map, which points
to the pages above without duplicating them.
