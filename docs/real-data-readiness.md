# Indexed FASTA/VCF provider contract

PanContext's first real-data provider translates indexed linear-reference and phased VCF
records into `ExperimentContext` objects without changing experiment or model code.

## Provider input

A provider receives:

- a focal variant with normalized REF and ALT alleles;
- a 1-based anchor locus on a named source;
- requested left and right flanks.

It returns validated projected context records plus structured non-fatal issues. Provider
context IDs must be unique.

## Implemented FASTA/VCF provider scope

The adapter deliberately supports:

- one indexed linear FASTA assembly;
- one indexed VCF/BCF containing biallelic small variants;
- explicit assembly/source naming;
- phased diploid genotypes when sample haplotypes are requested;
- `ACGTN` sequence and literal alleles;
- 1-based VCF input converted once to 0-based internal intervals;
- deterministic left/right-flank extraction;
- source, sample, haplotype, contig, and input-file provenance.

It rejects the query or issues structured sample exclusions for:

- symbolic alleles such as `<DEL>`;
- breakends and translocations;
- unphased heterozygous genotypes;
- ambiguous contig aliases;
- REF mismatches against FASTA;
- loci too close to sequence boundaries for the requested policy;
- unsupported ploidy or missing genotype calls;
- multiallelic records until allele selection is explicit.

## Headless fixtures

The adapter includes a tiny synthetic FASTA, index, VCF, and expected experiment report
covering:

1. REF-observed and ALT-observed haplotypes;
2. homozygous and heterozygous phased samples;
3. an anchored insertion and deletion;
4. a REF mismatch;
5. an unphased call;
6. a boundary failure;
7. deterministic provider metadata and issue ordering.

## Current explicit policies

- Variant normalization: exact VCF representation; no automatic normalization or left
  alignment yet.
- Contig aliases: exact names only.
- Strand: forward reference orientation only.
- Boundaries: the complete requested reference interval is required.
- Indels: flanks are defined in reference coordinates, so reconstructed haplotype lengths
  and focal offsets may differ.
- Alphabet: literal `ACGTN` records only; later IUPAC symbols are not accepted.
- Ordering: VCF-header sample order, then haplotype 1 and haplotype 2.
- Overlapping records: an affected carrying sample is excluded rather than guessed.
- FILTER: PASS records by default; carrying samples are excluded for filtered records.

None of these may be hidden as an undocumented default.

## Still missing from real-data support

- automatic normalization and left alignment;
- overlapping/compound variant resolution;
- polyploid and partially phased genotypes;
- contig alias maps and reverse-strand projection;
- graph formats such as GFA/GBZ and assembly-to-assembly homology mapping;
- cohort-scale batching across many focal variants;
- production biological model adapters and fixed-length tokenization policies.
