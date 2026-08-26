import unittest

from haplux.context import (
    ContextSource,
    SequenceContext,
    SequenceProvenance,
    ga4gh_sequence_id,
)
from haplux.domain import (
    HaplotypeWindow,
    ReferenceMismatchError,
    SequenceValidationError,
    Variant,
)


class HaplotypeWindowTests(unittest.TestCase):
    def test_normalizes_sequence_and_computes_half_open_end(self) -> None:
        window = HaplotypeWindow(sequence_id="chr1", start=100, sequence="aaccgg")

        self.assertEqual(window.sequence, "AACCGG")
        self.assertEqual(window.end, 106)

    def test_rejects_unsupported_dna_symbols(self) -> None:
        with self.assertRaisesRegex(SequenceValidationError, "unsupported DNA symbol"):
            HaplotypeWindow(sequence_id="chr1", start=0, sequence="ACXG")


class SequenceContextTests(unittest.TestCase):
    def test_computes_known_ga4gh_sequence_identifier(self) -> None:
        self.assertEqual(
            ga4gh_sequence_id("ACGT"),
            "SQ.aKF498dAxcJAqme6QYQ7EZ07-fiw8Kw2",
        )
        self.assertEqual(ga4gh_sequence_id("ac gt\n"), ga4gh_sequence_id("ACGT"))

    def test_preserves_source_provenance_separately_from_content_identity(self) -> None:
        window = HaplotypeWindow(sequence_id="chr1", start=100, sequence="AACCGG")
        reference = SequenceContext(
            window=window,
            provenance=SequenceProvenance(
                source_type=ContextSource.LINEAR_REFERENCE,
                source_name="GRCh38",
            ),
        )
        assembly = SequenceContext(
            window=window,
            provenance=SequenceProvenance(
                source_type=ContextSource.DE_NOVO_ASSEMBLY,
                source_name="sample-assembly-v1",
            ),
        )

        self.assertEqual(reference.content_id, assembly.content_id)
        self.assertNotEqual(reference.provenance, assembly.provenance)

    def test_rejects_blank_provenance_name(self) -> None:
        with self.assertRaisesRegex(SequenceValidationError, "source name"):
            SequenceProvenance(
                source_type=ContextSource.RAW_SEQUENCE,
                source_name="  ",
            )


class VariantTests(unittest.TestCase):
    def test_converts_vcf_position_to_zero_based_start(self) -> None:
        variant = Variant.from_vcf(
            sequence_id="chr1",
            position=103,
            reference="C",
            alternate="T",
        )

        self.assertEqual(variant.start, 102)
        self.assertEqual(variant.end, 103)

    def test_applies_single_nucleotide_variant(self) -> None:
        window = HaplotypeWindow(sequence_id="chr1", start=100, sequence="AACCGG")
        variant = Variant.from_vcf(
            sequence_id="chr1",
            position=103,
            reference="C",
            alternate="T",
        )

        self.assertEqual(variant.apply_to(window), "AATCGG")

    def test_applies_anchored_deletion(self) -> None:
        window = HaplotypeWindow(sequence_id="chr1", start=100, sequence="AACCGG")
        variant = Variant.from_vcf(
            sequence_id="chr1",
            position=102,
            reference="ACC",
            alternate="A",
        )

        self.assertEqual(variant.apply_to(window), "AAGG")

    def test_rejects_reference_mismatch(self) -> None:
        window = HaplotypeWindow(sequence_id="chr1", start=100, sequence="AACCGG")
        variant = Variant.from_vcf(
            sequence_id="chr1",
            position=103,
            reference="G",
            alternate="T",
        )

        with self.assertRaisesRegex(ReferenceMismatchError, "expected 'G', observed 'C'"):
            variant.apply_to(window)

    def test_rejects_variant_outside_window(self) -> None:
        window = HaplotypeWindow(sequence_id="chr1", start=100, sequence="AACCGG")
        variant = Variant.from_vcf(
            sequence_id="chr1",
            position=200,
            reference="A",
            alternate="T",
        )

        with self.assertRaisesRegex(ReferenceMismatchError, "outside window"):
            variant.apply_to(window)


if __name__ == "__main__":
    unittest.main()
