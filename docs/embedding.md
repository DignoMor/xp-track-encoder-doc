# Embedding

Embedding export encodes every element example in a processed dataset into
one fixed-length learned representation. Start from a verified processed
dataset (see [Preparation](preparation.md)) and the trained run that produced
a compatible encoder artifact (see [Training](training.md)). The export writes
`embeddings.npy`, `embeddings.json`, and a copy of the region information into
an output directory, preserving processed-dataset row order so each embedding
joins back to the correct genomic element.

## What you need

- **A processed dataset directory** holding `dataset.json`, `signals.npy`,
  the copied region table, and `split.npy`. Confirm the element count, channel
  names, and window length in `dataset.json` before exporting.
- **A compatible encoder artifact**: the trained run directory holding
  `encoder.json` plus `encoder.pt`. The artifact derives from the
  validation-selected checkpoint and carries only the state and metadata
  required for inference — no decoder or optimizer state.
- **An empty output destination.** Export never merges into or overwrites
  existing outputs.

`encoder.json` records the contract the dataset must satisfy: the
`dilated_cnn` architecture type and its hyperparameters, the channel names in
order, the window length, `orientation` (`genomic`), `normalization`
(`joint_sum`), the embedding dimension, and the SHA-256 encoder identity
computed over canonical encoder metadata plus the state-file bytes.

## Run export

Pass the dataset directory, the encoder artifact location, and the output
directory. All three arguments are required and every path is absolute:

```bash
track-encoder embed --dataset /absolute/path/to/northwood_dataset --checkpoint /absolute/path/to/northwood_run --output /absolute/path/to/northwood_embeddings
```

`--dataset` is the processed-dataset directory. `--checkpoint` is the trained
run directory that holds `encoder.json` (or, equivalently, the path of its
`encoder.json` file directly) — not `best.pt` or `latest.pt`. `--output` is
the export destination, which must not exist as a nonempty directory.

On incompatible inputs the command exits nonzero and names the responsible
field without a traceback by default; rerun with `--debug` for the full
traceback. Export runs the encoder over every processed element in order.

## Compatibility and refusal

Export compares content, not filenames. It recomputes the SHA-256 dataset
identity over canonical metadata and the region, signal, and split contents
and compares it with the identity recorded in `dataset.json`; it verifies the
encoder identity on load in the same way. Changed content therefore fails even
when the path is unchanged. The export refuses incompatible inputs instead of
producing silently misaligned embeddings:

- Dataset channels, in declared order, must equal the encoder channels.
- Dataset window length, orientation, and normalization must equal the
  encoder's recorded values.
- The dataset manifest must carry schema version `1`, and its recomputed
  content identity must match the recorded identity.
- The encoder manifest must validate, and its recorded identity must match
  the recomputed identity over its metadata and state bytes.
- The output directory must be absent or empty.

## Exported files

A successful run writes an export directory containing:

| Path | Meaning |
| --- | --- |
| `embeddings.npy` | `float32` embedding array, shape `(elements, embedding_dim)` |
| `embeddings.json` | Versioned manifest: absolute file locations, both content identities, shape, dtype, and row alignment |
| Region table copy | The processed region table, copied under its original file name so element identifiers travel with the embeddings, plus the copied custom region schema when one was used |

`embeddings.json` records `schema_version` (`1`), the absolute
`embeddings_file` and `region_file` paths, the 64-character
`dataset_identity` and `encoder_identity` values, `shape` as
`[elements, embedding_dim]`, `dtype` (`float32`), and `row_alignment`
(`processed_dataset`). The shape's first axis equals the dataset's element
count and the second axis equals the encoder's embedding dimension.

## Row alignment for joins

Row `i` of `embeddings.npy` is the encoding of row `i` of `signals.npy`,
which is the same genomic element as row `i` of the region table and row `i`
of `split.npy`. Encoding visits rows in order and never reorders, filters, or
subsets them, so embeddings join to genomic elements by row position: attach
column `i` of your own element-level table to row `i` of the embedding array,
using the copied region table as the shared key. The recorded identities let
you confirm later that the dataset and encoder behind a join are exactly the
ones the manifest names.

## What embeddings are not

An embedding is a learned representation of one element example under
full-window reconstruction — not a biological validation of element
membership, which remains established by the upstream analysis that selected
the genomic elements. The export performs no clustering, dimensionality
reduction, or other downstream analysis; those operate on the exported arrays
outside this framework, as summarized in [Outputs](outputs.md).
Demonstration hyperparameters and the synthetic fixture in the code repository
verify mechanics only and are not endorsed defaults or scientific evidence.
