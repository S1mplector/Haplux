# PanContext

PanContext is an early-stage, reference-neutral research tool for asking whether a
genomic model's prediction for the same focal variant remains stable across different
human haplotype backgrounds.

The intended research flow is:

```text
variant + compatible haplotype windows
                  |
                  v
          model predictions
                  |
                  v
  stability, uncertainty, and context attribution
```

Linear references are the first input adapter, not the product boundary. The architecture
is intended to support pangenome paths, de novo assemblies, raw sequence inputs, and models
that do not require reference coordinates. Every canonical context retains both its source
provenance and a sequence-derived GA4GH refget identifier.

## Current milestone

The first milestone establishes a precise representation for sequences, coordinates,
and small variants. This is deliberately smaller than model inference: if coordinates
or reference alleles are wrong, every downstream prediction is scientifically invalid.

The current prototype can:

- validate a local DNA haplotype window;
- distinguish linear-reference, pangenome-path, de novo, and raw-sequence provenance;
- calculate a coordinate-independent GA4GH refget identifier for the model input sequence;
- convert a 1-based VCF position into a 0-based internal interval;
- verify that the declared reference allele matches the sequence;
- apply a small variant and emit a machine-readable result.

## Run the TUI

Create a virtual environment and install the package in editable mode:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
```

Then launch the PanContext workspace:

```sh
.venv/bin/pancontext
```

The TUI opens with a worked example. Edit any field and press **Analyze** or
`Ctrl+R`. Press `E` to restore the example and `Q` to quit.

The VCF position field is 1-based. Window starts and all internal coordinates are
0-based interbase coordinates; the result panel makes that conversion visible.

Run the test suite with:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

## Repository map

```text
src/pancontext/       scientific domain layer and terminal interface
tests/                executable behavior specifications
docs/notes/           bioinformatics learning notes
docs/decisions/       architectural decisions and invariants
```

## Learning trail

Start with:

1. [`01-sequences-coordinates-and-variants.md`](docs/notes/01-sequences-coordinates-and-variants.md)
2. [`02-haplotypes-and-pangenomes.md`](docs/notes/02-haplotypes-and-pangenomes.md)
3. [`03-reference-neutral-contexts-and-models.md`](docs/notes/03-reference-neutral-contexts-and-models.md)

## Status and boundaries

PanContext is pre-alpha research software. It does not provide clinical interpretation,
diagnosis, or patient-specific recommendations. The first releases will use public data
and explicitly non-clinical evaluation claims.
