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

For each context, PanContext computes a paired model effect:

```text
effect_h = model(ALT in haplotype h) - model(REF in haplotype h)
```

Stability is then summarized across those paired effects rather than inferred from raw model
scores alone.

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
- apply a small variant and emit a versioned, machine-readable result;
- run the complete scientific analysis without opening the TUI.
- construct matched REF/ALT inputs when either allele was originally observed;
- run multi-context experiments with explicit skipped-context reasons;
- calculate descriptive effect stability using deterministic development adapters;
- accept a strict, versioned experiment-request JSON document.

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

The TUI opens on the **Experiment** workspace with a three-haplotype demonstration already
analyzed. Enter a `pancontext.experiment-request.v1` JSON path and choose **Run file**, or
choose **Load demo** to restore the bundled request. The paired-effect table and stability
cards are views over the same headless experiment engine used by the CLI.

Press `1` for **Experiment**, `2` for **Context Inspector**, `Ctrl+R` to rerun the active
workflow, `D` to restore the experiment demo, and `Q` to quit. The **Context Inspector**
validates one projected sequence window and is useful for debugging provider output.

In the inspector, the VCF position field is 1-based. Window starts and all internal
coordinates are 0-based interbase coordinates; the result panel makes that conversion
visible.

## Run headlessly

Use the same analysis engine without opening the interface:

```sh
.venv/bin/pancontext analyze \
  --source-type linear_reference \
  --source-name GRCh38 \
  --sequence-id chr1 \
  --window-start 100 \
  --sequence AACCGG \
  --position 103 \
  --ref C \
  --alt T \
  --pretty
```

The command writes a `pancontext.analysis.v1` JSON report. Validation failures use standard
error and exit code `2`, allowing scripts to stop on scientifically invalid input.

Run the bundled multi-context experiment:

```sh
make experiment-example
```

Or invoke it directly:

```sh
.venv/bin/pancontext experiment \
  --input tests/fixtures/experiment_request.json \
  --pretty
```

The GC-content and motif-count adapters are deterministic development instruments, not
biological models.

Run the test suite with:

```sh
make check
```

See [`docs/testing.md`](docs/testing.md) for the headless testing contract and manual-only
boundary.

## Repository map

```text
src/pancontext/       scientific domain layer and terminal interface
tests/                executable behavior specifications
docs/notes/           bioinformatics learning notes
docs/decisions/       architectural decisions and invariants
docs/testing.md       automated testing policy and commands
```

## Learning trail

Start with:

1. [`01-sequences-coordinates-and-variants.md`](docs/notes/01-sequences-coordinates-and-variants.md)
2. [`02-haplotypes-and-pangenomes.md`](docs/notes/02-haplotypes-and-pangenomes.md)
3. [`03-reference-neutral-contexts-and-models.md`](docs/notes/03-reference-neutral-contexts-and-models.md)
4. [`04-paired-effects-and-stability.md`](docs/notes/04-paired-effects-and-stability.md)

Before implementing a real FASTA/VCF loader, read
[`docs/real-data-readiness.md`](docs/real-data-readiness.md).

## Status and boundaries

PanContext is pre-alpha research software. It does not provide clinical interpretation,
diagnosis, or patient-specific recommendations. The first releases will use public data
and explicitly non-clinical evaluation claims.
