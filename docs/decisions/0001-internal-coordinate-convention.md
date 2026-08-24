# ADR 0001: use 0-based half-open interbase coordinates internally

## Status

Accepted for the initial prototype.

## Context

PanContext will ingest formats and APIs with different coordinate conventions. VCF uses
a 1-based position, while graph libraries, Python slices, BED-like intervals, and GA4GH
VRS commonly use 0-based boundaries or half-open intervals.

## Decision

All PanContext domain objects use 0-based, half-open interbase intervals: `[start, end)`.
Adapters must convert external coordinates at ingestion and record the source convention.

## Consequences

- Interval length is always `end - start`.
- Adjacent intervals compose without overlap: `[0, 3)` followed by `[3, 5)`.
- Python slicing uses the same coordinates.
- VCF ingestion subtracts one from `POS` exactly once.
- Serialized results must state their coordinate convention.

