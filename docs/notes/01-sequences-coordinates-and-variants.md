# Lesson 01: sequences, coordinates, and variants

## The mental model

A **sequence** is an ordered string of biological residues. For DNA, the canonical
bases are A, C, G, and T. N is often used when the base is unknown. Real formats may
also use additional IUPAC ambiguity symbols; Haplux deliberately starts with the
smaller `ACGTN` alphabet and will expand when real input requires it.

A **reference sequence** is the sequence used as the coordinate system for describing
something else. It is not “the correct human genome.” GRCh38, for example, is a useful
assembly of reference sequences, but any one person differs from it at millions of sites.

A **variant** describes a difference relative to a particular reference sequence:

```text
sequence identifier + location + reference allele + alternate allele
```

An **allele** is one sequence state at a locus. “Reference” and “alternate” are roles in
a representation; they do not automatically mean normal, healthy, harmful, common, or rare.

## Coordinate systems

Two conventions matter immediately:

### 1-based residue coordinates

The first base is position 1. VCF uses a 1-based `POS` field. Humans often find this
natural because there is no position zero.

```text
bases:       A  A  C  C  G  G
position:    1  2  3  4  5  6
```

### 0-based interbase coordinates

Locations are the boundaries between bases. A start is inclusive and an end is exclusive.
This is the same half-open interval idea used by Python slices. GA4GH VRS uses this model.

```text
boundaries: 0  1  2  3  4  5  6
bases:        A  A  C  C  G  G
```

The third base occupies `[2, 3)`. A six-base sequence occupies `[0, 6)`.

## Worked example

Suppose a VCF-like record says:

```text
CHROM=chr1  POS=103  REF=C  ALT=T
```

The VCF position is 1-based, so the internal start is:

```text
103 - 1 = 102
```

Because the reference allele has length 1, the interval is `[102, 103)`. Before applying
the change, software must confirm that the reference sequence really contains `C` there.
If it contains another base, likely causes include the wrong assembly, the wrong contig,
an off-by-one error, an unnormalized variant, or corrupt input.

## Why indels are trickier

VCF normally anchors insertions and deletions with at least one shared base. For example:

```text
REF=ACC  ALT=A
```

means that `CC` is deleted after the shared `A`. Other standards may represent the same
biological change using an empty replacement sequence and a minimal interval. Equivalent
biological variants can therefore have different textual representations. Variant
normalization will become a dedicated Haplux milestone.

## Rules to write down

1. A coordinate is meaningless without its reference sequence and convention.
2. Convert external coordinates once, at the system boundary.
3. Use one internal coordinate convention everywhere.
4. Always verify the reference allele before applying a variant.
5. Reference/alternate does not mean healthy/harmful.
6. Textually different variants can describe the same biological change.

## Exercise

For the sequence `AACCGG` beginning at internal coordinate 100:

1. What internal interval corresponds to VCF position 104 with `REF=C`?
2. What alternate sequence results from changing `C` to `G` there?
3. Why should the software reject `REF=A` at that position?

Answers: `[103, 104)`, `AACGGG`, and because the observed reference base is `C`, not `A`.

## Sources

- [GA4GH HTS specifications and canonical VCF 4.5](https://github.com/samtools/hts-specs)
- [GA4GH VRS Sequence Location](https://vrs.ga4gh.org/en/latest/concepts/LocationAndReference/SequenceLocation.html)
