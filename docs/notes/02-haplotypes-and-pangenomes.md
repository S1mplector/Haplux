# Lesson 02: haplotypes and pangenomes

## Genotype versus haplotype

Humans are usually diploid: most autosomal regions are represented by two chromosome
copies, one inherited from each biological parent.

A **genotype** describes which alleles an individual has at a locus. A **haplotype**
describes alleles that occur together on the same physical chromosome copy. This phase
information matters because nearby variants can jointly change a motif, codon, splice
signal, or model input.

```text
haplotype A: ... A C C T G ...
haplotype B: ... A T C T A ...
```

Knowing that a person has `C/T` at one locus and `G/A` at another does not tell us
whether `C` travels with `G` or with `A`. A phased haplotype does.

## Why one linear reference is insufficient

A linear reference provides one path through the genome. Reads or variants that differ
substantially from that path can be harder to align or represent, especially in highly
variable, duplicated, or structurally complex regions. This is often called reference bias.

A **pangenome** represents sequence from multiple genomes. A graph pangenome commonly uses:

- nodes for sequence segments;
- edges for allowed adjacencies;
- paths for particular haplotypes or assemblies.

Different haplotypes can share most nodes and diverge only where their sequences differ.

## Why this matters to Haplux

A genomic model usually receives a local sequence window. If we always construct that
window from one linear reference, the model sees only one surrounding context. Haplux
will instead place the same focal variant into multiple compatible haplotype paths and ask:

```text
Does the prediction remain stable when the surrounding human sequence changes?
```

Instability is not automatically an error. It could indicate:

- a real interaction between the focal variant and nearby sequence;
- a model that is sensitive to irrelevant changes;
- an out-of-distribution sequence;
- incorrect graph projection;
- an ambiguous or non-equivalent variant representation.

The scientific work is distinguishing these explanations.

## Terms to write down

- **Assembly:** a set of sequences representing a reconstructed genome.
- **Contig:** a contiguous assembled sequence.
- **Locus:** a location or region on a biological sequence.
- **Allele:** a sequence state at a locus.
- **Genotype:** the collection of alleles an individual has at a locus.
- **Phase:** which alleles occur together on the same chromosome copy.
- **Haplotype:** a phased sequence of alleles on one chromosome copy.
- **Pangenome:** a representation incorporating sequence from multiple genomes.
- **Path:** one traversal through a sequence graph, often representing a haplotype.
- **Projection:** mapping a location or variant from one path/reference to another.

## Exercise

Imagine two haplotypes differ at five nearby bases, but both can contain the same focal
variant. A model score changes from 0.15 on one haplotype to 0.91 on the other.

Write down at least three possible explanations before calling either score correct.
Good answers include biological sequence interaction, model instability, mapping error,
different window construction, or distribution shift.

## Sources

- [Human Pangenome Reference Consortium data](https://humanpangenome.org/data/)
- [GA4GH Variation Representation Specification](https://vrs.ga4gh.org/en/latest/)

