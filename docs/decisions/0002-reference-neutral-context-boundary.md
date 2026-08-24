# ADR 0002: use a reference-neutral context boundary

## Status

Accepted for the prototype architecture.

## Context

PanContext begins with a linear-reference and VCF-style workflow because it gives us a
tractable coordinate contract. The scientific goal is broader: compare model behavior
across linear references, pangenome paths, de novo assemblies, and raw sequence inputs.

A sequence-only interface loses where a context came from. A coordinate-only interface
assumes one naming authority and cannot recognize identical sequence reached through a
different assembly or path.

## Decision

Every model-ready sequence context carries two independent forms of identity:

1. source provenance: source type, source name, sequence/path name, interval, and later
   optional sample and haplotype identifiers;
2. sequence content identity: a GA4GH refget `SQ.` identifier computed from the actual
   normalized window sequence.

Context providers will translate linear references, graph paths, de novo contigs, and raw
sequences into this canonical boundary. Model adapters will consume canonical contexts and
must not require all contexts to use the same original coordinate system.

The initial variant-entry adapter remains VCF-like and converts its 1-based position at
ingestion. This is an adapter constraint, not a restriction on the canonical context model.

## Consequences

- PanContext is reference-neutral, not identity-free.
- A model can be reference-free while its input retains explicit provenance.
- Identical sequence windows from different sources share a content identifier but retain
  distinct provenance.
- Comparisons must establish locus or homology equivalence separately from content identity.
- Model adapters can begin with raw-sequence models and later include track-valued and
  graph-native models.
- PanContext must not imply that a synthetic alternate window existed in the source data.

## Deliberate non-goals for this milestone

- loading FASTA, VCF, GFA, GBZ, or assembly files;
- resolving homology between assemblies;
- normalizing equivalent variant representations;
- executing genomic models;
- claiming full GA4GH VRS object compatibility.

The `SQ.` identifier follows the refget sequence digest algorithm, but the surrounding
PanContext object is currently an internal domain model rather than a VRS object.

## Sources

- [GA4GH refget sequences v2.0](https://ga4gh.github.io/refget/sequences/)
- [GA4GH VRS sequence reference](https://vrs.ga4gh.org/en/latest/concepts/LocationAndReference/SequenceReference.html)
