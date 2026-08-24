# ADR 0003: keep scientific analysis headless

## Status

Accepted.

## Context

PanContext has an interactive terminal interface, but coordinate conversion, provenance,
variant validation, model-input construction, and serialization are scientific behavior.
Requiring a person to exercise the TUI to verify those rules would make regressions hard to
detect and results difficult to reproduce in continuous integration.

## Decision

The application layer accepts a typed `AnalysisRequest` and returns an immutable
`AnalysisResult`. It must not import Textual or depend on terminal state.

The TUI is a client of that layer. A headless `pancontext analyze` command is another client
and emits a versioned JSON report. Both paths use the same analysis function.

The report distinguishes:

- the baseline sequence observed in the supplied context;
- the synthetic alternate sequence constructed by applying the focal variant;
- the independent content identifier for each model input;
- the provenance of the observed context.

## Consequences

- Scientific behavior can be tested with ordinary unit tests.
- CI and future workflow engines can run PanContext without a terminal.
- UI wording and table layout do not define the result schema.
- A TUI regression cannot silently change the scientific calculation.
- Schema changes require a new `schema_version` or an explicitly compatible extension.

## Manual testing boundary

Only terminal-emulator-specific appearance, perceived readability, and physical mouse
behavior require human inspection. Textual mounting, responsive layout state, key bindings,
widget values, validation states, and result row counts remain automated headless tests.
