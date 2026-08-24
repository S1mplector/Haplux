# ADR 0004: compare paired effects across contexts

## Status

Accepted.

## Context

Raw model scores naturally vary between haplotype backgrounds. Comparing only alternate
scores would confound the focal allele with every neighboring difference in the window.
Some source haplotypes already contain the alternate allele, so assuming every supplied
window contains REF would also exclude valid contexts or misstate provenance.

## Decision

For each compatible context, PanContext constructs a matched pair that preserves the same
neighboring haplotype background:

```text
baseline_h  = background h with the focal REF allele
alternate_h = background h with the focal ALT allele
effect_h    = model(alternate_h) - model(baseline_h)
```

The source record explicitly states whether REF or ALT was observed. The other member of
the pair is marked as constructed. PanContext compares `effect_h` across contexts and keeps
raw baseline and alternate predictions for auditing.

The first stability report is descriptive: mean, minimum, maximum, range, population
standard deviation, sign counts, sign agreement, and sign consistency. It does not apply an
arbitrary biological significance threshold.

## Consequences

- REF-observed and ALT-observed haplotypes can participate in the same experiment.
- A content identifier is recorded independently for every baseline and alternate input.
- Invalid projections are skipped with a stage, error type, and reason.
- An experiment can be completed, partial, or failed.
- Model predictions must be finite and model metadata must be JSON-serializable.
- Fixed-length handling for indels remains an explicit future model-input policy.

## Development models

GC-content and motif-count adapters exist only as deterministic pipeline instruments. Their
reports are labelled `development-only` and must not be presented as biological models.
