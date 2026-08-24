# Lesson 04: paired effects and context stability

## Why raw scores are not enough

Suppose a model gives two haplotypes baseline scores of `0.20` and `0.80`. That difference
may be caused entirely by nearby haplotype sequence. If the focal alternate allele changes
both scores by `+0.10`, its predicted effect is stable even though the raw scores differ.

For haplotype background `h`:

```text
effect_h = score(ALT in h) - score(REF in h)
```

The subtraction is paired: every other base in the two inputs should remain the same.

## Observed versus constructed

A real haplotype may already carry REF or ALT. PanContext records that fact and constructs
the missing counterfactual:

```text
REF observed:  baseline observed, alternate constructed
ALT observed:  baseline constructed, alternate observed
```

This distinction is provenance, not a change to the biological question.

## Descriptive stability

Across context effects, PanContext currently reports:

- **Mean effect:** average paired effect.
- **Effect range:** maximum minus minimum effect.
- **Population standard deviation:** dispersion of effects in the analyzed context set.
- **Sign counts:** contexts with positive, negative, or effectively zero effects.
- **Sign agreement:** fraction in the largest sign category.
- **Sign consistency:** whether positive and negative effects never both occur.

The zero tolerance is explicit because floating-point model outputs may contain tiny values
that should be treated as zero for sign summaries.

These are descriptive statistics. A large range is not automatically a biological discovery,
and PanContext does not yet assign significance or confidence intervals.

## Invalid contexts

A context can be excluded because its observed allele does not match, the projected locus is
outside the supplied window, its sequence is invalid, or a model rejects the input. Skipping
must retain the stage and exact reason; silently dropping contexts could bias the result.

## Terms to write down

- **Counterfactual sequence:** a constructed sequence representing what would be observed
  if the focal allele were changed while other chosen features stayed fixed.
- **Paired comparison:** a comparison where matched observations differ in the target factor.
- **Effect sign:** whether ALT increases, decreases, or does not change the model output.
- **Dispersion:** the amount values vary around one another.
- **Context compatibility:** whether a focal allele can be represented and validated on a
  particular projected background.
