# Preparation

Preparation turns your regions, signal tracks, split assignment, and
reference FASTA into processed datasets: each split that has rows is published
as its own complete, standalone processed dataset. This is the only stage that
interprets genomic region formats, orientation, normalization, or the split
assignment; training, evaluation, embedding, and reconstruction consume the
processed numeric interface.

## Complete preparation configuration

Write a preparation configuration with absolute paths. Every path below is a
clearly marked placeholder beginning with `/absolute/path/to/`; the names are
fictional. Substitute your own absolute paths, keeping them absolute, and the
result validates against the shipped preparation schema.

```json
{
  "schema_version": 1,
  "regions": {
    "path": "/absolute/path/to/northwood_elements.bed3",
    "type": "bed3"
  },
  "fasta_path": "/absolute/path/to/references/hg38.fa",
  "tracks": [
    {
      "name": "northwood_track_alpha",
      "path": "/absolute/path/to/northwood_track_alpha.npy",
      "transform": "none"
    },
    {
      "name": "northwood_track_beta",
      "path": "/absolute/path/to/northwood_track_beta.npy",
      "transform": "absolute"
    }
  ],
  "orientation": "genomic",
  "normalization": "joint_sum",
  "split": {
    "type": "provided",
    "path": "/absolute/path/to/northwood_split_assignment.npy"
  },
  "output_dir": "/absolute/path/to/northwood_prepared"
}
```

The supported `regions.type` values are `bed3`, `bed6`, `bed6gene`,
`bed3gene`, `narrowPeak`, `TREbed`, and `bedGraph`; alternatively, replace
`type` with a `schema` absolute path for a custom region schema. `split.path`
names your split assignment, and `split.type` is always `provided`, because
the split assignment is supplied upstream. `orientation` is
always `genomic` and `normalization` is always `joint_sum` in the current
framework. Unknown fields are rejected, so a misspelled field fails early
rather than being ignored.

## Run preparation

Run the preparation command with the absolute path of your configuration:

```bash
track-encoder prepare --config /absolute/path/to/prepare.json
```

The command refuses a nonempty output directory. On invalid data it exits
nonzero and reports the responsible field, track, or region row without a
traceback by default; rerun with `--debug` for the full traceback.

## Prepared outputs

`output_dir` receives one subdirectory per split that has rows, plus a
preparation log:

| Path | Meaning |
| --- | --- |
| `train/` | Processed dataset of the rows assigned `0` |
| `val/` | Processed dataset of the rows assigned `1` |
| `test/` | Processed dataset of the rows assigned `2` |
| `preparation.json` | Informational log: the source row count and, per published dataset, its row count and absolute path |

A split with no rows produces no directory; an all-test split assignment
yields only `test/`. Each published directory is a complete processed dataset
that any command accepts. Whether it acts as a train, val, or test dataset is
decided by the command you pass it to, not by the dataset: `train` takes a
train dataset and a val dataset (see [Training](training.md)), and `evaluate`
scores a full checkpoint on any compatible dataset, typically the test
dataset (see [Evaluation](evaluation.md)). `preparation.json` is a summary for
you to check at a glance; no command reads it.

## Processed-dataset contents

Each processed dataset directory contains:

| Path | Meaning |
| --- | --- |
| `signals.npy` | Jointly sum-normalized `float32` signals, shape `(elements, channels, positions)` |
| `regions.*` | This dataset's rows of the typed, fixed-length region table, in source order and the source format, in the same row order as `signals.npy`, plus any custom region schema |
| `source_rows.npy` | Provenance only: `int64`, one entry per row, each the row's index in your source region table |
| `dataset.json` | Schema version `2`, channel order, dimensions, normalization, orientation, region format, and source provenance |

Every row of a processed dataset belongs to it; no dataset carries a split
column. `dataset.json` records, as provenance only, the split the dataset was
carved from (`provenance.source_split`: `train`, `val`, or `test`) and the
absolute path of `source_rows.npy` (`provenance.source_rows`). Use
`source_rows.npy` to link any per-row result back to your original elements:
row `i` of the dataset is row `source_rows[i]` of the source region table.
Joint normalization is per element, so a dataset's signals equal the same rows
of an unsplit preparation.

`dataset.json` also records the SHA-256 **dataset identity**, computed over
canonical metadata and the dataset's region table, any custom region schema,
and signal contents, so changed content cannot masquerade as the same dataset.
Provenance, including `source_split` and `source_rows.npy`, does not
contribute: identical content prepared through different split assignments
has the same identity. Every path recorded in `dataset.json` is absolute;
consumers use paths exactly as written. Confirm your channel names, element
count, and window length in `dataset.json` before training: training obtains
them from the train dataset's manifest.

Commands reject a processed dataset whose `dataset.json` is not schema version
`2`, by field `schema_version`. Datasets prepared by earlier releases, which
kept all splits in one directory, must be prepared again.

The prepared datasets feed [Training](training.md) and
[Evaluation](evaluation.md), and the trained encoder later produces embeddings
documented under [Embedding](embedding.md).
