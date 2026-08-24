"""Deterministic, UI-independent variant context analysis.

This module is the application boundary for PanContext's current milestone. User
interfaces collect an :class:`AnalysisRequest` and render an :class:`AnalysisResult`;
all scientific validation and result construction happens here and is headlessly
testable.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from pancontext.context import (
    ContextSource,
    SequenceContext,
    SequenceProvenance,
    ga4gh_sequence_id,
)
from pancontext.domain import HaplotypeWindow, Variant


SCHEMA_VERSION = "pancontext.analysis.v1"
CoordinateRow = Tuple[str, str, str]


@dataclass(frozen=True)
class AnalysisRequest:
    """Typed input contract shared by interactive and headless front ends."""

    source_type: ContextSource
    source_name: str
    sequence_id: str
    window_start: int
    sequence: str
    vcf_position: int
    reference: str
    alternate: str
    sample_id: Optional[str] = None
    haplotype_id: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_type", ContextSource(self.source_type))


@dataclass(frozen=True)
class AnalysisResult:
    """Validated context transformation and its reproducible report fields."""

    context: SequenceContext
    variant: Variant
    alternate_sequence: str
    variant_kind: str

    @property
    def baseline_content_id(self) -> str:
        """Return the identifier for the observed source window."""

        return self.context.content_id

    @property
    def alternate_content_id(self) -> str:
        """Return the identifier for the synthetic alternate model input."""

        return ga4gh_sequence_id(self.alternate_sequence)

    @property
    def status_text(self) -> str:
        """Return the compact validation summary used by front ends."""

        provenance = self.context.provenance
        return (
            f"Validated: {self.variant_kind} from {provenance.source_type.label} on "
            f"{self.variant.sequence_id}:[{self.variant.start}, {self.variant.end})"
        )

    @property
    def interpretation(self) -> str:
        """Return a deterministic scientific interpretation of the transformation."""

        provenance = self.context.provenance
        return (
            f"The VCF position {self.variant.start + 1} becomes internal start "
            f"{self.variant.start}. The declared REF allele matches the supplied window, "
            "so this sequence replacement is safe to pass to later model adapters. "
            f"The observed input is {self.baseline_content_id}; the constructed alternate "
            f"is {self.alternate_content_id}. Source provenance remains "
            f"{provenance.source_name}."
        )

    @property
    def coordinate_rows(self) -> Tuple[CoordinateRow, ...]:
        """Return presentation-neutral rows describing external and internal identity."""

        window = self.context.window
        provenance = self.context.provenance
        return (
            ("Context source", provenance.source_type.label, provenance.source_name),
            ("Sequence", window.sequence_id, window.sequence_id),
            ("Baseline content ID", window.sequence, self.baseline_content_id),
            ("Alternate content ID", self.alternate_sequence, self.alternate_content_id),
            ("Variant position", str(self.variant.start + 1), str(self.variant.start)),
            (
                "Variant interval",
                "VCF POS + REF",
                f"[{self.variant.start}, {self.variant.end})",
            ),
            ("Window interval", str(window.start), f"[{window.start}, {window.end})"),
            (
                "Alleles",
                f"{self.variant.reference} to {self.variant.alternate}",
                "validated",
            ),
        )

    def as_dict(self) -> Dict[str, Any]:
        """Return a stable, JSON-serializable analysis report."""

        window = self.context.window
        provenance = self.context.provenance
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "validated",
            "context": {
                "source": {
                    "type": provenance.source_type.value,
                    "name": provenance.source_name,
                    "sample_id": provenance.sample_id,
                    "haplotype_id": provenance.haplotype_id,
                },
                "sequence_id": window.sequence_id,
                "interval": {
                    "start": window.start,
                    "end": window.end,
                    "coordinate_system": "0-based-half-open-interbase",
                },
            },
            "variant": {
                "kind": self.variant_kind,
                "input": {
                    "position": self.variant.start + 1,
                    "coordinate_system": "1-based-VCF-style",
                },
                "internal_interval": {
                    "start": self.variant.start,
                    "end": self.variant.end,
                },
                "reference": self.variant.reference,
                "alternate": self.variant.alternate,
            },
            "model_inputs": {
                "baseline": {
                    "sequence": window.sequence,
                    "content_id": self.baseline_content_id,
                    "construction": "observed-context",
                },
                "alternate": {
                    "sequence": self.alternate_sequence,
                    "content_id": self.alternate_content_id,
                    "construction": "focal-variant-applied",
                },
            },
        }


def classify_variant(variant: Variant) -> str:
    """Classify a validated sequence replacement by allele lengths."""

    if len(variant.reference) == len(variant.alternate) == 1:
        return "single-nucleotide variant"
    if len(variant.alternate) > len(variant.reference):
        return "insertion"
    if len(variant.alternate) < len(variant.reference):
        return "deletion"
    return "multi-nucleotide substitution"


def analyze_variant(request: AnalysisRequest) -> AnalysisResult:
    """Validate and transform one focal variant without any UI dependency."""

    window = HaplotypeWindow(
        sequence_id=request.sequence_id,
        start=request.window_start,
        sequence=request.sequence,
    )
    context = SequenceContext(
        window=window,
        provenance=SequenceProvenance(
            source_type=request.source_type,
            source_name=request.source_name,
            sample_id=request.sample_id,
            haplotype_id=request.haplotype_id,
        ),
    )
    variant = Variant.from_vcf(
        sequence_id=request.sequence_id,
        position=request.vcf_position,
        reference=request.reference,
        alternate=request.alternate,
    )
    alternate_sequence = variant.apply_to(window)
    return AnalysisResult(
        context=context,
        variant=variant,
        alternate_sequence=alternate_sequence,
        variant_kind=classify_variant(variant),
    )
