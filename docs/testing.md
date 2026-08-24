# Testing PanContext

## Rule

If behavior can be expressed without judging pixels or physical input hardware, it belongs
in an automated headless test.

## Run the complete suite

```sh
make check
```

The release gate compiles the source and tests, runs every automated test, and checks the
installed environment for dependency conflicts.

The suite currently covers:

- DNA normalization and validation;
- VCF-to-internal coordinate conversion;
- reference matching and bounds checking;
- SNV, insertion, deletion, and multi-nucleotide substitution construction;
- all four context-source types;
- provenance and GA4GH refget content identity;
- baseline versus synthetic alternate model inputs;
- deterministic, versioned JSON serialization;
- headless command success, failure, streams, and exit codes;
- fresh-process module entry-point success and failure behavior;
- TUI mounting at wide and compact terminal sizes;
- TUI rendering of valid and invalid analyses;
- keyboard-triggered analysis through `Ctrl+R`.

## Run one analysis without the TUI

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

Successful reports are written to standard output and return exit code `0`. Scientific
validation failures are written as JSON to standard error and return exit code `2`. This
makes the command suitable for scripts and continuous integration.

## Test-layer ownership

```text
domain tests       sequence and variant invariants
analysis tests     end-to-end scientific result construction
CLI tests          JSON contract, streams, and process semantics
TUI tests          widget wiring and rendering state
manual review      terminal-specific visual quality only
```

Tests must target the lowest layer that owns the behavior. For example, a reference mismatch
is primarily an analysis/domain test; the TUI needs only one test proving it renders that
failure correctly.

## Not implemented yet

No current test implies support for real FASTA, VCF, GFA, GBZ, model inference, or homology
resolution. Those capabilities must arrive with fixtures and headless conformance tests.
