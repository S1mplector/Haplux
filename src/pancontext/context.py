"""Reference-neutral sequence context identity and provenance.

Coordinates say where a sequence came from within a source. Content identifiers
say what the sequence is. PanContext keeps both because neither one is enough for
reproducible comparisons across references, graph paths, and assemblies.
"""

from base64 import urlsafe_b64encode
from dataclasses import dataclass
from enum import Enum
from hashlib import sha512
from typing import Optional

from pancontext.domain import HaplotypeWindow, SequenceValidationError


class ContextSource(str, Enum):
    """Kinds of sequence source supported by PanContext's canonical boundary."""

    LINEAR_REFERENCE = "linear_reference"
    PHASED_VCF_HAPLOTYPE = "phased_vcf_haplotype"
    PANGENOME_PATH = "pangenome_path"
    DE_NOVO_ASSEMBLY = "de_novo_assembly"
    RAW_SEQUENCE = "raw_sequence"

    @property
    def label(self) -> str:
        """Return a concise label suitable for reports and user interfaces."""

        return {
            ContextSource.LINEAR_REFERENCE: "Linear reference",
            ContextSource.PHASED_VCF_HAPLOTYPE: "Phased VCF haplotype",
            ContextSource.PANGENOME_PATH: "Pangenome path",
            ContextSource.DE_NOVO_ASSEMBLY: "De novo assembly",
            ContextSource.RAW_SEQUENCE: "Raw sequence",
        }[self]


def ga4gh_sequence_id(sequence: str) -> str:
    """Return the GA4GH refget identifier derived from sequence content.

    Refget canonicalization retains ASCII letters and uppercases them. The digest then
    uses SHA-512 truncated to 24 bytes and unpadded base64url encoding.
    """

    canonical = "".join(
        character for character in sequence.upper() if "A" <= character <= "Z"
    )
    if not canonical:
        raise SequenceValidationError("sequence content ID requires at least one letter")

    digest = sha512(canonical.encode("ascii")).digest()[:24]
    encoded = urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"SQ.{encoded}"


def _optional_label(value: Optional[str], *, field_name: str) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise SequenceValidationError(f"{field_name} must not be blank when provided")
    return normalized


@dataclass(frozen=True)
class SequenceProvenance:
    """Describe where a sequence context was obtained.

    ``source_name`` is deliberately source-specific: examples include ``GRCh38``,
    ``HPRC-v2``, an assembly accession, or ``manual-entry``.
    """

    source_type: ContextSource
    source_name: str
    sample_id: Optional[str] = None
    haplotype_id: Optional[str] = None

    def __post_init__(self) -> None:
        try:
            source_type = ContextSource(self.source_type)
        except ValueError as error:
            raise SequenceValidationError(
                f"unsupported context source type: {self.source_type!r}"
            ) from error

        source_name = self.source_name.strip()
        if not source_name:
            raise SequenceValidationError("source name must not be blank")

        object.__setattr__(self, "source_type", source_type)
        object.__setattr__(self, "source_name", source_name)
        object.__setattr__(
            self,
            "sample_id",
            _optional_label(self.sample_id, field_name="sample ID"),
        )
        object.__setattr__(
            self,
            "haplotype_id",
            _optional_label(self.haplotype_id, field_name="haplotype ID"),
        )

    @property
    def label(self) -> str:
        """Return a human-readable provenance label without losing source type."""

        details = [self.source_name]
        if self.sample_id is not None:
            details.append(f"sample={self.sample_id}")
        if self.haplotype_id is not None:
            details.append(f"haplotype={self.haplotype_id}")
        return f"{self.source_type.label}: " + ", ".join(details)


@dataclass(frozen=True)
class SequenceContext:
    """A validated sequence window paired with explicit source provenance."""

    window: HaplotypeWindow
    provenance: SequenceProvenance

    @property
    def content_id(self) -> str:
        """Return a coordinate-independent GA4GH identifier for the window sequence."""

        return ga4gh_sequence_id(self.window.sequence)
