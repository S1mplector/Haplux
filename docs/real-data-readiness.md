# Real-data readiness contract

PanContext's core is ready for a first real-data provider when the provider can translate its
source records into `ExperimentContext` objects without changing experiment or model code.

## Provider input

A provider receives:

- a focal variant with normalized REF and ALT alleles;
- a 1-based anchor locus on a named source;
- requested left and right flanks.

It returns validated projected context records plus structured non-fatal issues. Provider
context IDs must be unique.

## First FASTA/VCF provider scope

The first real adapter should deliberately support:

- one indexed linear FASTA assembly;
- one VCF containing biallelic small variants;
- explicit assembly/source naming;
- phased diploid genotypes when sample haplotypes are requested;
- `ACGTN` sequence and literal alleles;
- 1-based VCF input converted once to 0-based internal intervals;
- deterministic left/right-flank extraction;
- source, sample, haplotype, contig, and input-file provenance.

It should reject or issue structured exclusions for:

- symbolic alleles such as `<DEL>`;
- breakends and translocations;
- unphased heterozygous genotypes;
- ambiguous contig aliases;
- REF mismatches against FASTA;
- loci too close to sequence boundaries for the requested policy;
- unsupported ploidy or missing genotype calls;
- multiallelic records until allele selection is explicit.

## Required headless fixtures

The adapter must arrive with a tiny synthetic FASTA, index, VCF, and expected experiment
report covering:

1. REF-observed and ALT-observed haplotypes;
2. homozygous and heterozygous phased samples;
3. an anchored insertion and deletion;
4. a REF mismatch;
5. an unphased call;
6. a boundary failure;
7. deterministic provider metadata and issue ordering.

## Policies that must remain explicit

- Variant normalization and left alignment
- Contig alias resolution
- Strand orientation
- Flank extraction at sequence boundaries
- Fixed-length model input handling for indels
- Treatment of `N` and later IUPAC ambiguity symbols
- Sample and haplotype ordering

None of these may be hidden as an undocumented default.
