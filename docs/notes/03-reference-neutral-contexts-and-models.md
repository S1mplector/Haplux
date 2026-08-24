# Lesson 03: reference-neutral contexts and model boundaries

## Two independent questions

For every model input, PanContext must answer:

1. Where did this sequence come from?
2. What sequence did the model actually receive?

The first question is provenance. The second is content identity. They are related but
not interchangeable.

```text
source provenance                         content identity
GRCh38, chr1:[100, 106)                   SQ.<digest>
HPRC path HG002#1:[812, 818)              SQ.<digest>
de novo contig42:[900, 906)               SQ.<digest>
```

If all three intervals contain exactly `AACCGG`, their content identifier is the same even
though their coordinate systems and biological provenance differ.

## Reference-free does not mean identity-free

A reference-free model may accept only a DNA string. It does not need to know whether that
string came from GRCh38, a pangenome path, or a new assembly. PanContext still needs that
information to reproduce and interpret the comparison.

Likewise, two equal strings are not automatically the same biological locus. Short DNA
sequences repeat throughout a genome. Establishing that contexts are homologous requires
an anchor such as an alignment, graph projection, stable locus mapping, or sufficiently
specific flanking sequence.

## Context providers and model adapters

PanContext will separate acquisition from inference:

```text
FASTA/VCF       pangenome graph       de novo contig       raw sequence
    |                  |                    |                    |
    +------------------+--------------------+--------------------+
                               |
                  canonical sequence context
                               |
              +----------------+----------------+
              |                |                |
         sequence model   track model     graph-native model
```

A **context provider** understands a source format and produces canonical contexts. A
**model adapter** understands a model's input and output contract. This prevents model code
from becoming entangled with assembly names, graph libraries, or VCF conventions.

## Sequence-derived identifiers

GA4GH refget identifies sequence content using a digest. The `ga4gh` identifier:

1. canonicalizes the sequence as uppercase letters without formatting;
2. computes SHA-512;
3. retains the first 24 digest bytes;
4. encodes them with unpadded URL-safe Base64;
5. prefixes the result with `SQ.`.

For example:

```text
ACGT -> SQ.aKF498dAxcJAqme6QYQ7EZ07-fiw8Kw2
```

This is content-addressing: the identifier depends on the sequence, not the filename or
coordinate alias.

## Terms to write down

- **Provenance:** evidence describing the origin and processing history of data.
- **Content address:** an identifier calculated from the content itself.
- **Homology:** shared ancestry between biological sequences.
- **Context provider:** an adapter that obtains and canonicalizes sequence contexts.
- **Model adapter:** an adapter that translates canonical contexts into model inputs and
  normalizes model outputs.
- **Reference-neutral:** able to preserve and compare multiple coordinate authorities
  without treating one linear reference as universally privileged.

## Current limit

The TUI lets us label the four source types, validate a local sequence, and calculate its
content identifier. It does not yet verify that a manually entered source label is true,
resolve homology, load a graph, or run a model.

## Exercise

Two windows have the same `SQ.` identifier. One is labelled GRCh38 and one is labelled as a
de novo contig.

1. What can you conclude? Their normalized sequence content is identical.
2. What can you not conclude? You cannot conclude from the digest alone that they represent
   the same biological locus or share the same provenance.

## Sources

- [GA4GH refget sequences v2.0](https://ga4gh.github.io/refget/sequences/)
- [GA4GH VRS sequence reference](https://vrs.ga4gh.org/en/latest/concepts/LocationAndReference/SequenceReference.html)
