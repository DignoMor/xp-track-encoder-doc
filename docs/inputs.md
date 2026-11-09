# Inputs

Before writing any configuration, assemble four inputs. You supply all of
them; preparation never selects regions, never generates a split
assignment, and never downloads data.

## Genomic elements and reference FASTA

Your genomic elements of interest are fixed-length regions on a reference
genome. Membership is established by your upstream biological analysis — for
example, which transcribed transcriptional regulatory elements to include —
and Track Encoder does not redefine the cohort.

- **Fixed lengths.** Every element must have the same length. Preparation
  rejects collections whose region lengths vary.
- **Region format.** Provide either a supported named region format
  (`bed3`, `bed6`, `bed6gene`, `bed3gene`, `narrowPeak`, `TREbed`, or
  `bedGraph`) or a custom region schema. The choice is recorded, and each
  processed dataset receives its own rows of the region table, in source
  order and in the same format.
- **Reference FASTA.** Preparation requires an absolute genome FASTA path and
  constructs the collection through the public genomic-elements interface. The
  reference workflow validates against the FASTA but does not extract genomic
  sequence. Record the absolute path of your own reference FASTA.

## Signal tracks

Each named signal track becomes one explicitly ordered channel. A track is a
row-aligned numeric array: one row per genomic element, one value per
nucleotide position, so each track array has shape
`(elements, positions)` and every track shares the same element count and
window length.

- **Row alignment.** Row `i` of every track array, row `i` of the region
  table, and row `i` of the split assignment identify the same genomic
  element.
  Preparation preserves input order end to end, so each signal stays attached
  to the correct element.
- **Channel order.** Channels are consolidated in the declared track order
  into one signal array of shape `(elements, channels, positions)` with type
  `float32`. Track names keep their meaning through declaration order; there
  is no silent reordering between experiments.
- **Explicit transforms.** Each track declares either `none` or `absolute`.
  Use `absolute` for conventionally negative tracks whose strand storage
  convention needs correcting; the absolute value is applied before any
  validation. Signed data with `none` is validated as written.

## Split assignment

The **split assignment** is supplied upstream as a row-aligned NumPy array of
shape `(elements,)` with dtype `uint8`: `0` for train, `1` for val, and `2`
for test. Preparation uses it only to divide your region table into separate
processed datasets, one per split that has rows; it is not copied into any
dataset. Preparation never chooses or randomizes splits, so reusing a split
assignment reuses exactly the same elements in each dataset.

A split does not need rows. A split with no rows simply produces no dataset,
so to prepare data only for evaluation, for example from another cell type,
assign every element `2` and preparation publishes only a test dataset.

## Joint normalization

Preparation jointly sum-normalizes every element across all of its channels
and positions: each element example sums to one. This emphasizes signal shape
while preserving the relative allocation among channels, and it removes total
magnitude. The normalization choice is recorded in the dataset manifest, and
training reads channel count and window length from that manifest rather than
from user configuration.

## Invalid-input rules

Preparation rejects invalid data with an error that names the responsible
field, track, or region row, instead of silently imputing or discarding:

- Variable-length regions.
- Negative signal values after the declared per-track transform.
- Non-finite signal values.
- Elements whose joint signal sum is zero.
- Split assignments whose length does not match the region count, that
  contain values outside `0`, `1`, `2`, or that have no rows at all.
- Duplicate track names.
- Non-absolute paths or unknown configuration fields.
- A nonempty output directory: preparation never merges into or overwrites
  existing outputs.

With valid inputs in hand, continue to [Preparation](preparation.md).
