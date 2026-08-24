"""Core domain objects for sequence windows and small variants.

PanContext accepts familiar 1-based VCF positions at its input boundary, then
uses 0-based, half-open interbase coordinates internally. Keeping that invariant
in one place prevents silent off-by-one errors in later graph and model code.
"""

from dataclasses import dataclass


DNA_ALPHABET = frozenset("ACGTN")


class SequenceValidationError(ValueError):
    """Raised when a sequence or allele violates the current DNA contract."""


class ReferenceMismatchError(ValueError):
    """Raised when a variant's reference allele does not match its window."""


def _normalized_dna(value: str, *, field_name: str) -> str:
    normalized = value.upper()
    invalid = sorted(set(normalized) - DNA_ALPHABET)
    if invalid:
        symbols = ", ".join(invalid)
        raise SequenceValidationError(
            f"{field_name} contains unsupported DNA symbol(s): {symbols}"
        )
    return normalized


@dataclass(frozen=True)
class HaplotypeWindow:
    """A contiguous sequence interval from one named haplotype or reference.

    ``start`` is a 0-based interbase coordinate on ``sequence_id``. Therefore a
    six-base window beginning at 100 spans the half-open interval ``[100, 106)``.
    """

    sequence_id: str
    start: int
    sequence: str

    def __post_init__(self) -> None:
        if not self.sequence_id.strip():
            raise SequenceValidationError("sequence_id must not be blank")
        if self.start < 0:
            raise SequenceValidationError("window start must be non-negative")

        normalized = _normalized_dna(self.sequence, field_name="sequence")
        if not normalized:
            raise SequenceValidationError("sequence must not be empty")
        object.__setattr__(self, "sequence", normalized)

    @property
    def end(self) -> int:
        """Return the exclusive 0-based end coordinate."""

        return self.start + len(self.sequence)


@dataclass(frozen=True)
class Variant:
    """A small sequence replacement on a named sequence.

    ``start`` is 0-based and ``end`` is exclusive. The current representation
    preserves VCF-style anchored alleles; normalization will be a later milestone.
    """

    sequence_id: str
    start: int
    reference: str
    alternate: str

    def __post_init__(self) -> None:
        if not self.sequence_id.strip():
            raise SequenceValidationError("sequence_id must not be blank")
        if self.start < 0:
            raise SequenceValidationError("variant start must be non-negative")

        reference = _normalized_dna(self.reference, field_name="reference allele")
        alternate = _normalized_dna(self.alternate, field_name="alternate allele")
        if not reference:
            raise SequenceValidationError("reference allele must not be empty")
        if not alternate:
            raise SequenceValidationError("alternate allele must not be empty")
        if reference == alternate:
            raise SequenceValidationError("reference and alternate alleles must differ")

        object.__setattr__(self, "reference", reference)
        object.__setattr__(self, "alternate", alternate)

    @classmethod
    def from_vcf(
        cls,
        *,
        sequence_id: str,
        position: int,
        reference: str,
        alternate: str,
    ) -> "Variant":
        """Create a variant from a 1-based VCF position."""

        if position < 1:
            raise SequenceValidationError("VCF position must be at least 1")
        return cls(
            sequence_id=sequence_id,
            start=position - 1,
            reference=reference,
            alternate=alternate,
        )

    @property
    def end(self) -> int:
        """Return the exclusive 0-based end coordinate of the reference allele."""

        return self.start + len(self.reference)

    def apply_to(self, window: HaplotypeWindow) -> str:
        """Apply this variant to a compatible haplotype window.

        The returned string is the alternate sequence. The input window remains
        unchanged because domain objects are immutable.
        """

        if self.sequence_id != window.sequence_id:
            raise ReferenceMismatchError(
                f"variant sequence {self.sequence_id!r} does not match "
                f"window sequence {window.sequence_id!r}"
            )
        if self.start < window.start or self.end > window.end:
            raise ReferenceMismatchError(
                f"variant interval [{self.start}, {self.end}) is outside "
                f"window interval [{window.start}, {window.end})"
            )

        local_start = self.start - window.start
        local_end = local_start + len(self.reference)
        observed = window.sequence[local_start:local_end]
        if observed != self.reference:
            raise ReferenceMismatchError(
                f"reference mismatch at [{self.start}, {self.end}): "
                f"expected {self.reference!r}, observed {observed!r}"
            )

        return window.sequence[:local_start] + self.alternate + window.sequence[local_end:]

