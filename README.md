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

The current milestone establishes precise sequence and coordinate handling, paired
multi-context experiments, and the first real-data adapter. Model inference remains a
separate boundary: if coordinates or reference alleles are wrong, every downstream
prediction is scientifically invalid.

The current prototype can:

- validate a local DNA haplotype window;
- distinguish linear-reference, phased-VCF-haplotype, pangenome-path, de novo, and
  raw-sequence provenance;
- calculate a coordinate-independent GA4GH refget identifier for the model input sequence;
- convert a 1-based VCF position into a 0-based internal interval;
- verify that the declared reference allele matches the sequence;
- apply a small variant and emit a versioned, machine-readable result;
- run the complete scientific analysis without opening the TUI;
- construct matched REF/ALT inputs when either allele was originally observed;
- run multi-context experiments with explicit skipped-context reasons;
- calculate descriptive effect stability using deterministic development adapters;
- accept a strict, versioned experiment-request JSON document;
- reconstruct local diploid haplotypes from indexed FASTA and phased VCF/BCF input;
- apply supported nearby variants before locating the focal allele on each haplotype;
- retain provider exclusions and input identities in a versioned real-data report.

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

Press `1` for **Experiment**, `2` for **FASTA + VCF**, `3` for **Context Inspector**,
`4` for **Guide**, `Ctrl+R` to rerun the active workflow, `D` to restore the experiment
demo, `L` to load the prepared public lesson, and `Q` to quit. The guided data loader marks
required fields, checks local files and indexes as you type, previews the requested sequence
length and maximum context count, reconstructs haplotypes, and sends successful runs to the
Experiment dashboard. The inspector validates one projected sequence window and is useful
for debugging provider output.

In the Experiment workspace, focus the paired-effects table and move with the arrow keys.
The selected-context panel shows that chromosome copy's provenance, locus, observed allele,
matched REF/ALT sequence change, scores, and effect without rerunning the experiment.

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

## Run indexed FASTA/VCF data

The FASTA must have a `.fai` index. The VCF must be bgzip-compressed and have a `.tbi` or
`.csi` index; BCF with a CSI index is also accepted by the underlying HTS reader. Contig
names are exact: `chr1` and `1` are intentionally not guessed to be equivalent.

Run the repository's indexed fixture end to end:

```sh
make real-data-example
```

For your own files:

```sh
.venv/bin/pancontext vcf-experiment \
  --fasta /data/GRCh38.fa \
  --vcf /data/cohort.vcf.gz \
  --assembly GRCh38 \
  --contig chr1 \
  --position 103 \
  --ref C \
  --alt T \
  --left-flank 512 \
  --right-flank 512 \
  --sample HG001 \
  --pretty
```

Repeat `--sample` to select multiple samples, or omit it to inspect every VCF sample. The
command emits `pancontext.real-data-experiment.v1`. A partial result is still written to
standard output when compatible haplotypes exist; exclusions remain visible under
`provider.issues`.

To prepare the compact public-data teaching locus used in the guided lessons, run:

```sh
make public-lesson
```

This downloads Ensembl's GRCh38 chromosome 22 reference and extracts a two-kilobase,
three-sample slice from the indexed 1000 Genomes phased VCF. Generated data stays under
`.pancontext-data/` and is not committed to Git. Once prepared, press `L` in the TUI or
choose **Load public lesson**. The preset uses a motif-count experiment designed to expose
one genuine context-dependent result across the six reconstructed chromosome copies.

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
5. [`05-phased-vcf-haplotype-reconstruction.md`](docs/notes/05-phased-vcf-haplotype-reconstruction.md)

The supported FASTA/VCF policies and remaining format boundaries are recorded in
[`docs/real-data-readiness.md`](docs/real-data-readiness.md).

## Status and boundaries

PanContext is pre-alpha research software. It does not provide clinical interpretation,
diagnosis, or patient-specific recommendations. The first releases will use public data
and explicitly non-clinical evaluation claims.
