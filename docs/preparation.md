# Preparation

Preparation turns your regions, signal tracks, split assignments, and
reference FASTA into a processed dataset. This is the only stage that
interprets genomic region formats, orientation, normalization, or split
assignment; training and embedding consume the processed numeric interface.

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
    "path": "/absolute/path/to/northwood_split.npy"
  },
  "output_dir": "/absolute/path/to/northwood_dataset"
}
```

The supported `regions.type` values are `bed3`, `bed6`, `bed6gene`,
`bed3gene`, `narrowPeak`, `TREbed`, and `bedGraph`; alternatively, replace
`type` with a `schema` absolute path for a custom region schema. `split.type`
is always `provided`, because splits are supplied upstream. `orientation` is
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

## Processed-dataset outputs

A successful run writes a processed-dataset directory containing:

| Path | Meaning |
| --- | --- |
| `signals.npy` | Jointly sum-normalized `float32` signals, shape `(elements, channels, positions)` |
| `regions.*` | Typed, fixed-length region table in the same row order as `signals.npy`, plus any custom region schema |
| `split.npy` | Row-aligned `uint8` split assignments (`0` train, `1` validation, `2` test) |
| `dataset.json` | Versioned schema, channel order, dimensions, normalization, orientation, region format, and source provenance |

`dataset.json` records the SHA-256 dataset identity computed over canonical
metadata and the region, signal, and split contents, so changed content cannot
masquerade as the same dataset. Every path recorded in `dataset.json` is
absolute; consumers use paths exactly as written. Confirm your channel names,
element count, and window length in `dataset.json` before training: training
obtains them from this manifest.

The prepared dataset feeds [Training](training.md), and the trained encoder
later produces embeddings documented under [Embedding](embedding.md).
