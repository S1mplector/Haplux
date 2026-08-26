"""Deterministic, UI-independent variant context analysis.

This module is the application boundary for Haplux's current milestone. User
interfaces collect an :class:`AnalysisRequest` and render an :class:`AnalysisResult`;
all scientific validation and result construction happens here and is headlessly
testable.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from haplux.context import (
    ContextSource,
    SequenceContext,
    SequenceProvenance,
    ga4gh_sequence_id,
)
from haplux.domain import HaplotypeWindow, Variant


SCHEMA_VERSION = "haplux.analysis.v1"
CoordinateRow = Tuple[str, str, str]


class ObservedAllele(str, Enum):
    """Allele present in a supplied source context at the focal locus."""

    REFERENCE = "reference"
    ALTERNATE = "alternate"


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
    observed_allele: ObservedAllele = ObservedAllele.REFERENCE
    sample_id: Optional[str] = None
    haplotype_id: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_type", ContextSource(self.source_type))
        object.__setattr__(self, "observed_allele", ObservedAllele(self.observed_allele))


@dataclass(frozen=True)
class AnalysisResult:
    """Validated context transformation and its reproducible report fields."""

    context: SequenceContext
    variant: Variant
    baseline_sequence: str
    alternate_sequence: str
    observed_allele: ObservedAllele
    variant_kind: str

    @property
    def baseline_content_id(self) -> str:
        """Return the identifier for the baseline model input."""

        return ga4gh_sequence_id(self.baseline_sequence)

    @property
    def alternate_content_id(self) -> str:
        """Return the identifier for the alternate model input."""

        return ga4gh_sequence_id(self.alternate_sequence)

    @property
    def baseline_construction(self) -> str:
        """Describe whether the baseline was observed or constructed."""

        if self.observed_allele is ObservedAllele.REFERENCE:
            return "observed-context"
        return "focal-reference-constructed"

    @property
    def alternate_construction(self) -> str:
        """Describe whether the alternate was observed or constructed."""

        if self.observed_allele is ObservedAllele.ALTERNATE:
            return "observed-context"
        return "focal-variant-applied"

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
            f"{self.variant.start}. The declared observed {self.observed_allele.value} "
            "allele matches the supplied window, so the matched REF/ALT pair is safe to "
            f"pass to later model adapters. The baseline input is {self.baseline_content_id}; "
            f"the alternate input is {self.alternate_content_id}. Source provenance remains "
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
            ("Baseline content ID", self.baseline_sequence, self.baseline_content_id),
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
                "observed_allele": self.observed_allele.value,
                "observed_content_id": self.context.content_id,
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
                    "sequence": self.baseline_sequence,
                    "content_id": self.baseline_content_id,
                    "construction": self.baseline_construction,
                },
                "alternate": {
                    "sequence": self.alternate_sequence,
                    "content_id": self.alternate_content_id,
                    "construction": self.alternate_construction,
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
    if request.observed_allele is ObservedAllele.REFERENCE:
        baseline_sequence = window.sequence
        alternate_sequence = variant.apply_to(window)
    else:
        reverse_variant = Variant.from_vcf(
            sequence_id=request.sequence_id,
            position=request.vcf_position,
            reference=variant.alternate,
            alternate=variant.reference,
        )
        baseline_sequence = reverse_variant.apply_to(window)
        alternate_sequence = window.sequence
    return AnalysisResult(
        context=context,
        variant=variant,
        baseline_sequence=baseline_sequence,
        alternate_sequence=alternate_sequence,
        observed_allele=request.observed_allele,
        variant_kind=classify_variant(variant),
    )
