# Lesson 05: phased VCF haplotype reconstruction

## Why the focal variant is not enough

A reference FASTA describes one linear sequence. A person's two chromosome copies can
contain many nearby variants. If Haplux changed only the focal allele, both inputs would
still have the reference's surrounding sequence and would miss the biological context that
the project is meant to measure.

The provider therefore starts with a reference interval and applies every supported local
VCF call separately to haplotype 1 and haplotype 2.

## Reading a diploid genotype

The VCF `GT` field uses allele indexes. `0` means REF and `1` means the first ALT allele:

```text
0|0  both haplotypes carry REF
0|1  haplotype 1 carries REF; haplotype 2 carries ALT
1|0  haplotype 1 carries ALT; haplotype 2 carries REF
1|1  both haplotypes carry ALT
```

The vertical bar means the call is phased: the file claims to know which chromosome copy
carries each allele. A slash such as `0/1` is unphased. We know the sample is heterozygous,
but not whether nearby ALT alleles occur together or on opposite chromosome copies.
Haplux excludes that sample from the local reconstruction rather than inventing phase.

## Indels change local coordinates

Suppose the focal variant begins ten bases into the reference window. If haplotype 1 has a
two-base insertion upstream, the focal variant begins twelve bases into the reconstructed
haplotype. Its source VCF position has not changed, but its index in the model input has.

```text
reference window:  left flank -------- focal
haplotype window:  left flank --[+2]-- focal
                                      ^ shifted local offset
```

Haplux measures the focal offset while constructing each sequence. It never assumes
that a reference coordinate is still a valid string index after applying an indel.

## Why indexes matter

A human FASTA and cohort VCF are too large to scan for every query. A FASTA `.fai` index and
a tabix/CSI VCF index map a genomic interval to byte or compressed-block locations. The
provider can fetch one local window without reading whole chromosomes or the entire cohort.

Indexing improves access speed; it does not validate biology. Haplux still verifies each
VCF REF allele against FASTA and stops or records an exclusion when the inputs disagree.

## Current conservative choices

- Contig names must match exactly.
- Heterozygous diploid calls must be phased.
- Records must be biallelic literal `ACGTN` replacements.
- The whole requested reference-coordinate window must exist.
- Nearby overlapping variants are not guessed into a compound allele.
- Focal and nearby indels are supported, but reconstructed sequence lengths may differ.

These restrictions make incomplete support visible. Quietly constructing a plausible but
incorrect haplotype would be more dangerous than returning an explicit exclusion.

## Terms to write down

- **Phasing:** assigning alleles to specific chromosome copies.
- **Haplotype:** the ordered alleles carried together on one chromosome copy.
- **Genotype allele index:** the `0`, `1`, and later values in a VCF `GT` field.
- **Tabix index:** an index for coordinate queries over block-compressed genomic records.
- **Projection:** translating source variants into a concrete sequence representation.
- **Local offset:** the position of an allele within a reconstructed sequence string.
