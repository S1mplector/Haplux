# ADR 0005: reconstruct local haplotypes from indexed FASTA and phased VCF

## Status

Accepted.

## Decision

The first real-data adapter uses `pysam` over an indexed FASTA and indexed VCF/BCF. It
fetches one reference-coordinate window, validates local REF alleles against FASTA, and
applies supported records independently to two diploid haplotypes per compatible sample.

Heterozygous calls must be phased. Contig matching is exact. Focal offsets are measured in
the reconstructed sequence rather than inferred from reference coordinates after indels.

Unsupported carrying calls exclude the affected sample and emit structured provider issues.
Global query contradictions, such as a focal REF mismatch or incomplete boundary window,
fail the provider request.

## Consequences

- The experiment engine remains independent of HTS file formats.
- A real local haplotype includes supported nearby variants, not only the focal substitution.
- Indexed interval access scales independently of whole-file length.
- The initial adapter deliberately excludes ambiguous phase, multiallelic focal records,
  overlapping compound variants, alias guessing, and automatic normalization.
